"""Captured route/anomaly/trap encounters with permanent individual outcomes.

This bounded coarse policy is configured by trusted world/catalog state.
It does not simulate remote collision ticks, manufacture loot, or replace
engine damage volumes. Native ownership/hydration integration is separate.
"""
import hashlib
import json

from .contacts import earliest_contact, trajectory
from .contact_index import ContactIndex, CandidateBudget
from .capture import CaptureBudget
from .economy import integer
from .offline import distance, point
from .plans import reservations
from .store import Conflict, Invalid, Unavailable, canonical, finite, identifier, persistent_id, positive


class Hazards:
    def __init__(self, world, offline, catalog):
        if offline.world is not world or offline.scheduler.world is not world:
            raise Conflict("hazard representation belongs to another world authority")
        self.world,self.store,self.offline,self.catalog = world,world.store,offline,catalog
        offline.scheduler.handlers["OfflineHazard"] = self.resolve
        world.plan_validators["OfflineHazard"] = self.capture_valid

    def hazard_capture(self, row):
        if row["kind"] not in ("ANOMALY","TRAP") or not row["alive"]:
            raise Conflict("hazard requires a living persistent anomaly or trap")
        state = json.loads(row["state"])
        kind = identifier(state.get("hazard_type"))
        active = state.get("active") if row["kind"] == "ANOMALY" else state.get("armed")
        if type(active) is not bool:
            raise Invalid("hazard requires explicit active/armed state")
        if not active:
            raise Conflict("hazard is inactive")
        charges = integer(state.get("charges",0),0,10000,"trap charges")
        if row["kind"] == "TRAP" and not charges:
            raise Conflict("trap has no charges")
        owner = state.get("owner_id")
        if owner is not None:
            persistent_id(owner)
        safe = state.get("safe_factions",[])
        if not isinstance(safe,list) or len(safe)>32:
            raise Invalid("invalid hazard faction policy")
        safe = sorted(set(identifier(faction) for faction in safe))
        return {"id":row["id"],"version":row["version"],"kind":row["kind"],"type":kind,
                "position":point(state.get("position")),"radius":finite(state.get("radius"),.1,200),
                "damage_bp":integer(state.get("damage_bp"),1,10000,"hazard damage"),
                "intensity":finite(state.get("intensity",100),0,100),"charges":charges,"owner_id":owner,
                "safe_factions":safe,"cooldown_ms":finite(state.get("cooldown_ms",60000),1,86_400_000),
                "cooldown_until_ms":finite(state.get("cooldown_until_ms",0)),"state":state}

    def actors(self, tx, root, hazard_type):
        if root["kind"] not in ("NPC","MUTANT","GROUP") or not root["alive"]:
            raise Conflict("hazard requires a living offline actor/group")
        if root["kind"] != "GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?",(root["id"],)).fetchone():
            raise Conflict("hazard contact belongs to the persistent group")
        rows = [row for row in self.offline.members(tx,root,limit=65) if row["kind"] in ("NPC","MUTANT") and row["alive"]]
        if not 1 <= len(rows) <= 64:
            raise Conflict("hazard actor capture exceeds member limit")
        result,budget = [],CaptureBudget()
        for row in sorted(rows,key=lambda row:row["id"]):
            self.offline.require_offline(tx,row["id"])
            if row["location"] != root["location"]:
                raise Conflict("hazard member is on another map")
            budget.consume(row["state"])
            state = json.loads(row["state"])
            health = int(finite(state.get("health",1),0,1)*10000)
            if not health:
                raise Conflict("living hazard participant has zero health")
            known = state.get("known_hazards",[])
            if not isinstance(known,list) or len(known)>64:
                raise Invalid("invalid captured hazard knowledge")
            known = [identifier(value) for value in known]
            inventory = tx.execute("SELECT * FROM item WHERE kind='NPC' AND holder=? ORDER BY id LIMIT 65",(row["id"],))
            items,protection = [],0
            for index,item in enumerate(inventory):
                if index==64:
                    raise Conflict("hazard inventory exceeds capture limit")
                budget.consume(item["state"])
                item_state = json.loads(item["state"])
                items.append(dict(item,state=item_state))
                if item_state.get("equipped") is True:
                    entry = self.catalog.entry(item["section"])
                    if entry["category"] in ("ARMOR","ARTIFACT"):
                        if item["quantity"] != 1:
                            raise Conflict("equipped protection needs individual item IDs")
                        condition = int(finite(item_state.get("condition",1),0,1)*10000)
                        protection = max(protection,entry["hazard_protection_bp"].get(hazard_type,0)*condition//10000)
            result.append({"id":row["id"],"version":row["version"],"health_bp":health,"items":items,
                           "faction":identifier(state.get("faction","unknown")),
                           "experience":integer(state.get("experience",0),0,10,"hazard experience"),
                           "known":hazard_type in known,"protection_bp":protection,
                           "motion":self.offline.position_capture(tx,row)})
        return result

    @staticmethod
    def eligible(actor, hazard, root_id):
        return root_id != hazard["owner_id"] and actor["id"] != hazard["owner_id"] and actor["faction"] not in hazard["safe_factions"]

    def plan_contact(self, actor, command_id, event_id, entity_id, hazard_id,
                     entity_version, hazard_version, horizon_ms, seed):
        for value in (event_id,entity_id,hazard_id):
            persistent_id(value)
        positive(entity_version);positive(hazard_version);finite(horizon_ms,1,86_400_000)
        if entity_id==hazard_id or type(seed) is not int or not 0<=seed<2**64:
            raise Invalid("invalid hazard contact identity/seed")
        payload = {"type":"offline_hazard","event_id":event_id,"entity_id":entity_id,"hazard_id":hazard_id,
                   "entity_version":entity_version,"hazard_version":hazard_version,"horizon_ms":horizon_ms,"seed":seed}
        return self.store.command(actor,command_id,payload,lambda tx:self.schedule_in(tx,payload))

    def schedule_in(self, tx, payload, planning_now=None):
        entity_id,hazard_id = payload["entity_id"],payload["hazard_id"]
        entity_version,hazard_version = payload["entity_version"],payload["hazard_version"]
        event_id = payload["event_id"]
        root = self.offline.require_offline(tx,entity_id,entity_version)
        hazard = self.offline.require_offline(tx,hazard_id,hazard_version)
        if root["location"] != hazard["location"]:
            raise Conflict("hazard contact crosses locations")
        capture = self.hazard_capture(hazard)
        actors = self.actors(tx,root,capture["type"])
        now = self.world.now() if planning_now is None else planning_now
        end = finite(now+payload["horizon_ms"])
        start = max(now,capture["cooldown_until_ms"])
        contacts = []
        if start < end:
            fixed = [(start,capture["position"]),(end,capture["position"])]
            for member in actors:
                if self.eligible(member,capture,root["id"]):
                    row = tx.execute("SELECT * FROM entity WHERE id=?",(member["id"],)).fetchone()
                    at = earliest_contact(trajectory(self.offline,tx,row,start,end),fixed,capture["radius"])
                    if at is not None:
                        contacts.append(at)
        if not contacts:
            return {"event_id":None,"reason":"route does not reach an eligible active hazard"}
        at = min(contacts)
        plan = {**payload,"due_ms":at,"location":root["location"],"world_id":self.world.world_id,
                "world_seed":self.world.seed,"hazard":capture,"actors":actors,
                "motion":self.offline.position_capture(tx,root)}
        plan["capture_hash"] = hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest()
        self.offline.scheduler.schedule_in(tx,event_id,at,"entity:"+entity_id,entity_version,"OfflineHazard",plan)
        self.store.event(tx,"entity:"+entity_id,"OfflineHazardPlanned",{**payload,"due_ms":at,"capture_hash":plan["capture_hash"]},now,committed_ms=self.world.now())
        return {"event_id":event_id,"due_ms":at,"capture_hash":plan["capture_hash"]}

    def capture_valid(self, tx, plan):
        try:
            root = self.offline.require_offline(tx,plan["entity_id"],plan["entity_version"])
            hazard = self.offline.require_offline(tx,plan["hazard_id"],plan["hazard_version"])
            capture = self.hazard_capture(hazard)
            return (root["location"]==plan["location"] and hazard["location"]==plan["location"] and
                    capture==plan["hazard"] and self.actors(tx,root,capture["type"])==plan["actors"] and
                    self.offline.position_capture(tx,root)==plan["motion"])
        except (Conflict,Invalid,KeyError):
            return False

    def plan_location(self, actor, command_id, location, horizon_ms, seed):
        """Discover the next physical hazard contact per unreserved root.

        One bounded location pass, not a distant physics tick. Competing
        contacts need another pass after their captured state is resolved.
        """
        identifier(location);finite(horizon_ms,1,86_400_000)
        if type(seed) is not int or not 0<=seed<2**64:
            raise Invalid("invalid deterministic hazard seed")
        payload = {"type":"offline_hazards","location":location,"horizon_ms":horizon_ms,"seed":seed}
        return self.store.command(actor,command_id,payload,lambda tx:self.location_in(tx,actor,command_id,payload))

    def location_in(self, tx, actor, command_id, payload, planning_now=None, collect=False, reservation_state=None):
        location,horizon_ms,seed = (payload[key] for key in ("location","horizon_ms","seed"))
        reserved,reserved_hazards,cancelled = reservation_state if reservation_state is not None else reservations(self.world,tx,location,self.world.plan_validators)
        now = self.world.now() if planning_now is None else planning_now
        end = finite(now+horizon_ms)
        index,by_hazard = ContactIndex(),{}
        capture_budget,work = CaptureBudget(8*1024*1024),CandidateBudget()
        rows = tx.execute("SELECT * FROM entity WHERE location=? AND alive=1 AND writer=? AND fence=? "
                          "AND kind IN ('ANOMALY','TRAP') ORDER BY id LIMIT 257",
                          (location,"offline:"+location,self.store.epoch))
        hazards_count = 0
        for hazard in rows:
            hazards_count += 1
            if hazards_count>256:
                raise Unavailable("offline hazard population budget exhausted")
            capture_budget.consume(hazard["state"])
            if hazard["id"] in reserved_hazards:
                continue
            try:
                capture = self.hazard_capture(hazard)
            except Conflict:
                continue # Inactive/disarmed hazards are persistent, not removed.
            start = max(now,capture["cooldown_until_ms"])
            if start>=end:
                continue
            index.upsert(hazard["id"],location,[(start,capture["position"]),(end,capture["position"])])
            by_hazard[hazard["id"]] = capture
        query_radius = max((value["radius"] for value in by_hazard.values()),default=.1)
        roots,contacts,participants,segments,candidates = {},{},0,0,0
        rows = tx.execute("SELECT e.* FROM entity e WHERE e.location=? AND e.alive=1 AND e.writer=? AND e.fence=? "
                          "AND e.kind IN ('NPC','MUTANT','GROUP') AND NOT EXISTS "
                          "(SELECT 1 FROM group_member m WHERE m.member_id=e.id) ORDER BY e.id LIMIT 257",
                          (location,"offline:"+location,self.store.epoch))
        roots_count = 0
        for root in rows:
            roots_count += 1
            if roots_count>256:
                raise Unavailable("offline hazard actor budget exhausted")
            capture_budget.consume(root["state"])
            if root["id"] in reserved or not by_hazard:
                continue
            roots[root["id"]] = root
            for member in self.offline.members(tx,root,limit=65):
                if member["kind"] not in ("NPC","MUTANT"):
                    continue
                self.offline.require_offline(tx,member["id"])
                if member["location"]!=location:
                    raise Conflict("hazard member is on another map")
                participants += 1
                if participants>256:
                    raise Unavailable("offline hazard member budget exhausted")
                if member["id"]!=root["id"]:
                    capture_budget.consume(member["state"])
                member_state = json.loads(member["state"])
                candidate_actor = {"id":member["id"],"faction":identifier(member_state.get("faction","unknown"))}
                path = trajectory(self.offline,tx,member,now,end)
                segments += len(path)-1
                if segments>8192:
                    raise Unavailable("offline hazard trajectory budget exhausted")
                for hazard_id in index.query(location,path,query_radius,work):
                    capture = by_hazard[hazard_id]
                    if not self.eligible(candidate_actor,capture,root["id"]):
                        continue
                    candidates += 1
                    if candidates>4096:
                        raise Unavailable("offline hazard candidate budget exhausted")
                    start = max(now,capture["cooldown_until_ms"])
                    member_path = path if start==now else trajectory(self.offline,tx,member,start,end)
                    work.consume(len(member_path))
                    at = earliest_contact(member_path,[(start,capture["position"]),(end,capture["position"])],capture["radius"])
                    if at is not None:
                        key = (root["id"],hazard_id)
                        contacts[key] = min(at,contacts.get(key,at))
        plans,deferred = [],0
        if collect:
            options = [{"type":"offline_hazard","entity_id":root_id,"hazard_id":hazard_id,
                        "entity_version":roots[root_id]["version"],"hazard_version":by_hazard[hazard_id]["version"],
                        "due_ms":at,"horizon_ms":horizon_ms,"seed":seed}
                       for at,root_id,hazard_id in sorted((at,*key) for key,at in contacts.items())]
            return {"options":options,"actors":roots_count,"hazards":hazards_count,"members":participants,
                    "candidates":candidates,"cancelled_plans":cancelled}
        for at,root_id,hazard_id in sorted((at,*key) for key,at in contacts.items()):
            if root_id in reserved or hazard_id in reserved_hazards:
                deferred += 1
                continue
            if len(plans)>=64:
                raise Unavailable("offline hazard contact admission budget exhausted")
            event_id = hashlib.sha256(f"hazard:{self.world.world_id}:{actor}:{command_id}:{root_id}:{hazard_id}".encode("utf-8")).hexdigest()[:32]
            hazard = by_hazard[hazard_id]
            request = {"type":"offline_hazard","event_id":event_id,"entity_id":root_id,"hazard_id":hazard_id,
                       "entity_version":roots[root_id]["version"],"hazard_version":hazard["version"],
                       "horizon_ms":horizon_ms,"seed":seed}
            result = self.schedule_in(tx,request,planning_now=now)
            if result["event_id"] is None:
                raise Conflict("hazard discovery and captured narrow phase disagree")
            plans.append({**result,"entity_id":root_id,"hazard_id":hazard_id})
            reserved.add(root_id);reserved_hazards.add(hazard_id)
        return {"contacts":plans,"actors":roots_count,"hazards":hazards_count,"members":participants,
                "candidates":candidates,"deferred_contacts":deferred,"cancelled_plans":cancelled}


    def resolve(self, tx, event):
        plan = json.loads(event["payload"])
        at = event["due_world_ms"]
        try:
            root = self.offline.require_offline(tx,plan["entity_id"],plan["entity_version"])
            hazard = self.offline.require_offline(tx,plan["hazard_id"],plan["hazard_version"])
            capture = self.hazard_capture(hazard)
            actors = self.actors(tx,root,capture["type"])
            if (root["location"]!=plan["location"] or hazard["location"]!=plan["location"] or
                    capture!=plan["hazard"] or actors!=plan["actors"] or
                    self.offline.position_capture(tx,root)!=plan["motion"]):
                return {"reason":"hazard/member/motion capture changed"},False
        except Conflict:
            return {"reason":"hazard representation/capture changed"},False
        if at < capture["cooldown_until_ms"]:
            return {"reason":"hazard cooldown"},False
        affected = []
        for member in actors:
            row = tx.execute("SELECT * FROM entity WHERE id=?",(member["id"],)).fetchone()
            if self.eligible(member,capture,root["id"]) and distance(self.offline.position_at(tx,row,at),capture["position"])<=capture["radius"]+1e-6:
                affected.append(member)
        if not affected:
            return {"reason":"route misses hazard volume"},False
        target = self.offline.position_at(tx,root,at)
        self.offline.write_positions(tx,root,target)
        tx.execute("UPDATE route SET active=0 WHERE entity_id=?",(root["id"],))
        self.offline.cancel_arrivals(tx,root["id"])
        outcomes,triggered = [],False
        for member in affected:
            data = f"{plan['world_id']}:{plan['world_seed']}:{event['id']}:{plan['seed']}:{plan['capture_hash']}:{member['id']}"
            roll = int.from_bytes(hashlib.sha256(data.encode("utf-8")).digest()[:8],"big")
            avoidance = min(9000,member["experience"]*200+(3000 if member["known"] else 0))
            avoided = roll%10000 < avoidance
            damage = 0 if avoided else int(capture["damage_bp"]*capture["intensity"]/100)*(10000-member["protection_bp"])//10000
            triggered = triggered or not avoided
            health = max(0,member["health_bp"]-damage)
            row = tx.execute("SELECT * FROM entity WHERE id=?",(member["id"],)).fetchone()
            evidence = {"entity_id":row["id"],"hazard_id":hazard["id"],"event_id":event["id"],"capture_hash":plan["capture_hash"]}
            if not health:
                self.offline.ownership.die_in(tx,row,"offline_hazard",at,evidence)
            else:
                state = json.loads(row["state"])
                state.update(health=health/10000,last_hazard_ms=at,last_hazard_id=hazard["id"],
                             injury_bp=min(10000,integer(state.get("injury_bp",0),0,10000,"injury")+damage//2))
                tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(canonical(state),row["id"]))
            outcomes.append({"id":member["id"],"avoided":avoided,"damage_bp":damage,"health":health/10000,"died":not health})
        state = dict(capture["state"],cooldown_until_ms=finite(at+capture["cooldown_ms"]),last_contact_ms=at)
        if hazard["kind"] == "TRAP" and triggered:
            state["charges"] -= 1
            state["armed"] = state["charges"]>0
        tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(canonical(state),hazard["id"]))
        result = {"hazard_id":hazard["id"],"entity_id":root["id"],"capture_hash":plan["capture_hash"],
                  "outcomes":outcomes,"occurred_ms":at,"charges":state.get("charges"),"cooldown_until_ms":state["cooldown_until_ms"]}
        self.store.event(tx,"entity:"+hazard["id"],"OfflineHazardResolved",result,at,committed_ms=self.world.now())
        return result,True
