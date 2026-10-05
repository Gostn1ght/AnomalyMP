"""Rare deterministic stash visits moving existing items, never rerolling loot."""
import hashlib
import json

from .economy import DEPOSIT_CATEGORIES, integer
from .offline import distance
from .store import Conflict, Invalid, canonical, finite, persistent_id, positive


class Scavenging:
    def __init__(self, world, offline, catalog, rules=None):
        self.world, self.store, self.offline, self.catalog = world, world.store, offline, catalog
        rules = {} if rules is None else rules
        if not isinstance(rules, dict):
            raise Invalid("invalid scavenging rules")
        self.rules = {
            "minimum_interval_ms": integer(rules.get("minimum_interval_ms", 21_600_000), 60_000, 604_800_000, "stash visit interval"),
            "chance_bp": integer(rules.get("chance_bp", 800), 0, 10000, "stash visit chance"),
            "radius": finite(rules.get("radius", 10), .1, 30)}
        offline.scheduler.handlers["StashVisited"] = self.visited

    def participants(self, tx, npc_id, stash_id):
        npc, stash = (self.offline.require_offline(tx, value) for value in (npc_id,stash_id))
        if npc["kind"] != "NPC" or not npc["alive"] or stash["kind"] != "STASH" or not stash["alive"] or npc["location"] != stash["location"]:
            raise Conflict("stash visit requires a living offline stalker in the same location")
        policy = tx.execute("SELECT * FROM container WHERE id=?", (stash_id,)).fetchone()
        if not policy or (policy["policy"] != "NPC_ACCESSIBLE" and
                          not (policy["policy"] == "FACTION" and policy["owner"] == json.loads(npc["state"]).get("faction"))):
            raise Conflict("stash is protected from NPC scavenging")
        return npc,stash,policy

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
        def apply(tx):
            npc,stash,policy = self.participants(tx,npc_id,stash_id)
            if (npc["version"],stash["version"]) != (npc_version,stash_version) or due_ms < self.world.now():
                raise Conflict("visit version/time changed")
            last = json.loads(stash["state"]).get("last_npc_visit_ms")
            if last is not None and due_ms-last < self.rules["minimum_interval_ms"]:
                raise Conflict("stash was visited too recently")
            plan = {**payload,"rules":self.rules,"container_version":policy["version"],"location":npc["location"]}
            self.offline.scheduler.schedule_in(tx,event_id,due_ms,"entity:"+stash_id,stash_version,"StashVisited",plan)
            self.store.event(tx,"entity:"+stash_id,"StashVisitPlanned",payload,self.world.now())
            return {"event_id":event_id,"due_ms":due_ms}
        return self.store.command(actor,command_id,payload,apply)

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
        rules,at = plan["rules"],event["due_world_ms"]
        stash_state,npc_state = (json.loads(row["state"]) for row in (stash,npc))
        last = stash_state.get("last_npc_visit_ms")
        if last is not None and at-last < rules["minimum_interval_ms"]:
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
            take = tx.execute("SELECT * FROM item WHERE kind='STASH' AND holder=? ORDER BY id LIMIT 64", (stash["id"],)).fetchall()
            deposit = [row for row in tx.execute("SELECT * FROM item WHERE kind='NPC' AND holder=? ORDER BY id LIMIT 64", (npc["id"],))
                       if row["section"] in self.catalog.entries and self.catalog.entry(row["section"])["category"] in DEPOSIT_CATEGORIES]
            # The trusted catalog excludes armor/all weapons/artifacts from
            # deposits; individual carried items are moved with the same IDs.
            options = []
            capacity = integer(npc_state.get("carry_capacity_g",50000),0,1_000_000,"NPC carry capacity")
            carried_weight = self.catalog.carry_weight(tx,npc["id"]) if take else 0
            for row in take:
                if row["section"] not in self.catalog.entries:
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
