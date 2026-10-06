"""Independent quest state with stable entity links and atomic rewards."""
import hashlib
import json

from .ownership import Ownership
from .scheduler import Scheduler
from .store import Conflict, Invalid, canonical, identifier, persistent_id, positive


class Quests:
    def __init__(self, world, definitions, scheduler=None):
        if not isinstance(definitions, dict):
            raise Invalid("quest definitions must be a server configuration object")
        self.world, self.store = world, world.store
        self.ownership = Ownership(world)
        self.scheduler = scheduler or Scheduler(world)
        if self.scheduler.world is not world:
            raise Conflict("quest scheduler belongs to another world authority")
        self.definitions = json.loads(canonical(definitions))
        for quest_id, definition in self.definitions.items():
            identifier(quest_id)
            if not isinstance(definition, dict) or not isinstance(definition.get("steps"), list) or not 1 <= len(definition["steps"]) <= 64:
                raise Invalid("quest needs a bounded list of steps")
            for step in definition["steps"]:
                identifier(step["type"])
                persistent_id(step["target"])
                if type(step.get("count", 1)) is not int or not 1 <= step.get("count", 1) <= 10000:
                    raise Invalid("invalid quest step count")
            for requirement in definition.get("requirements", []):
                persistent_id(requirement["entity_id"])
                if requirement.get("policy", "FAIL") != "FAIL" or type(requirement.get("alive_required", True)) is not bool:
                    raise Invalid("unsupported quest entity death policy")
            reward = definition.get("reward", {})
            if type(reward.get("money", 0)) is not int or not 0 <= reward.get("money", 0) <= 1_000_000_000:
                raise Invalid("invalid quest money reward")
            items = reward.get("items", [])
            if not isinstance(items, list) or len(items) > 64:
                raise Invalid("invalid quest item rewards")
            for item in items:
                identifier(item["section"])
                if type(item.get("quantity", 1)) is not int or not 1 <= item.get("quantity", 1) <= 1000000:
                    raise Invalid("invalid quest item quantity")
                if not isinstance(item.get("state", {}), dict):
                    raise Invalid("invalid quest reward item state")
        self.scheduler.handlers["QuestDeathConsequences"] = self.death_consequences
        world.quest_death_queue = self.queue_death
        with self.store.transaction() as tx:
            self.reconcile_in(tx)

    @staticmethod
    def death_job_id(death_id, batch):
        return hashlib.sha256(f"quest-death:{death_id}:{batch}".encode("ascii")).hexdigest()[:32]

    def queue_death(self, tx, entity_id, sequence, occurred_ms):
        # Scheduling one durable job shares the death transaction; applying
        # possibly many quest failures is deferred into bounded atomic batches.
        required = tx.execute("SELECT 1 FROM quest_requirement r JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id "
                              "WHERE r.entity_id=? AND r.alive_required=1 AND r.policy='FAIL' "
                              "AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE') NOT IN ('FAILED','COMPLETED') LIMIT 1",(entity_id,)).fetchone()
        if not required:
            return False
        source = tx.execute("SELECT * FROM world_event WHERE sequence=?",(sequence,)).fetchone()
        if not source or source["aggregate_id"]!="entity:"+entity_id or source["type"] not in ("EntityDied","GroupLostAllMembers"):
            raise Conflict("quest failure requires committed death evidence")
        event_id = self.death_job_id(source["id"],0)
        payload = {"entity_id":entity_id,"death_id":source["id"],"death_sequence":sequence,"batch":0}
        existing = tx.execute("SELECT 1 FROM scheduled_event WHERE id=?",(event_id,)).fetchone()
        self.scheduler.schedule_in(tx,event_id,occurred_ms,"entity:"+entity_id,sequence,"QuestDeathConsequences",payload)
        return existing is None

    def death_consequences(self, tx, event):
        payload = json.loads(event["payload"])
        entity_id,sequence = payload["entity_id"],payload["death_sequence"]
        source = tx.execute("SELECT * FROM world_event WHERE sequence=? AND id=?",(sequence,payload["death_id"])).fetchone()
        entity = tx.execute("SELECT alive FROM entity WHERE id=?",(entity_id,)).fetchone()
        if (not source or source["aggregate_id"]!="entity:"+entity_id or source["type"] not in ("EntityDied","GroupLostAllMembers")
                or not entity or entity[0]):
            return {"reason":"death evidence/registry changed"},False
        rows = tx.execute("SELECT q.* FROM quest_requirement r JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id "
                          "WHERE r.entity_id=? AND r.alive_required=1 AND r.policy='FAIL' "
                          "AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE') NOT IN ('FAILED','COMPLETED') "
                          "ORDER BY q.character_id,q.id LIMIT 65",(entity_id,)).fetchall()
        failed = []
        for row in rows[:64]:
            state = json.loads(row["state"])
            state.update(status="FAILED",failure_entity=entity_id,failure_event=source["id"],failed_world_ms=source["world_ms"])
            tx.execute("UPDATE quest SET state=?,version=version+1 WHERE character_id=? AND id=?",
                       (canonical(state),row["character_id"],row["id"]))
            data = {"character_id":row["character_id"],"quest_id":row["id"],"entity_id":entity_id,"death_id":source["id"]}
            self.store.event(tx,"quest:"+row["character_id"]+":"+row["id"],"QuestFailed",data,source["world_ms"],committed_ms=self.world.now())
            failed.append({"character_id":row["character_id"],"quest_id":row["id"]})
        more = len(rows)>64
        if more:
            next_payload = {**payload,"batch":payload["batch"]+1}
            self.scheduler.schedule_in(tx,self.death_job_id(source["id"],next_payload["batch"]),source["world_ms"],
                                       "entity:"+entity_id,sequence,"QuestDeathConsequences",next_payload)
        return {"failed":failed,"more":more,"death_id":source["id"]},True

    def reconcile_in(self, tx, after_entity=None):
        # Compatibility recovery for deaths committed before this subscriber
        # existed. Missing evidence is held; no fabricated death or respawn.
        rows = tx.execute("SELECT DISTINCT r.entity_id FROM quest_requirement r JOIN entity e ON e.id=r.entity_id "
                          "JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id WHERE e.alive=0 "
                          "AND r.alive_required=1 AND r.policy='FAIL' AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE') "
                          "NOT IN ('FAILED','COMPLETED') AND r.entity_id>? ORDER BY r.entity_id LIMIT 65",(after_entity or "",)).fetchall()
        scheduled,unproven = 0,[]
        for row in rows[:64]:
            source = tx.execute("SELECT sequence,world_ms FROM world_event WHERE aggregate_id=? AND type IN ('EntityDied','GroupLostAllMembers') "
                                "ORDER BY sequence DESC LIMIT 1",("entity:"+row[0],)).fetchone()
            if source:
                scheduled += self.queue_death(tx,row[0],source["sequence"],source["world_ms"])
            else:
                unproven.append(row[0])
        return {"scheduled":scheduled,"examined":min(64,len(rows)),"unproven":unproven,
                "next_after":rows[63][0] if len(rows)>64 else None}

    def reconcile(self, actor, command_id, after_entity=None):
        if after_entity is not None:
            persistent_id(after_entity)
        return self.store.command(actor,command_id,{"type":"quest_reconcile","after_entity":after_entity},
                                  lambda tx:self.reconcile_in(tx,after_entity))

    def grant(self, actor, command_id, character_id, fence, quest_id):
        identifier(quest_id)
        if quest_id not in self.definitions:
            raise Invalid("unknown server quest definition")
        payload = {"type": "quest_grant", "character_id": character_id, "fence": fence, "quest_id": quest_id}
        def apply(tx):
            character = self.ownership.require_entity(tx, actor, character_id, fence, alive=True)
            if character["kind"] != "CHARACTER":
                raise Conflict("quest recipient is not a character")
            old = tx.execute("SELECT * FROM quest WHERE character_id=? AND id=?", (character_id, quest_id)).fetchone()
            if old:
                return self.public(old)
            definition = self.definitions[quest_id]
            state = {"status": "ACTIVE", "step_count": 0, "definition": definition}
            requirements = definition.get("requirements", [])
            for requirement in requirements:
                target = tx.execute("SELECT alive FROM entity WHERE id=?", (requirement["entity_id"],)).fetchone()
                if target is None:
                    raise Conflict("quest entity is absent from the unique registry")
                if requirement.get("alive_required", True) and not target[0]:
                    state["status"] = "FAILED"
            tx.execute("INSERT INTO quest VALUES(?,?,0,1,?,0)", (character_id, quest_id, canonical(state)))
            for requirement in requirements:
                tx.execute("INSERT INTO quest_requirement VALUES(?,?,?,?,?)",
                           (character_id, quest_id, requirement["entity_id"],
                            int(requirement.get("alive_required", True)), requirement.get("policy", "FAIL")))
            self.store.event(tx, "quest:" + character_id + ":" + quest_id, "QuestGranted", payload, self.world.now())
            return self.public(tx.execute("SELECT * FROM quest WHERE character_id=? AND id=?", (character_id, quest_id)).fetchone())
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx:self.ownership.authorize_entity(tx,actor,character_id,fence))

    def progress(self, actor, command_id, character_id, fence, quest_id, version, event_sequence):
        positive(version)
        positive(event_sequence, "event sequence")
        identifier(quest_id)
        payload = {"type": "quest_progress", "character_id": character_id, "fence": fence,
                   "quest_id": quest_id, "version": version, "event_sequence": event_sequence}
        def apply(tx):
            character = self.ownership.require_entity(tx, actor, character_id, fence, alive=True)
            if character["kind"] != "CHARACTER":
                raise Conflict("quest recipient is not a character")
            row = tx.execute("SELECT * FROM quest WHERE character_id=? AND id=?", (character_id, quest_id)).fetchone()
            if not row:
                raise Invalid("quest was not granted")
            if tx.execute("SELECT 1 FROM quest_event WHERE character_id=? AND quest_id=? AND event_sequence=?",
                          (character_id, quest_id, event_sequence)).fetchone():
                return self.public(row)
            if row["version"] != version:
                raise Conflict("quest version changed")
            state = json.loads(row["state"])
            if state["status"] != "ACTIVE":
                return self.public(row)
            requirements = tx.execute("SELECT e.alive FROM quest_requirement r JOIN entity e ON e.id=r.entity_id WHERE r.character_id=? AND r.quest_id=? AND r.alive_required=1",
                                      (character_id, quest_id)).fetchall()
            if any(not value[0] for value in requirements):
                state["status"] = "FAILED"
                tx.execute("UPDATE quest SET state=?,version=version+1 WHERE character_id=? AND id=?", (canonical(state), character_id, quest_id))
                self.store.event(tx, "quest:" + character_id + ":" + quest_id, "QuestFailed", payload, self.world.now())
                return self.public(tx.execute("SELECT * FROM quest WHERE character_id=? AND id=?", (character_id, quest_id)).fetchone())
            event = tx.execute("SELECT * FROM world_event WHERE sequence=?", (event_sequence,)).fetchone()
            step = state["definition"]["steps"][row["stage"]]
            if not event or event["type"] != step["type"] or event["aggregate_id"] != "entity:" + step["target"]:
                raise Conflict("committed event does not satisfy this objective")
            tx.execute("INSERT INTO quest_event VALUES(?,?,?)", (character_id, quest_id, event_sequence))
            state["step_count"] += 1
            stage, rewarded = row["stage"], row["rewarded"]
            if state["step_count"] >= step.get("count", 1):
                stage += 1
                state["step_count"] = 0
            if stage == len(state["definition"]["steps"]):
                state["status"] = "COMPLETED"
                self.reward(tx, character, quest_id, state["definition"].get("reward", {}))
                rewarded = 1
            tx.execute("UPDATE quest SET stage=?,version=version+1,state=?,rewarded=? WHERE character_id=? AND id=?",
                       (stage, canonical(state), rewarded, character_id, quest_id))
            self.store.event(tx, "quest:" + character_id + ":" + quest_id, "QuestProgressed", payload, self.world.now())
            return self.public(tx.execute("SELECT * FROM quest WHERE character_id=? AND id=?", (character_id, quest_id)).fetchone())
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx:self.ownership.authorize_entity(tx,actor,character_id,fence))

    def reward(self, tx, character, quest_id, reward):
        state = json.loads(character["state"])
        money = state.get("money", 0)
        if type(money) is not int or not 0 <= money < 2**63 - 1 - reward.get("money", 0):
            raise Conflict("character wallet is invalid or exhausted")
        state["money"] = money + reward.get("money", 0)
        encoded = canonical(state)
        tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (encoded, character["id"]))
        tx.execute("UPDATE character SET state=? WHERE id=?", (encoded, character["id"]))
        for index, item in enumerate(reward.get("items", [])):
            item_id = hashlib.sha256(f"quest-reward:{character['id']}:{quest_id}:{index}".encode("utf-8")).hexdigest()[:32]
            tx.execute("INSERT INTO item VALUES(?,?,'PLAYER',?,?,1,?)",
                       (item_id, item["section"], character["id"], item.get("quantity", 1), canonical(item.get("state", {}))))

    @staticmethod
    def public(row):
        state = json.loads(row["state"])
        return {"quest_id": row["id"], "character_id": row["character_id"], "stage": row["stage"],
                "version": row["version"], "status": state["status"], "rewarded": bool(row["rewarded"])}

    def requirements(self, actor, character_id, fence):
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            self.ownership.require_entity(self.store.db, actor, character_id, fence, alive=True)
            rows = self.store.db.execute("SELECT r.*,e.location,e.alive,e.version AS entity_version FROM quest_requirement r JOIN entity e ON e.id=r.entity_id WHERE r.character_id=? ORDER BY quest_id,entity_id", (character_id,)).fetchall()
            return [dict(row) for row in rows]

    def location_requirements(self, actor, location, fence, *, after=None, epoch=None, revision=None):
        """Bounded current references for a location, never a spawn permission.

        Continuations belong to one authority epoch/journal revision. Any
        committed change requires a fresh scan, rather than silently mixing
        requirements before/after a migration, failure or new quest grant.
        """
        identifier(location)
        positive(fence, "location fence")
        if after is not None:
            if not isinstance(after, list) or len(after) != 3:
                raise Invalid("invalid quest requirement cursor")
            persistent_id(after[0]); identifier(after[1]); persistent_id(after[2])
            if epoch is None or revision is None:
                raise Invalid("quest requirement continuation needs a snapshot cut")
        if (epoch is None) != (revision is None):
            raise Invalid("quest requirement cut needs both epoch and revision")
        if epoch is not None:
            positive(epoch, "authority epoch"); positive(revision, "world revision")
        def project(tx):
            cut = tx.execute("SELECT epoch,revision FROM world WHERE singleton=1").fetchone()
            if epoch is not None and (epoch, revision) != (cut["epoch"], cut["revision"]):
                raise Conflict("quest requirement snapshot changed; restart the scan")
            rows = tx.execute(
                "SELECT r.*,q.version AS quest_version,e.location,e.alive,e.version AS entity_version,e.writer,e.fence "
                "FROM quest_requirement r JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id "
                "JOIN entity e ON e.id=r.entity_id WHERE e.location=? "
                "AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE')='ACTIVE' "
                "AND (r.character_id,r.quest_id,r.entity_id)>(?,?,?) "
                "ORDER BY r.character_id,r.quest_id,r.entity_id LIMIT 65",
                (location, *(after or ["", "", ""]))).fetchall()
            page = [dict(row) for row in rows[:64]]
            cursor = [page[-1][key] for key in ("character_id", "quest_id", "entity_id")] if len(rows)>64 else None
            return {"schema":1,"location":location,"epoch":cut["epoch"],"revision":cut["revision"],
                    "world_ms":self.world.now(),"requirements":page,"next_after":cursor}
        with self.store.transaction() as tx:
            self.store.require_epoch(tx)
            self.world.require_location(tx, actor, location, fence)
            return self.world.mutation(project)(tx)
