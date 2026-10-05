"""Independent quest state with stable entity links and atomic rewards."""
import hashlib
import json

from .ownership import Ownership
from .store import Conflict, Invalid, canonical, identifier, persistent_id, positive


class Quests:
    def __init__(self, world, definitions):
        if not isinstance(definitions, dict):
            raise Invalid("quest definitions must be a server configuration object")
        self.world, self.store = world, world.store
        self.ownership = Ownership(world)
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
        return self.store.command(actor, command_id, payload, apply)

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
        return self.store.command(actor, command_id, payload, apply)

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
