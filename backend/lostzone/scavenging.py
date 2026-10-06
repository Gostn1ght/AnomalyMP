"""Rare deterministic stash visits moving existing items, never rerolling loot."""
import hashlib
import json

from .economy import DEPOSIT_CATEGORIES, integer
from .offline import distance, point
from .contacts import earliest_contact, trajectory
from .contact_index import ContactIndex, CandidateBudget
from .capture import CaptureBudget
from .store import Conflict, Invalid, Unavailable, canonical, finite, persistent_id, positive


class Scavenging:
    def __init__(self, world, offline, catalog, rules=None, *, capture_limit=4*1024*1024):
        if offline.world is not world or offline.scheduler.world is not world:
            raise Conflict("scavenging representation belongs to another world authority")
        if type(capture_limit) is not int or not 1024<=capture_limit<=4*1024*1024:
            raise Invalid("invalid stash visit capture byte budget")
        self.world, self.store, self.offline, self.catalog = world, world.store, offline, catalog
        self.capture_limit=capture_limit
        rules = {} if rules is None else rules
        if not isinstance(rules, dict):
            raise Invalid("invalid scavenging rules")
        self.rules = {
            "minimum_interval_ms": integer(rules.get("minimum_interval_ms", 21_600_000), 60_000, 604_800_000, "stash visit interval"),
            "chance_bp": integer(rules.get("chance_bp", 800), 0, 10000, "stash visit chance"),
            "radius": finite(rules.get("radius", 10), .1, 30)}
        offline.scheduler.handlers["StashVisited"] = self.visited
        world.plan_validators["StashVisited"] = self.capture_valid

    def participants(self, tx, npc_id, stash_id):
        npc, stash = (self.offline.require_offline(tx, value) for value in (npc_id,stash_id))
        if npc["kind"] != "NPC" or not npc["alive"] or stash["kind"] != "STASH" or not stash["alive"] or npc["location"] != stash["location"]:
            raise Conflict("stash visit requires a living offline stalker in the same location")
        policy = tx.execute("SELECT * FROM container WHERE id=?", (stash_id,)).fetchone()
        if not policy or (policy["policy"] != "NPC_ACCESSIBLE" and
                          not (policy["policy"] == "FACTION" and policy["owner"] == json.loads(npc["state"]).get("faction"))):
            raise Conflict("stash is protected from NPC scavenging")
        if json.loads(stash["state"]).get("locked",False) is not False or self.offline.ownership.quest_required(tx,stash_id):
            raise Conflict("stash is locked or required by an active quest")
        return npc,stash,policy

    def movable_item(self, row):
        if row["section"] not in self.catalog.entries or self.catalog.entry(row["section"])["quest_protected"]:
            return False
        state = json.loads(row["state"])
        return all(state.get(flag,False) is False for flag in ("quest_item","quest_protected"))

    def schedule(self, actor, command_id, event_id, npc_id, stash_id, npc_version, stash_version, due_ms, seed):
        for value in (event_id,npc_id,stash_id):
            persistent_id(value)
        positive(npc_version)
        positive(stash_version)
        finite(due_ms)
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid deterministic visit seed")
        payload = {"type": "stash_visit", "event_id":event_id, "npc_id":npc_id, "stash_id":stash_id,
                   "npc_version":npc_version, "stash_version":stash_version, "due_ms":due_ms, "seed":seed}
        return self.store.command(actor,command_id,payload,lambda tx:self.schedule_in(tx,payload))

    def schedule_in(self, tx, payload, planning_now=None):
        npc,stash,policy=self.participants(tx,payload["npc_id"],payload["stash_id"])
        at=payload["due_ms"];now=self.world.now() if planning_now is None else planning_now
        if (npc["version"],stash["version"]) != (payload["npc_version"],payload["stash_version"]) or at<now:
            raise Conflict("visit version/time changed")
        for row,key in ((npc,"last_scavenge_ms"),(stash,"last_npc_visit_ms")):
            last=json.loads(row["state"]).get(key)
            if last is not None and at-finite(last)<self.rules["minimum_interval_ms"]:
                raise Conflict("NPC or stash was visited too recently")
        positions=[self.offline.position_capture(tx,row) for row in (npc,stash)]
        root=positions[0]["group"]["id"] if positions[0]["group"] else npc["id"]
        if payload.get("root_id",root)!=root:
            raise Conflict("stash visitor's motion root changed")
        plan={**payload,"root_id":root,"rules":self.rules,"container_version":policy["version"],
              "location":npc["location"],"positions":positions}
        self.offline.scheduler.schedule_in(tx,payload["event_id"],at,"entity:"+stash["id"],stash["version"],"StashVisited",plan)
        self.store.event(tx,"entity:"+stash["id"],"StashVisitPlanned",payload,now,committed_ms=self.world.now())
        return {"event_id":payload["event_id"],"due_ms":at}

    def capture_valid(self, tx, plan):
        try:
            npc,stash,policy=self.participants(tx,plan["npc_id"],plan["stash_id"])
            if (npc["version"],stash["version"],policy["version"]) != (plan["npc_version"],plan["stash_version"],plan["container_version"]):
                return False
            return [self.offline.position_capture(tx,row) for row in (npc,stash)]==plan.get("positions")
        except (Conflict,Invalid,KeyError):
            return False

    def options_in(self, tx, payload, now):
        location=payload["location"];end=finite(now+payload["horizon_ms"])
        index,stashes=ContactIndex(),{}
        budget,work=CaptureBudget(8*1024*1024),CandidateBudget()
        rows=tx.execute("SELECT e.* FROM entity e JOIN container c ON c.id=e.id WHERE e.location=? AND e.alive=1 "
                        "AND e.kind='STASH' AND e.writer=? AND e.fence=? AND c.policy IN ('NPC_ACCESSIBLE','FACTION') ORDER BY e.id LIMIT 257",
                        (location,"offline:"+location,self.store.epoch))
        for number,stash in enumerate(rows):
            if number==256:
                raise Unavailable("scavenging stash population budget exhausted")
            budget.consume(stash["state"]);state=json.loads(stash["state"])
            if state.get("locked",False) is not False or self.offline.ownership.quest_required(tx,stash["id"]):
                continue
            last=state.get("last_npc_visit_ms")
            start=max(now,finite(last)+self.rules["minimum_interval_ms"]) if last is not None else now
            if start>=end:
                continue
            index.upsert(stash["id"],location,[(start,point(state.get("position"))),(end,point(state.get("position")))])
            stashes[stash["id"]]=(stash,start)
        options,candidates,segments=[],0,0
        rows=tx.execute("SELECT * FROM entity WHERE location=? AND kind='NPC' AND alive=1 AND writer=? AND fence=? ORDER BY id LIMIT 257",
                        (location,"offline:"+location,self.store.epoch))
        for number,npc in enumerate(rows):
            if number==256:
                raise Unavailable("scavenging NPC population budget exhausted")
            budget.consume(npc["state"])
            if not stashes:
                continue
            state=json.loads(npc["state"]);last=state.get("last_scavenge_ms")
            start=max(now,finite(last)+self.rules["minimum_interval_ms"]) if last is not None else now
            if start>=end:
                continue
            path=trajectory(self.offline,tx,npc,start,end);segments+=len(path)-1
            if segments>8192:
                raise Unavailable("scavenging trajectory budget exhausted")
            motion=self.offline.position_capture(tx,npc)
            root=motion["group"]["id"] if motion["group"] else npc["id"]
            for stash_id in index.query(location,path,self.rules["radius"],work):
                candidates+=1
                if candidates>4096:
                    raise Unavailable("scavenging candidate budget exhausted")
                try:
                    _,stash,_=self.participants(tx,npc["id"],stash_id)
                except Conflict:
                    continue
                contact_start=max(start,stashes[stash_id][1])
                member_path=path if contact_start==start else trajectory(self.offline,tx,npc,contact_start,end)
                work.consume(len(member_path))
                fixed=[(contact_start,point(json.loads(stash["state"])["position"])),(end,point(json.loads(stash["state"])["position"]))]
                at=earliest_contact(member_path,fixed,self.rules["radius"])
                if at is not None:
                    options.append({"type":"offline_scavenge","root_id":root,"npc_id":npc["id"],"stash_id":stash_id,
                                    "npc_version":npc["version"],"stash_version":stash["version"],"due_ms":at,"seed":payload["seed"]})
        return {"options":options,"candidates":candidates}

    def visited(self, tx, event):
        plan = json.loads(event["payload"])
        # Hydration or a new writer cancels abstract interaction. It must never
        # resolve a duplicate alongside a visible engine loot interaction.
        try:
            npc,stash,policy = self.participants(tx,plan["npc_id"],plan["stash_id"])
        except Conflict:
            return {"reason":"participants/protection changed"},False
        if (npc["version"],stash["version"],policy["version"]) != (plan["npc_version"],plan["stash_version"],plan["container_version"]):
            return {"reason":"visit capture changed"},False
        try:
            positions = [self.offline.position_capture(tx,row) for row in (npc,stash)]
        except Conflict:
            return {"reason":"visit motion authority changed"},False
        if positions != plan.get("positions"):
            return {"reason":"visit motion capture changed"},False
        rules,at = plan["rules"],event["due_world_ms"]
        capture_budget=CaptureBudget(self.capture_limit)
        capture_budget.consume(stash["state"]);capture_budget.consume(npc["state"])
        stash_state,npc_state = (json.loads(row["state"]) for row in (stash,npc))
        for state,key in ((stash_state,"last_npc_visit_ms"),(npc_state,"last_scavenge_ms")):
            last=state.get(key)
            if last is not None and at-finite(last)<rules["minimum_interval_ms"]:
                return {"reason":"visit cooldown"},False
        origin = self.offline.position_at(tx,npc,at)
        if distance(origin,self.offline.position_at(tx,stash,at)) > rules["radius"]:
            return {"reason":"route does not reach this stash"},False
        seed = hashlib.sha256(canonical({"world_seed":self.world.seed,"event_id":event["id"],"seed":plan["seed"],
                                         "npc":npc["id"],"stash":stash["id"],"at":at}).encode("utf-8")).digest()
        roll = int.from_bytes(seed[:8],"big")
        action = "NONE"
        item = None
        if roll % 10000 < rules["chance_bp"]:
            # Bound work regardless of box size; ordering is stable across hosts.
            take,deposit=[],[]
            for row in tx.execute("SELECT * FROM item WHERE kind='STASH' AND holder=? ORDER BY id LIMIT 64",(stash["id"],)):
                entry=self.catalog.entries.get(row["section"])
                if entry is None or entry["quest_protected"]:
                    continue
                capture_budget.consume(row["state"]);take.append(row)
            for row in tx.execute("SELECT * FROM item WHERE kind='NPC' AND holder=? ORDER BY id LIMIT 64",(npc["id"],)):
                entry=self.catalog.entries.get(row["section"])
                if entry is None or entry["quest_protected"] or entry["category"] not in DEPOSIT_CATEGORIES:
                    continue
                capture_budget.consume(row["state"])
                if self.movable_item(row):
                    deposit.append(row)
            # The trusted catalog excludes armor/all weapons/artifacts from
            # deposits; individual carried items are moved with the same IDs.
            options = []
            capacity = integer(npc_state.get("carry_capacity_g",50000),0,1_000_000,"NPC carry capacity")
            carried_weight = self.catalog.carry_weight(tx,npc["id"]) if take else 0
            for row in take:
                if not self.movable_item(row):
                    continue
                weight = self.catalog.entry(row["section"])["weight_g"] * row["quantity"]
                if carried_weight + weight <= capacity:
                    options.append(("TAKE",row))
            count = tx.execute("SELECT COUNT(*) FROM item WHERE kind='STASH' AND holder=?", (stash["id"],)).fetchone()[0]
            if count < policy["capacity"]:
                options += [("DEPOSIT",row) for row in deposit]
            if options:
                action,item = options[int.from_bytes(seed[8:16],"big") % len(options)]
                target_kind,target_holder = ("NPC",npc["id"]) if action=="TAKE" else ("STASH",stash["id"])
                tx.execute("UPDATE item SET kind=?,holder=?,version=version+1 WHERE id=?", (target_kind,target_holder,item["id"]))
                tx.execute("UPDATE container SET version=version+1 WHERE id=?", (stash["id"],))
                self.store.event(tx,"item:"+item["id"],"ItemScavenged",
                                 {"item_id":item["id"],"npc_id":npc["id"],"stash_id":stash["id"],"action":action,"visit_id":event["id"]},
                                 at,committed_ms=self.world.now())
        stash_state["last_npc_visit_ms"] = at
        npc_state["last_scavenge_ms"] = at
        for row,state in ((stash,stash_state),(npc,npc_state)):
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (canonical(state),row["id"]))
        return {"action":action,"item_id":item["id"] if item else None,"npc_id":npc["id"],"stash_id":stash["id"]},True
