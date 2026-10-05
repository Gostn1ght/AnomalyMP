"""Durable cross-location handoff for characters, NPCs and whole groups.

Prepare freezes one authoritative record before returning a signed token.
Claim reserves the destination; commit alone grants its writer ownership.
The engine adapter must hide target actors until commit and retire source
shells under the old fence. Tokens do not carry a client-editable save.
"""
import base64
import hashlib
import hmac
import json
import secrets
import uuid

from .store import Conflict, Invalid, canonical, identifier, persistent_id, positive
from .ownership import Ownership


class Transfers:
    def __init__(self, world, signing_key):
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise Invalid("transfer signing key must contain at least 32 bytes")
        self.world, self.store = world, world.store
        self.ownership = Ownership(world)
        self.key = signing_key

    def sign(self, claims):
        encoded = base64.urlsafe_b64encode(canonical(claims).encode("utf-8")).rstrip(b"=")
        signature = hmac.new(self.key, encoded, hashlib.sha256).hexdigest()
        return encoded.decode("ascii") + "." + signature

    def verify(self, token):
        if not isinstance(token, str) or len(token) > 2048:
            raise Invalid("invalid transfer token")
        try:
            encoded, signature = token.split(".")
            expected = hmac.new(self.key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise Invalid("invalid transfer signature")
            claims = json.loads(base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True))
            if not isinstance(claims, dict) or claims.get("world_id") != self.world.world_id or claims.get("audience") != "lostzone-transfer-v1":
                raise Invalid("transfer token belongs to another world/audience")
            persistent_id(claims["transfer_id"])
            persistent_id(claims["entity_id"])
            identifier(claims["target"])
            positive(claims["expires_ms"], "token expiry")
            return claims
        except (ValueError, KeyError, UnicodeError) as error:
            raise Invalid("invalid transfer token") from error

    def prepare(self, actor, command_id, entity_id, source, source_fence, target,
                entity_version, ttl_ms=60000):
        persistent_id(entity_id)
        identifier(source)
        identifier(target)
        positive(source_fence, "source fence")
        positive(entity_version)
        if source == target or type(ttl_ms) is not int or not 1000 <= ttl_ms <= 300000:
            raise Invalid("invalid transfer destination/duration")
        payload = {"type": "transfer_prepare", "entity_id": entity_id, "source": source,
                   "source_fence": source_fence, "target": target,
                   "entity_version": entity_version, "ttl_ms": ttl_ms}
        def apply(tx):
            root = self.ownership.require_entity(tx, actor, entity_id, source_fence, entity_version, alive=True)
            if root["location"] != source or root["kind"] not in ("CHARACTER", "NPC", "MUTANT", "GROUP"):
                raise Conflict("entity cannot depart this source")
            target_lease = tx.execute("SELECT * FROM location_lease WHERE location=?", (target,)).fetchone()
            if not target_lease or target_lease["expires_ms"] <= self.world.real_ms():
                raise Conflict("target authority is unavailable")
            if root["kind"] == "CHARACTER":
                session = tx.execute("SELECT * FROM player_session WHERE character_id=?", (entity_id,)).fetchone()
                if not session or session["state"] != "ACTIVE" or session["owner"] != actor:
                    raise Conflict("character has no active source session")
                self.ownership.admission(tx, target, excluding=entity_id)
            ids = [entity_id]
            if root["kind"] == "GROUP":
                members = json.loads(root["state"]).get("member_ids", [])
                if not isinstance(members, list) or len(members) > 512 or len(set(members)) != len(members):
                    raise Invalid("invalid persistent group membership")
                for member in members:
                    persistent_id(member)
                    row = tx.execute("SELECT * FROM entity WHERE id=?", (member,)).fetchone()
                    if not row or member == entity_id or row["kind"] not in ("NPC", "MUTANT"):
                        raise Conflict("invalid persistent group member")
                    # Casualty IDs remain in the roster, but a body stays
                    # where it died. It is never transported with a patrol.
                    if not row["alive"]:
                        continue
                    row = self.ownership.require_entity(tx, actor, member, source_fence)
                    if row["location"] != source:
                        raise Conflict("group member is not owned by source")
                    ids.append(member)
            entities = [dict(tx.execute("SELECT * FROM entity WHERE id=?", (value,)).fetchone()) for value in ids]
            items = [dict(row) for value in ids for row in tx.execute("SELECT * FROM item WHERE holder=? AND kind IN('PLAYER','NPC','CORPSE') ORDER BY id", (value,))]
            transfer_id = uuid.uuid4().hex
            expiry = self.world.real_ms() + ttl_ms
            claims = {"audience": "lostzone-transfer-v1", "world_id": self.world.world_id,
                      "transfer_id": transfer_id, "entity_id": entity_id,
                      "target": target, "expires_ms": expiry, "nonce": secrets.token_hex(16)}
            token = self.sign(claims)
            checkpoint = {"entities": entities, "items": items, "ids": ids}
            tx.execute("INSERT INTO transfer VALUES(?,?,?,?,?,?,NULL,NULL,'PREPARED',?,?,?,?,?)",
                       (transfer_id, entity_id, source, target, actor, source_fence, expiry,
                        hashlib.sha256(token.encode("ascii")).hexdigest(), canonical(checkpoint),
                        entity_version, self.store.epoch))
            for value in ids:
                tx.execute("UPDATE entity SET writer=?,version=version+1 WHERE id=?", ("transfer:" + transfer_id, value))
            tx.execute("UPDATE player_session SET owner=?,state='FROZEN',fence=fence+1 WHERE character_id=?",
                       ("transfer:" + transfer_id, entity_id))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id=?", (entity_id,))
            event = self.store.event(tx, "transfer:" + transfer_id, "TransferPrepared",
                                     {**payload, "id": transfer_id, "checkpoint_hash": hashlib.sha256(canonical(checkpoint).encode("utf-8")).hexdigest()}, self.world.now())
            return {"transfer_id": transfer_id, "state": "PREPARED", "token": token, "expires_ms": expiry, "event": event}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.world.require_location(tx, actor, source, source_fence))

    def claim(self, actor, command_id, token, target_fence):
        positive(target_fence, "target fence")
        claims = self.verify(token)
        payload = {"type": "transfer_claim", "token_hash": hashlib.sha256(token.encode("ascii")).hexdigest(), "target_fence": target_fence}
        def apply(tx):
            row = tx.execute("SELECT * FROM transfer WHERE id=?", (claims["transfer_id"],)).fetchone()
            if not row or row["token_hash"] != payload["token_hash"] or row["entity_id"] != claims["entity_id"] or row["target"] != claims["target"]:
                raise Conflict("transfer token does not match durable record")
            self.world.require_location(tx, actor, row["target"], target_fence)
            if row["state"] == "ABORTED":
                raise Conflict("transfer was aborted")
            if row["state"] == "COMMITTED":
                if row["target_owner"] != actor or row["target_fence"] != target_fence:
                    raise Conflict("committed transfer belongs to another destination fence")
                return self.public(row)
            if row["state"] == "PREPARED" and row["expires_ms"] <= self.world.real_ms():
                raise Conflict("unclaimed transfer expired")
            if row["state"] == "CLAIMED" and row["target_owner"] == actor and row["target_fence"] == target_fence:
                return self.public(row, checkpoint=True)
            # Only the current target lease may recover an expired old claim;
            # the old target is fenced before it can activate a hidden actor.
            tx.execute("UPDATE transfer SET state='CLAIMED',target_owner=?,target_fence=? WHERE id=?",
                       (actor, target_fence, row["id"]))
            self.store.event(tx, "transfer:" + row["id"], "TransferClaimed",
                             {"target_owner": actor, "target_fence": target_fence}, self.world.now())
            return self.public(tx.execute("SELECT * FROM transfer WHERE id=?", (row["id"],)).fetchone(), checkpoint=True)
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.world.require_location(tx, actor, claims["target"], target_fence))

    def commit(self, actor, command_id, transfer_id, target_fence):
        persistent_id(transfer_id)
        positive(target_fence, "target fence")
        payload = {"type": "transfer_commit", "id": transfer_id, "target_fence": target_fence}
        def apply(tx):
            row = tx.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone()
            if not row or row["target_owner"] != actor or row["target_fence"] != target_fence:
                raise Conflict("destination claim/fence mismatch")
            self.world.require_location(tx, actor, row["target"], target_fence)
            if row["state"] == "COMMITTED":
                return self.public(row)
            if row["state"] != "CLAIMED":
                raise Conflict("transfer is not claimed")
            checkpoint = json.loads(row["checkpoint"])
            root = tx.execute("SELECT kind FROM entity WHERE id=?", (row["entity_id"],)).fetchone()
            if root[0] == "CHARACTER":
                self.ownership.admission(tx, row["target"], excluding=row["entity_id"])
            for value in checkpoint["ids"]:
                updated = tx.execute("UPDATE entity SET location=?,writer=?,fence=?,version=version+1 WHERE id=? AND writer=?",
                                     (row["target"], actor, target_fence, value, "transfer:" + transfer_id))
                if updated.rowcount != 1:
                    raise Conflict("transfer entity ownership changed")
            tx.execute("UPDATE player_session SET owner=?,state='ACTIVE',fence=fence+1 WHERE character_id=? AND state='FROZEN'",
                       (actor, row["entity_id"]))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id=?", (row["entity_id"],))
            tx.execute("UPDATE transfer SET state='COMMITTED' WHERE id=?", (transfer_id,))
            self.store.event(tx, "transfer:" + transfer_id, "TransferCommitted",
                             {"entity_id": row["entity_id"], "source": row["source"], "target": row["target"],
                              "owner": actor, "fence": target_fence, "member_ids": checkpoint["ids"]}, self.world.now())
            return self.public(tx.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone())
        def authorize(tx):
            row = tx.execute("SELECT target FROM transfer WHERE id=?", (transfer_id,)).fetchone()
            if not row:
                raise Conflict("unknown transfer")
            self.world.require_location(tx, actor, row[0], target_fence)
        return self.store.command(actor, command_id, payload, apply, authorize=authorize)

    def abort(self, actor, command_id, transfer_id, source_fence):
        persistent_id(transfer_id)
        positive(source_fence, "source fence")
        payload = {"type": "transfer_abort", "id": transfer_id, "source_fence": source_fence}
        def apply(tx):
            row = tx.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone()
            if not row:
                raise Conflict("unknown transfer")
            self.world.require_location(tx, actor, row["source"], source_fence)
            if row["state"] == "ABORTED":
                return self.public(row)
            if row["state"] != "PREPARED":
                raise Conflict("claimed/committed transfer requires destination recovery, not source resume")
            root = tx.execute("SELECT kind FROM entity WHERE id=?", (row["entity_id"],)).fetchone()
            session_state = "ACTIVE"
            if root[0] == "CHARACTER":
                try:
                    self.ownership.admission(tx, row["source"], excluding=row["entity_id"])
                except Conflict:
                    # Restoring ownership must not exceed source capacity.
                    # The checkpoint survives; reconnect waits for admission.
                    session_state = "DISCONNECTED"
            for value in json.loads(row["checkpoint"])["ids"]:
                updated = tx.execute("UPDATE entity SET writer=?,fence=?,version=version+1 WHERE id=? AND writer=?",
                                     (actor, source_fence, value, "transfer:" + transfer_id))
                if updated.rowcount != 1:
                    raise Conflict("transfer entity ownership changed")
            tx.execute("UPDATE player_session SET owner=?,state=?,fence=fence+1 WHERE character_id=? AND state='FROZEN'",
                       (actor, session_state, row["entity_id"]))
            tx.execute("UPDATE character SET session_fence=session_fence+1 WHERE id=?", (row["entity_id"],))
            tx.execute("UPDATE transfer SET state='ABORTED' WHERE id=?", (transfer_id,))
            self.store.event(tx, "transfer:" + transfer_id, "TransferAborted", payload, self.world.now())
            return self.public(tx.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone())
        return self.store.command(actor, command_id, payload, apply)

    def status(self, actor, transfer_id):
        persistent_id(transfer_id)
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            row = self.store.db.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone()
            if not row:
                raise Invalid("unknown transfer")
            owners = self.store.db.execute("SELECT owner FROM location_lease WHERE location IN (?,?)", (row["source"], row["target"])).fetchall()
            if actor not in {value[0] for value in owners}:
                raise Conflict("transfer status is restricted to source/destination")
            return self.public(row)

    def public(self, row, checkpoint=False):
        result = {key: row[key] for key in ("id", "entity_id", "source", "target", "state",
                                           "target_owner", "target_fence", "expires_ms")}
        if checkpoint:
            result["checkpoint"] = json.loads(row["checkpoint"])
        session = self.store.db.execute("SELECT state,fence FROM player_session WHERE character_id=?", (row["entity_id"],)).fetchone()
        result["session_state"] = session[0] if session else None
        result["session_fence"] = session[1] if session else None
        return result
