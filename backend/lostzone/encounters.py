"""Deterministic coarse combat with individual casualties and ledger ammo.

This bounded model is a baseline policy, not detailed engine ballistics. The
route planner must schedule actual encounters; it never invents a firefight
because an observer arrived. Engine hydration cancels the abstract resolver.
"""
import hashlib
import json

from .contacts import earliest_contact, trajectory
from .contact_index import ContactIndex, CandidateBudget
from .capture import CaptureBudget
from .economy import integer
from .offline import distance
from .plans import reservations
from .store import Conflict, Invalid, Unavailable, canonical, finite, identifier, persistent_id, positive


class Encounters:
    def __init__(self, world, offline, catalog):
        self.world,self.store,self.offline,self.catalog = world,world.store,offline,catalog
        offline.scheduler.handlers["OfflineCombat"] = self.resolve
        world.plan_validators["OfflineCombat"] = self.capture_valid

    def fighters(self, tx, root):
        if root["kind"] not in ("NPC","MUTANT","GROUP") or not root["alive"]:
            raise Conflict("encounter requires living actors/groups")
        rows = self.offline.members(tx,root,limit=65)
        rows = [row for row in rows if row["kind"] in ("NPC","MUTANT") and row["alive"]]
        if not 1 <= len(rows) <= 64:
            raise Conflict("encounter exceeds bounded individual resolution")
        result,budget = [],CaptureBudget()
        for row in sorted(rows,key=lambda value:value["id"]):
            self.offline.require_offline(tx,row["id"])
            if row["location"] != root["location"]:
                raise Conflict("member is outside encounter location")
            budget.consume(row["state"])
            state = json.loads(row["state"])
            hp = int(finite(state.get("health",1),0,1)*10000)
            if not hp:
                raise Conflict("living actor has zero captured health")
            skill = integer(state.get("experience",0),0,10,"actor experience")
            items = tx.execute("SELECT * FROM item WHERE kind='NPC' AND holder=? ORDER BY id LIMIT 65", (row["id"],))
            weapons = []
            for index,item in enumerate(items):
                if index==64:
                    raise Conflict("combat inventory exceeds bounded resolver")
                entry = self.catalog.entry(item["section"])
                if entry["category"] == "WEAPON":
                    if item["quantity"] != 1:
                        raise Conflict("weapon stacks need individual ledger IDs")
                    budget.consume(item["state"])
                    item_state = json.loads(item["state"])
                    rounds = integer(item_state.get("rounds",0),0,10000,"weapon rounds")
                    condition = int(finite(item_state.get("condition",1),0,1)*10000)
                    power = entry["combat_power"]*condition//10000 if rounds else 0
                    weapons.append({"id":item["id"],"version":item["version"],"state":item_state,"rounds":rounds,"power":power})
            result.append({"id":row["id"],"version":row["version"],"health_bp":hp,"experience":skill,
                           "melee_power":integer(state.get("melee_power",10),1,10000,"melee power"),"weapons":weapons})
        return result

    def hostility(self, tx, a, b):
        factions = [json.loads(row["state"]).get("faction") for row in (a,b)]
        row = tx.execute("SELECT * FROM world_state WHERE name='relations'").fetchone()
        if not row or not all(isinstance(value,str) for value in factions) or factions[0]==factions[1]:
            raise Conflict("encounter has no committed hostile relation")
        pairs = json.loads(row["state"]).get("hostile",[])
        if not isinstance(pairs,list) or not any(isinstance(pair,list) and len(pair)==2 and set(pair)==set(factions) for pair in pairs):
            raise Conflict("factions are not hostile")
        return row["version"]

    def schedule(self, actor, command_id, event_id, first_id, second_id, first_version, second_version, due_ms, seed, radius=50):
        for value in (event_id,first_id,second_id):
            persistent_id(value)
        positive(first_version)
        positive(second_version)
        finite(due_ms)
        finite(radius,.1,200)
        if first_id==second_id or type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid encounter identity/seed")
        payload = {"type":"offline_combat","event_id":event_id,"first_id":first_id,"second_id":second_id,
                   "first_version":first_version,"second_version":second_version,"due_ms":due_ms,"seed":seed,"radius":radius}
        return self.store.command(actor, command_id, payload, lambda tx: self.schedule_in(tx, payload))

    @staticmethod
    def route_capture(tx, entity_id):
        row = tx.execute("SELECT version,active FROM route WHERE entity_id=?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def schedule_in(self, tx, payload, planning_now=None):
        first_id, second_id = payload["first_id"], payload["second_id"]
        first_version, second_version = payload["first_version"], payload["second_version"]
        due_ms, event_id = payload["due_ms"], payload["event_id"]
        roots = [self.offline.require_offline(tx,value,version) for value,version in ((first_id,first_version),(second_id,second_version))]
        if roots[0]["location"]!=roots[1]["location"] or due_ms < (self.world.now() if planning_now is None else planning_now):
            raise Conflict("encounter location/time changed")
        if any(root["kind"]!="GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?",(root["id"],)).fetchone() for root in roots):
            raise Conflict("schedule the persistent group rather than an individual member")
        relation = self.hostility(tx,*roots)
        sides = [self.fighters(tx,root) for root in roots]
        if set(row["id"] for row in sides[0]) & set(row["id"] for row in sides[1]):
            raise Conflict("encounter sides overlap")
        plan = {**payload,"world_id":self.world.world_id,"world_seed":self.world.seed,"location":roots[0]["location"],
                "relation_version":relation,"sides":sides,
                "routes":[self.route_capture(tx, root["id"]) for root in roots]}
        # Freeze input before resolution; owner restarts/observers do not
        # become RNG inputs and cannot change committed casualties.
        plan["capture_hash"] = hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest()
        self.offline.scheduler.schedule_in(tx,event_id,due_ms,"entity:"+first_id,first_version,"OfflineCombat",plan)
        self.store.event(tx,"entity:"+first_id,"OfflineEncounterPlanned",{**payload,"capture_hash":plan["capture_hash"]},self.world.now())
        return {"event_id":event_id,"capture_hash":plan["capture_hash"]}

    def plan_contact(self, actor, command_id, event_id, first_id, second_id,
                     first_version, second_version, horizon_ms, seed, radius=50):
        for value in (event_id, first_id, second_id):
            persistent_id(value)
        positive(first_version); positive(second_version)
        finite(horizon_ms, 1, 86_400_000); finite(radius, .1, 200)
        if first_id == second_id or type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid encounter identity/seed")
        payload = {"type":"offline_contact", "event_id":event_id, "first_id":first_id,
                   "second_id":second_id, "first_version":first_version, "second_version":second_version,
                   "horizon_ms":horizon_ms, "seed":seed, "radius":radius}
        def apply(tx):
            roots = [self.offline.require_offline(tx, value, version) for value, version in
                     ((first_id,first_version),(second_id,second_version))]
            if roots[0]["location"] != roots[1]["location"]:
                raise Conflict("contact candidates are on different maps")
            self.hostility(tx, *roots)
            # Validation also excludes static/dead/member-only candidates.
            for root in roots:
                self.fighters(tx, root)
                if root["kind"] != "GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?", (root["id"],)).fetchone():
                    raise Conflict("plan contact for the persistent group")
            now = self.world.now()
            end = finite(now + horizon_ms)
            paths = [trajectory(self.offline, tx, root, now, end) for root in roots]
            at = earliest_contact(*paths, radius)
            if at is None:
                return {"event_id":None, "reason":"routes do not meet"}
            combat = {key:payload[key] for key in ("event_id","first_id","second_id","first_version","second_version","seed","radius")}
            combat.update(type="offline_combat", due_ms=at)
            result = self.schedule_in(tx, combat, planning_now=now)
            return {**result, "due_ms":at}
        return self.store.command(actor, command_id, payload, apply)

    @staticmethod
    def roll(plan, label):
        data = f"{plan['world_id']}:{plan['world_seed']}:{plan['event_id']}:{plan['seed']}:{plan['capture_hash']}:{label}"
        return int.from_bytes(hashlib.sha256(data.encode("utf-8")).digest()[:8],"big")

    def plan_location(self, actor, command_id, location, horizon_ms, seed, radius=50):
        """One bounded event-driven planning pass; never a per-frame NPC scan.

        Snapshot scanning is still required for this backend adapter. The
        incremental index can be kept by a future route-change subscriber.
        Only the earliest disjoint contacts are reserved; subsequent contacts
        must be replanned after resolution changes the actor captures.
        """
        identifier(location); finite(horizon_ms,1,86_400_000); finite(radius,.1,200)
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid deterministic contact seed")
        payload = {"type":"offline_contacts","location":location,"horizon_ms":horizon_ms,"seed":seed,"radius":radius}
        return self.store.command(actor,command_id,payload,lambda tx:self.location_in(tx,actor,command_id,payload))

    def location_in(self, tx, actor, command_id, payload, planning_now=None, collect=False, reservation_state=None):
        location,horizon_ms,seed,radius = (payload[key] for key in ("location","horizon_ms","seed","radius"))
        rows = tx.execute("SELECT e.* FROM entity e WHERE e.location=? AND e.alive=1 AND e.writer=? AND e.fence=? "
                           "AND e.kind IN ('NPC','MUTANT','GROUP') AND NOT EXISTS "
                           "(SELECT 1 FROM group_member m WHERE m.member_id=e.id) ORDER BY e.id LIMIT 257",
                           (location,"offline:"+location,self.store.epoch))
        roots,budget = [],CaptureBudget(8*1024*1024)
        for row in rows:
            if len(roots)==256:
                raise Unavailable("offline contact actor budget exhausted")
            budget.consume(row["state"])
            roots.append(row)
        reserved,reserved_hazards,cancelled = reservation_state if reservation_state is not None else reservations(self.world,tx,location,self.world.plan_validators)
        now = self.world.now() if planning_now is None else planning_now
        end = finite(now+horizon_ms)
        index,paths,by_id = ContactIndex(),{},{}
        for root in roots:
            if root["id"] in reserved:
                continue
            path = trajectory(self.offline,tx,root,now,end)
            index.upsert(root["id"],location,path)
            paths[root["id"]],by_id[root["id"]] = path,root
        work = CandidateBudget(index.limits["max_checks"])
        pairs = index.pairs(radius,work)
        contacts = []
        for first,second in pairs:
            try:
                self.hostility(tx,by_id[first],by_id[second])
            except Conflict:
                continue
            work.consume(len(paths[first])+len(paths[second]))
            at = earliest_contact(paths[first],paths[second],radius)
            if at is not None:
                contacts.append((at,first,second))
        plans,deferred = [],0
        if collect:
            options = [{"type":"offline_combat","first_id":first,"second_id":second,
                        "first_version":by_id[first]["version"],"second_version":by_id[second]["version"],
                        "due_ms":at,"seed":seed,"radius":radius} for at,first,second in sorted(contacts)]
            return {"options":options,"actors":len(roots),"candidate_pairs":len(pairs),"cancelled_plans":cancelled}
        for at,first,second in sorted(contacts):
            if first in reserved or second in reserved:
                deferred += 1
                continue
            if len(plans) >= 64:
                raise Unavailable("offline encounter admission budget exhausted")
            event_id = hashlib.sha256(f"contact:{self.world.world_id}:{actor}:{command_id}:{first}:{second}".encode("utf-8")).hexdigest()[:32]
            combat = {"type":"offline_combat","event_id":event_id,"first_id":first,"second_id":second,
                      "first_version":by_id[first]["version"],"second_version":by_id[second]["version"],
                      "due_ms":at,"seed":seed,"radius":radius}
            result = self.schedule_in(tx,combat,planning_now=now)
            plans.append({**result,"first_id":first,"second_id":second,"due_ms":at})
            reserved.update((first,second))
        return {"contacts":plans,"actors":len(roots),"candidate_pairs":len(pairs),"deferred_contacts":deferred,
                "cancelled_plans":cancelled}


    def capture_valid(self, tx, plan):
        try:
            roots = [self.offline.require_offline(tx,plan[key],plan[version]) for key,version in
                     (("first_id","first_version"),("second_id","second_version"))]
            return (all(root["alive"] and root["location"]==plan["location"] for root in roots) and
                    [self.route_capture(tx,root["id"]) for root in roots]==plan.get("routes") and
                    self.hostility(tx,*roots)==plan["relation_version"] and
                    [self.fighters(tx,root) for root in roots]==plan["sides"])
        except (Conflict,Invalid,KeyError):
            return False

    def resolve(self, tx, event):
        plan,at = json.loads(event["payload"]),event["due_world_ms"]
        try:
            roots = [self.offline.require_offline(tx,plan[key],plan[version]) for key,version in
                     (("first_id","first_version"),("second_id","second_version"))]
        except Conflict:
            return {"reason":"representation/capture changed"},False
        if [self.route_capture(tx, root["id"]) for root in roots] != plan.get("routes"):
            return {"reason":"route capture changed"},False
        try:
            relation = self.hostility(tx,*roots)
        except Conflict:
            return {"reason":"location/diplomacy changed"},False
        if any(row["location"]!=plan["location"] for row in roots) or relation!=plan["relation_version"]:
            return {"reason":"location/diplomacy changed"},False
        try:
            if [self.fighters(tx,root) for root in roots] != plan["sides"]:
                return {"reason":"individual capture/inventory changed"},False
        except Conflict:
            return {"reason":"individual capture/inventory changed"},False
        positions = [self.offline.position_at(tx,root,at) for root in roots]
        if distance(*positions)>plan["radius"]:
            return {"reason":"routes do not meet"},False
        scores = []
        for side in plan["sides"]:
            score = 0
            for fighter in side:
                weapon = max((value["power"] for value in fighter["weapons"]),default=0)
                power = max(weapon,fighter["melee_power"])
                score += max(1,power*fighter["health_bp"]*(10+fighter["experience"])*(75+self.roll(plan,"power:"+fighter["id"])%51)//100000)
            scores.append(score)
        casualties, survivors, ammo = [],[],[]
        for root,target in zip(roots,positions):
            self.offline.write_positions(tx,root,target)
            tx.execute("UPDATE route SET active=0 WHERE entity_id=?",(root["id"],))
            self.offline.cancel_arrivals(tx,root["id"])
        for index,side in enumerate(plan["sides"]):
            damage_base = scores[1-index]*14000//sum(scores)
            for fighter in side:
                # Shoot only one carried weapon, consume its recorded rounds.
                armed = sorted(fighter["weapons"],key=lambda value:(-value["power"],value["id"]))
                if armed and armed[0]["power"]:
                    weapon = armed[0]
                    spent = min(weapon["rounds"],3+self.roll(plan,"shots:"+fighter["id"])%6)
                    weapon_state = dict(weapon["state"],rounds=weapon["rounds"]-spent)
                    tx.execute("UPDATE item SET state=?,version=version+1 WHERE id=?",(canonical(weapon_state),weapon["id"]))
                    ammo.append({"item_id":weapon["id"],"spent":spent,"remaining":weapon_state["rounds"]})
                damage = damage_base*(80+self.roll(plan,"damage:"+fighter["id"])%41)//100
                health = max(0,fighter["health_bp"]-damage)
                row = tx.execute("SELECT * FROM entity WHERE id=?",(fighter["id"],)).fetchone()
                if not health:
                    self.offline.ownership.die_in(tx,row,"offline_combat",at,{"entity_id":row["id"],"encounter_id":event["id"],"capture_hash":plan["capture_hash"]})
                    casualties.append(row["id"])
                else:
                    state = json.loads(row["state"])
                    state.update(health=health/10000,last_combat_ms=at,
                                 injury_bp=min(10000,integer(state.get("injury_bp",0),0,10000,"injury")+damage//2))
                    tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(canonical(state),row["id"]))
                    survivors.append({"id":row["id"],"health":state["health"]})
        result = {"encounter_id":event["id"],"location":plan["location"],"positions":positions,"capture_hash":plan["capture_hash"],
                  "casualties":casualties,"survivors":survivors,"ammo":ammo,"scores":scores,"occurred_ms":at}
        self.store.event(tx,"entity:"+plan["first_id"],"OfflineEncounterResolved",result,at,committed_ms=self.world.now())
        return result,True
