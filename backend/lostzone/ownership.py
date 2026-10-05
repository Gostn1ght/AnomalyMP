"""Persistent entity registry and one-row item containment ledger.

Runtime callers are trusted location servers, not player clients. Runtime
distance/combat checks remain mandatory in the engine adapter.
"""
import json
import uuid

from .store import Conflict, Invalid, canonical, identifier, persistent_id, positive

ENTITY_KINDS = frozenset(("CHARACTER", "NPC", "MUTANT", "GROUP", "STASH", "CONTAINER",
                         "CORPSE", "ANOMALY", "ARTIFACT", "DOOR", "TRAP", "TRADER",
                         "CAMPFIRE", "OBJECT", "NEST"))
ITEM_KINDS = frozenset(("WORLD", "PLAYER", "NPC", "CORPSE", "STASH", "CONTAINER", "TRADE"))
POLICIES = frozenset(("PUBLIC", "PLAYER_ONLY", "QUEST_PROTECTED", "NPC_ACCESSIBLE", "FACTION"))


class Ownership:
    def __init__(self, world):
        self.world, self.store = world, world.store

    def create_entity(self, actor, command_id, entity_id, kind, location, fence, state,
                      account=None, policy=None, owner=None, capacity=64):
        persistent_id(entity_id)
        positive(fence, "fence")
        identifier(location)
        if kind not in ENTITY_KINDS or not isinstance(state, dict):
            raise Invalid("invalid entity kind/state")
        if kind == "CHARACTER":
            identifier(account)
        if kind in ("STASH", "CONTAINER"):
            if policy not in POLICIES or type(capacity) is not int or not 0 <= capacity <= 10000:
                raise Invalid("invalid container policy/capacity")
            identifier(owner or "public")
        encoded = canonical(state)
        payload = {"type": "entity_create", "id": entity_id, "kind": kind, "location": location,
                   "fence": fence, "state": state, "account": account, "policy": policy,
                   "owner": owner, "capacity": capacity}
        def apply(tx):
            self.world.require_location(tx, actor, location, fence)
            if tx.execute("SELECT 1 FROM entity WHERE id=?", (entity_id,)).fetchone():
                raise Conflict("entity ID already exists; hydration cannot create a new copy")
            if kind == "CHARACTER":
                self.admission(tx, location, account)
            tx.execute("INSERT INTO entity VALUES(?,?,?,?,?,1,1,?)",
                       (entity_id, kind, location, actor, fence, encoded))
            if kind == "GROUP":
                members = state.get("member_ids")
                if not isinstance(members, list) or not 1 <= len(members) <= 512:
                    raise Invalid("group requires persistent member IDs")
                if len(set(members)) != len(members):
                    raise Invalid("duplicate group members")
                for member in members:
                    row = self.require_entity(tx, actor, member, fence)
                    if row["kind"] not in ("NPC", "MUTANT") or row["location"] != location:
                        raise Conflict("group member is outside this authority")
                    if tx.execute("SELECT 1 FROM group_member WHERE member_id=?", (member,)).fetchone():
                        raise Conflict("individual already belongs to a persistent group")
                    tx.execute("INSERT INTO group_member VALUES(?,?)", (entity_id, member))
            if kind == "CHARACTER":
                tx.execute("INSERT INTO character VALUES(?,?,1,?)", (entity_id, account, encoded))
                tx.execute("INSERT INTO player_session VALUES(?,?,?,1,'ACTIVE')", (entity_id, account, actor))
            if kind in ("STASH", "CONTAINER"):
                tx.execute("INSERT INTO container VALUES(?,?,?,?,1,?)",
                           (entity_id, policy, owner or "public", capacity, encoded))
            event = self.store.event(tx, "entity:" + entity_id, "EntityCreated", payload, self.world.now())
            return {"id": entity_id, "version": 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def admission(self, tx, location, account=None, excluding=None):
        row = tx.execute("SELECT capacity FROM location_lease WHERE location=?", (location,)).fetchone()
        if not row:
            raise Conflict("target location has no authority")
        # Active and prepared/claimed reservations share the same capacity.
        # A transfer never adds a second global character.
        target = tx.execute("SELECT COUNT(*) FROM entity e JOIN player_session s ON s.character_id=e.id WHERE e.location=? AND e.id!=? AND e.alive=1 AND s.state='ACTIVE'",
                            (location, excluding or "")).fetchone()[0]
        reserved = tx.execute("SELECT COUNT(*) FROM transfer t JOIN entity e ON e.id=t.entity_id WHERE t.target=? AND t.state IN ('PREPARED','CLAIMED') AND e.kind='CHARACTER' AND e.id!=?",
                              (location, excluding or "")).fetchone()[0]
        if target + reserved >= row[0]:
            raise Conflict("target location is full")
        if account is not None:
            active = tx.execute("SELECT COUNT(*) FROM player_session WHERE state IN('ACTIVE','FROZEN')").fetchone()[0]
            if active >= 512:
                raise Conflict("world player limit reached")
            if tx.execute("SELECT 1 FROM player_session WHERE account=? AND state IN('ACTIVE','FROZEN')", (account,)).fetchone():
                raise Conflict("account already owns an active character")

    def require_entity(self, tx, actor, entity_id, fence, version=None, alive=False):
        persistent_id(entity_id)
        positive(fence, "fence")
        row = tx.execute("SELECT * FROM entity WHERE id=?", (entity_id,)).fetchone()
        if not row or row["writer"] != actor or row["fence"] != fence:
            raise Conflict("entity writer/fence mismatch")
        self.world.require_location(tx, actor, row["location"], fence)
        if version is not None and row["version"] != positive(version):
            raise Conflict("entity version changed")
        if alive and not row["alive"]:
            raise Conflict("entity is permanently dead")
        if alive and row["kind"] == "CHARACTER":
            session = tx.execute("SELECT * FROM player_session WHERE character_id=?", (entity_id,)).fetchone()
            if not session or session["state"] != "ACTIVE" or session["owner"] != actor:
                raise Conflict("character session is not active under this owner")
        return row

    def update_entity(self, actor, command_id, entity_id, fence, version, state):
        if not isinstance(state, dict):
            raise Invalid("entity state must be an object")
        encoded = canonical(state)
        payload = {"type": "entity_update", "id": entity_id, "fence": fence,
                   "version": version, "state": state}
        def apply(tx):
            row = self.require_entity(tx, actor, entity_id, fence, version, alive=True)
            if row["kind"] == "GROUP" and state.get("member_ids") != json.loads(row["state"]).get("member_ids"):
                raise Conflict("group membership cannot be rewritten through a state update")
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (encoded, entity_id))
            if row["kind"] == "CHARACTER":
                tx.execute("UPDATE character SET state=? WHERE id=?", (encoded, entity_id))
            event = self.store.event(tx, "entity:" + entity_id, "EntityStateChanged", payload, self.world.now())
            return {"id": entity_id, "version": version + 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def disconnect(self, actor, command_id, character_id, fence, version, state):
        if not isinstance(state, dict):
            raise Invalid("character checkpoint must be an object")
        encoded = canonical(state)
        payload = {"type": "session_disconnect", "character_id": character_id,
                   "fence": fence, "version": version, "state": state}
        def apply(tx):
            row = self.require_entity(tx, actor, character_id, fence, version, alive=True)
            if row["kind"] != "CHARACTER":
                raise Conflict("entity has no player session")
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (encoded, character_id))
            tx.execute("UPDATE character SET state=?,session_fence=session_fence+1 WHERE id=?", (encoded, character_id))
            tx.execute("UPDATE player_session SET state='DISCONNECTED',fence=fence+1 WHERE character_id=?", (character_id,))
            event = self.store.event(tx, "entity:" + character_id, "SessionDisconnected", payload, self.world.now())
            return {"id": character_id, "version": version + 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def resume(self, actor, command_id, character_id, location, fence, version):
        persistent_id(character_id)
        identifier(location)
        positive(fence, "fence")
        positive(version)
        payload = {"type": "session_resume", "character_id": character_id,
                   "location": location, "fence": fence, "version": version}
        def apply(tx):
            row = self.require_entity(tx, actor, character_id, fence, version)
            if row["kind"] != "CHARACTER" or not row["alive"] or row["location"] != location:
                raise Conflict("character cannot resume in this location")
            session = tx.execute("SELECT * FROM player_session WHERE character_id=?", (character_id,)).fetchone()
            if not session or session["state"] != "DISCONNECTED":
                raise Conflict("character already has an active/frozen session")
            self.admission(tx, location, session["account"])
            tx.execute("UPDATE player_session SET state='ACTIVE',owner=?,fence=fence+1 WHERE character_id=?", (actor, character_id))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id=?", (character_id,))
            tx.execute("UPDATE entity SET version=version+1 WHERE id=?", (character_id,))
            event = self.store.event(tx, "entity:" + character_id, "SessionResumed", payload, self.world.now())
            session_fence = tx.execute("SELECT fence FROM player_session WHERE character_id=?", (character_id,)).fetchone()[0]
            return {"id": character_id, "version": version + 1, "session_fence": session_fence,
                    "state": json.loads(row["state"]), "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def recover_location(self, actor, command_id, location, fence):
        # A newly fenced owner adopts existing records; it does not reroll
        # inventories, resurrect dead members, or claim transit entities.
        payload = {"type": "location_recover", "location": location, "fence": fence}
        def apply(tx):
            self.world.require_location(tx, actor, location, fence)
            tx.execute("UPDATE entity SET writer=?,fence=?,version=version+1 WHERE location=? AND writer NOT LIKE 'transfer:%' AND writer NOT LIKE 'offline:%'",
                       (actor, fence, location))
            rows = tx.execute("SELECT id,version,alive FROM entity WHERE location=? AND writer=? AND fence=?",
                              (location, actor, fence)).fetchall()
            tx.execute("UPDATE player_session SET owner=?,fence=fence+1 WHERE state='ACTIVE' AND character_id IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?)",
                       (actor, location, actor, fence))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?)",
                       (location, actor, fence))
            event = self.store.event(tx, "location:" + location, "LocationRecovered",
                                     {**payload, "entities": [dict(row) for row in rows]}, self.world.now())
            return {"entities": [dict(row) for row in rows], "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def endpoint(self, tx, actor, location, fence, kind, holder, requester=None):
        if kind not in ITEM_KINDS:
            raise Invalid("unsupported containment kind")
        if kind == "WORLD":
            if holder != location:
                raise Conflict("world item belongs to another location")
            return
        row = self.require_entity(tx, actor, holder, fence)
        if row["location"] != location:
            raise Conflict("item endpoint belongs to another location")
        expected = {"PLAYER": ("CHARACTER",), "NPC": ("NPC", "MUTANT"),
                    "CORPSE": ("NPC", "MUTANT", "CHARACTER", "CORPSE"),
                    "STASH": ("STASH",), "CONTAINER": ("CONTAINER",), "TRADE": ("TRADER",)}
        if row["kind"] not in expected[kind] or (kind == "CORPSE" and row["alive"]):
            raise Conflict("containment kind does not match holder")
        if kind in ("PLAYER", "NPC") and not row["alive"]:
            raise Conflict("living inventory holder is dead")
        box = tx.execute("SELECT * FROM container WHERE id=?", (holder,)).fetchone()
        if box and requester is not None:
            req = self.require_entity(tx, actor, requester, fence, alive=True)
            if req["location"] != location:
                raise Conflict("requester belongs to another location")
            if box["policy"] in ("PLAYER_ONLY", "QUEST_PROTECTED"):
                if req["kind"] != "CHARACTER" or requester != box["owner"]:
                    raise Conflict("container is protected from this requester")
            elif box["policy"] == "FACTION":
                if json.loads(req["state"]).get("faction") != box["owner"]:
                    raise Conflict("container faction restriction")

    def create_item(self, actor, command_id, item_id, section, location, fence,
                    kind="WORLD", holder=None, quantity=1, state=None):
        persistent_id(item_id)
        identifier(section)
        identifier(location)
        positive(fence, "fence")
        if type(quantity) is not int or not 1 <= quantity <= 1000000:
            raise Invalid("invalid item quantity")
        if state is None:
            state = {}
        if not isinstance(state, dict):
            raise Invalid("item state must be an object")
        holder = holder or location
        encoded = canonical(state)
        payload = {"type": "item_create", "id": item_id, "section": section, "location": location,
                   "fence": fence, "kind": kind, "holder": holder, "quantity": quantity, "state": state}
        def apply(tx):
            self.world.require_location(tx, actor, location, fence)
            self.endpoint(tx, actor, location, fence, kind, holder)
            if tx.execute("SELECT 1 FROM item WHERE id=?", (item_id,)).fetchone():
                raise Conflict("item already exists")
            self.check_capacity(tx, kind, holder)
            tx.execute("INSERT INTO item VALUES(?,?,?,?,?,1,?)",
                       (item_id, section, kind, holder, quantity, encoded))
            event = self.store.event(tx, "item:" + item_id, "ItemCreated", payload, self.world.now())
            return {"id": item_id, "version": 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    @staticmethod
    def check_capacity(tx, kind, holder):
        box = tx.execute("SELECT capacity FROM container WHERE id=?", (holder,)).fetchone()
        if box:
            count = tx.execute("SELECT COUNT(*) FROM item WHERE kind=? AND holder=?", (kind, holder)).fetchone()[0]
            if count >= box[0]:
                raise Conflict("container has no free slots")

    def move_item(self, actor, command_id, item_id, location, fence, version,
                  source_kind, source_holder, target_kind, target_holder, requester):
        persistent_id(item_id)
        positive(version)
        persistent_id(requester)
        payload = {"type": "item_move", "id": item_id, "location": location, "fence": fence,
                   "version": version, "source_kind": source_kind, "source_holder": source_holder,
                   "target_kind": target_kind, "target_holder": target_holder, "requester": requester}
        def apply(tx):
            self.world.require_location(tx, actor, location, fence)
            req = self.require_entity(tx, actor, requester, fence, alive=True)
            if req["location"] != location:
                raise Conflict("requester belongs to another location")
            for kind, holder in ((source_kind, source_holder), (target_kind, target_holder)):
                self.endpoint(tx, actor, location, fence, kind, holder, requester)
                if kind in ("PLAYER", "NPC") and holder != requester:
                    raise Conflict("requester cannot mutate another living inventory")
            row = tx.execute("SELECT * FROM item WHERE id=?", (item_id,)).fetchone()
            if not row or (row["kind"], row["holder"], row["version"]) != (source_kind, source_holder, version):
                raise Conflict("item ownership/version changed")
            if (source_kind, source_holder) == (target_kind, target_holder):
                raise Invalid("source and destination are identical")
            self.check_capacity(tx, target_kind, target_holder)
            tx.execute("UPDATE item SET kind=?,holder=?,version=version+1 WHERE id=?",
                       (target_kind, target_holder, item_id))
            tx.execute("UPDATE container SET version=version+1 WHERE id IN (?,?)",
                       (source_holder, target_holder))
            event = self.store.event(tx, "item:" + item_id, "ItemMoved", payload, self.world.now())
            return {"id": item_id, "version": version + 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def kill(self, actor, command_id, entity_id, fence, version, cause):
        identifier(cause)
        payload = {"type": "entity_death", "id": entity_id, "fence": fence,
                   "version": version, "cause": cause}
        def apply(tx):
            row = self.require_entity(tx, actor, entity_id, fence, version, alive=True)
            state = json.loads(row["state"])
            state.update(death_time=self.world.now(), cause=cause, corpse_removed=False)
            tx.execute("UPDATE entity SET alive=0,state=?,version=version+1 WHERE id=?",
                       (canonical(state), entity_id))
            tx.execute("UPDATE item SET kind='CORPSE',version=version+1 WHERE holder=? AND kind IN ('PLAYER','NPC')",
                       (entity_id,))
            tx.execute("UPDATE player_session SET state='DISCONNECTED',fence=fence+1 WHERE character_id=?", (entity_id,))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id=?", (entity_id,))
            event = self.store.event(tx, "entity:" + entity_id, "EntityDied", payload, self.world.now())
            return {"id": entity_id, "version": version + 1, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def cleanup_corpse(self, actor, command_id, entity_id, fence, version):
        payload = {"type": "corpse_cleanup", "id": entity_id, "fence": fence, "version": version}
        def apply(tx):
            row = self.require_entity(tx, actor, entity_id, fence, version)
            if row["alive"]:
                raise Conflict("living entity cannot be cleaned up")
            if tx.execute("SELECT 1 FROM quest_requirement r JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id WHERE r.entity_id=? AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE') NOT IN ('FAILED','COMPLETED')", (entity_id,)).fetchone():
                raise Conflict("corpse is still required by an active quest")
            state = json.loads(row["state"])
            state["corpse_removed"] = True
            items = tx.execute("SELECT id FROM item WHERE kind='CORPSE' AND holder=?", (entity_id,)).fetchall()
            # A tombstone remains. Gameplay items have no expiry or cleanup
            # path here; this operation changes containment, never item IDs.
            for item in tx.execute("SELECT * FROM item WHERE kind='CORPSE' AND holder=?", (entity_id,)).fetchall():
                item_state = json.loads(item["state"])
                item_state.update(drop_position=state.get("position"), dropped_from_corpse=entity_id)
                tx.execute("UPDATE item SET kind='WORLD',holder=?,state=?,version=version+1 WHERE id=?",
                           (row["location"], canonical(item_state), item["id"]))
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (canonical(state), entity_id))
            event = self.store.event(tx, "entity:" + entity_id, "CorpseRemoved",
                                     {**payload, "items": [item[0] for item in items]}, self.world.now())
            return {"id": entity_id, "version": version + 1, "items": [item[0] for item in items], "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def location_state(self, actor, location, fence):
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            self.world.require_location(self.store.db, actor, location, fence)
            entities = self.store.db.execute("SELECT * FROM entity WHERE location=? AND writer=? AND fence=? ORDER BY id",
                                             (location, actor, fence)).fetchall()
            # Inventory projection is derived from the single ledger. There
            # is no second authoritative inventory embedded in entity JSON.
            items = self.store.db.execute("SELECT * FROM item WHERE (kind='WORLD' AND holder=?) OR holder IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?) ORDER BY id",
                                          (location, location, actor, fence)).fetchall()
            return {"entities": [dict(row, state=json.loads(row["state"])) for row in entities],
                    "items": [dict(row, state=json.loads(row["state"])) for row in items]}
