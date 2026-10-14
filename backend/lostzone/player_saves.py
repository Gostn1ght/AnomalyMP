"""Fenced, bounded native checkpoints for the future primary engine adapter.

Only a live master-owned character/session may upload. Incomplete transfers
never replace a committed checkpoint. This module does not activate native
game persistence or instantiate players from the staged migration archive.
"""
import base64
import hashlib
import json
import re
import uuid

from .native_save import FILE_LIMIT, identity, parse_native_save
from .ownership import Ownership
from .store import Conflict, Invalid, Unavailable, canonical, persistent_id, positive

CHUNK = 30720  # divisible by three; bounded JSON/base64 GET response
UPLOAD_BUDGET = 64 * 1024 * 1024


class PlayerSaves:
    def __init__(self, world):
        self.world, self.store = world, world.store
        self.ownership = Ownership(world)

    def authorize(self, tx, actor, character_id, fence, session_fence):
        row = self.ownership.require_entity(tx, actor, character_id, fence, alive=True)
        if row["kind"] != "CHARACTER":
            raise Conflict("native save requires a character")
        session = tx.execute("SELECT fence FROM player_session WHERE character_id=?", (character_id,)).fetchone()
        if session[0] != positive(session_fence, "session fence"):
            raise Conflict("native save session fence changed")
        return row

    @staticmethod
    def revision(tx, character_id):
        return tx.execute("SELECT COALESCE(MAX(revision),0) FROM native_player_save WHERE character_id=?", (character_id,)).fetchone()[0]

    def upload(self, tx, actor, character_id, fence, session_fence, upload_id):
        persistent_id(upload_id)
        self.authorize(tx, actor, character_id, fence, session_fence)
        row = tx.execute("SELECT * FROM native_player_upload WHERE id=?", (upload_id,)).fetchone()
        if not row or (row["character_id"], row["writer"], row["fence"], row["session_fence"], row["epoch"]) != (
                character_id, actor, fence, session_fence, self.store.epoch) or row["expires_ms"] <= self.world.real_ms():
            raise Conflict("native upload expired or changed authority")
        return row

    def begin(self, actor, command_id, character_id, fence, session_fence, entity_version,
              base_revision, slot, byte_count, sha256):
        persistent_id(character_id)
        positive(entity_version)
        if type(base_revision) is not int or not 0 <= base_revision < 2**63-1:
            raise Invalid("invalid native base revision")
        if type(byte_count) is not int or not 4 <= byte_count <= FILE_LIMIT:
            raise Invalid("native checkpoint exceeds admission bounds")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise Invalid("invalid native checkpoint checksum")
        payload = {"type": "native_save_begin", "character_id": character_id, "fence": fence,
                   "session_fence": session_fence, "entity_version": entity_version, "base_revision": base_revision,
                   "slot": slot, "byte_count": byte_count, "sha256": sha256}
        def apply(tx):
            row = self.authorize(tx, actor, character_id, fence, session_fence)
            account = tx.execute("SELECT account FROM character WHERE id=?", (character_id,)).fetchone()[0]
            if identity(self.world.world_id, self.world.seed, account, slot) != character_id:
                raise Conflict("native save account/slot identity mismatch")
            if row["version"] != entity_version or self.revision(tx, character_id) != base_revision:
                raise Conflict("native checkpoint version changed")
            now = self.world.real_ms()
            tx.execute("DELETE FROM native_player_upload WHERE epoch<>? OR expires_ms<=? OR id IN ("
                       "SELECT u.id FROM native_player_upload u JOIN entity e ON e.id=u.character_id "
                       "JOIN player_session s ON s.character_id=u.character_id WHERE e.writer<>u.writer OR e.fence<>u.fence "
                       "OR e.alive<>1 OR s.owner<>u.writer OR s.fence<>u.session_fence OR s.state<>'ACTIVE')",
                       (self.store.epoch, now))
            if tx.execute("SELECT 1 FROM native_player_upload WHERE character_id=?", (character_id,)).fetchone():
                raise Conflict("native character already has an incomplete upload")
            used, count = tx.execute("SELECT COALESCE(SUM(byte_count),0),COUNT(*) FROM native_player_upload").fetchone()
            if used + byte_count > UPLOAD_BUDGET or count >= 32:
                raise Unavailable("native upload admission budget is full")
            upload_id = uuid.uuid4().hex
            tx.execute("INSERT INTO native_player_upload VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (upload_id, character_id, actor, fence, session_fence, self.store.epoch,
                        entity_version, base_revision, slot, byte_count, sha256, 0, now + 120000))
            return {"upload_id": upload_id, "offset": 0, "chunk_bytes": CHUNK}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.authorize(tx, actor, character_id, fence, session_fence),
                                  validate_replay=lambda tx, result: self.upload(tx, actor, character_id, fence, session_fence, result["upload_id"]))

    def append(self, actor, command_id, character_id, fence, session_fence, upload_id, offset, data):
        if type(offset) is not int or offset < 0 or offset % CHUNK or not isinstance(data, str) or not 1 <= len(data) <= CHUNK*4//3:
            raise Invalid("invalid native upload chunk")
        try:
            raw = base64.b64decode(data, validate=True)
        except ValueError as error:
            raise Invalid("invalid native upload base64") from error
        if not raw or len(raw) > CHUNK or base64.b64encode(raw).decode("ascii") != data:
            raise Invalid("noncanonical native upload chunk")
        payload = {"type": "native_save_append", "character_id": character_id, "fence": fence,
                   "session_fence": session_fence, "upload_id": upload_id, "offset": offset, "data": data}
        def apply(tx):
            row = self.upload(tx, actor, character_id, fence, session_fence, upload_id)
            if offset != row["received"] or offset + len(raw) > row["byte_count"] or (
                    offset + len(raw) < row["byte_count"] and len(raw) != CHUNK):
                raise Conflict("native upload offset or chunk size changed")
            tx.execute("INSERT INTO native_player_part VALUES(?,?,?)", (upload_id, offset, data))
            tx.execute("UPDATE native_player_upload SET received=? WHERE id=?", (offset + len(raw), upload_id))
            return {"upload_id": upload_id, "offset": offset + len(raw)}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.upload(tx, actor, character_id, fence, session_fence, upload_id))

    def finish(self, actor, command_id, character_id, fence, session_fence, upload_id):
        persistent_id(command_id)
        persistent_id(upload_id)
        payload = {"type": "native_save_finish", "character_id": character_id, "fence": fence,
                   "session_fence": session_fence, "upload_id": upload_id}
        # A committed retry has no upload rows. Authorize under the current
        # session first; then return the durable result without reassembly.
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            self.authorize(self.store.db, actor, character_id, fence, session_fence)
            previous = self.store.db.execute("SELECT payload_hash,result FROM command_result WHERE actor=? AND id=?", (actor, command_id)).fetchone()
            if previous:
                if previous["payload_hash"] != hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest():
                    raise Conflict("idempotency key reused for another command")
                return json.loads(previous["result"])
            row = self.upload(self.store.db, actor, character_id, fence, session_fence, upload_id)
            if row["received"] != row["byte_count"]:
                raise Conflict("native upload is incomplete")
            parts = self.store.db.execute("SELECT offset,payload_base64 FROM native_player_part WHERE upload_id=? ORDER BY offset", (upload_id,)).fetchall()
            raw = b"".join(base64.b64decode(part["payload_base64"], validate=True) for part in parts)
            expected = row["sha256"]
        # Bounded format/checksum work happens outside the SQLite/world lock.
        saved = parse_native_save(raw)
        if saved.sha256 != expected:
            raise Invalid("native upload complete checksum mismatch")
        encoded = base64.b64encode(raw).decode("ascii")
        def apply(tx):
            current = self.upload(tx, actor, character_id, fence, session_fence, upload_id)
            entity = self.authorize(tx, actor, character_id, fence, session_fence)
            if entity["version"] != current["entity_version"] or self.revision(tx, character_id) != current["base_revision"]:
                raise Conflict("native checkpoint changed before commit")
            if current["sha256"] != saved.sha256 or current["received"] != len(raw) or current["byte_count"] != len(raw):
                raise Conflict("native upload changed before commit")
            revision = current["base_revision"] + 1
            tx.execute("INSERT INTO native_player_save VALUES(?,?,?,?,?,?)",
                       (character_id, revision, saved.sha256, len(raw), canonical(saved.summary()), encoded))
            state = json.loads(entity["state"])
            state["native_save"] = {"revision": revision, "sha256": saved.sha256, "bytes": len(raw)}
            state = canonical(state)
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (state, character_id))
            tx.execute("UPDATE character SET state=? WHERE id=?", (state, character_id))
            tx.execute("DELETE FROM native_player_upload WHERE id=?", (upload_id,))
            # No active handoff can overlap an ACTIVE source commit. The two
            # latest complete checkpoints are sufficient; journal retains hashes.
            tx.execute("DELETE FROM native_player_save WHERE character_id=? AND revision<?", (character_id, revision-1))
            event = self.store.event(tx, "entity:" + character_id, "NativePlayerSaveCommitted",
                                     {"revision": revision, "sha256": saved.sha256, "bytes": len(raw)}, self.world.now())
            return {"character_id": character_id, "revision": revision, "entity_version": entity["version"]+1,
                    "sha256": saved.sha256, "bytes": len(raw), "durable": True, "event": event}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.authorize(tx, actor, character_id, fence, session_fence))

    def cancel(self, actor, command_id, character_id, fence, session_fence, upload_id):
        persistent_id(upload_id)
        payload = {"type": "native_save_cancel", "character_id": character_id, "fence": fence,
                   "session_fence": session_fence, "upload_id": upload_id}
        def apply(tx):
            row = tx.execute("SELECT character_id,writer FROM native_player_upload WHERE id=?", (upload_id,)).fetchone()
            if row and tuple(row) != (character_id, actor):
                raise Conflict("native upload belongs to another player/writer")
            tx.execute("DELETE FROM native_player_upload WHERE id=?", (upload_id,))
            return {"cancelled": True}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.authorize(tx, actor, character_id, fence, session_fence))

    def read(self, actor, character_id, fence, session_fence, revision, offset=0, transfer_id=None):
        positive(revision)
        if type(offset) is not int or offset < 0 or offset % CHUNK:
            raise Invalid("invalid native checkpoint read offset")
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            transfer_reference = None
            if transfer_id is None:
                self.authorize(self.store.db, actor, character_id, fence, session_fence)
            else:
                persistent_id(transfer_id)
                transfer = self.store.db.execute("SELECT * FROM transfer WHERE id=?", (transfer_id,)).fetchone()
                if not transfer or (transfer["entity_id"], transfer["target_owner"], transfer["target_fence"], transfer["state"]) != (
                        character_id, actor, fence, "CLAIMED"):
                    raise Conflict("native read requires the current destination claim")
                self.world.require_location(self.store.db, actor, transfer["target"], fence)
                session = self.store.db.execute("SELECT fence,state FROM player_session WHERE character_id=?", (character_id,)).fetchone()
                if not session or tuple(session) != (positive(session_fence), "FROZEN"):
                    raise Conflict("native transfer session changed")
                checkpoint = json.loads(transfer["checkpoint"])
                for entity in checkpoint["entities"]:
                    if entity["id"] == character_id:
                        transfer_reference = json.loads(entity["state"]).get("native_save")
                if not transfer_reference or transfer_reference.get("revision") != revision:
                    raise Conflict("native save is outside the immutable transfer checkpoint")
            row = self.store.db.execute("SELECT revision,sha256,byte_count,summary,substr(payload_base64,?,?) AS data FROM native_player_save WHERE character_id=? AND revision=?",
                                        (offset//3*4+1, CHUNK*4//3, character_id, revision)).fetchone()
            if not row or offset >= row["byte_count"]:
                raise Invalid("unknown native checkpoint or read range")
            if transfer_reference and transfer_reference.get("sha256") != row["sha256"]:
                raise Unavailable("native transfer checkpoint checksum mismatch")
            return {"revision": revision, "sha256": row["sha256"], "bytes": row["byte_count"],
                    "summary": json.loads(row["summary"]), "offset": offset,
                    "next_offset": min(offset+CHUNK,row["byte_count"]), "data": row["data"]}
