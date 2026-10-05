"""Single-host durable authority, journal and transactional message primitives.

Only one service process owns a DB. SQLite transactions serialize worker
threads; locations call that process instead of owning independent ledgers.
This is deliberately not a distributed election or an engine snapshot.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid


class Invalid(ValueError):
    pass


class Conflict(RuntimeError):
    pass


class Unavailable(RuntimeError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", value):
        raise Invalid("invalid identifier")
    return value


def persistent_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise Invalid("expected a 128-bit lowercase persistent ID")
    return value


def positive(value, name="version"):
    if type(value) is not int or not 0 < value < 2**63:
        raise Invalid(f"invalid {name}")
    return value


def finite(value, low=0, high=2**53 - 1):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise Invalid("number is outside supported bounds")
    return value


def canonical(value, limit=1024 * 1024):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise Invalid("invalid JSON state") from error
    if len(encoded.encode("utf-8")) > limit:
        raise Invalid("state exceeds size limit")
    return encoded


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO metadata VALUES ('schema','2');
CREATE TABLE world (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), world_id TEXT NOT NULL,
 seed TEXT NOT NULL, epoch INTEGER NOT NULL CHECK(epoch>0),
 world_ms REAL NOT NULL CHECK(world_ms>=0), scale REAL NOT NULL CHECK(scale>0 AND scale<=1000),
 sequence INTEGER NOT NULL CHECK(sequence>0), revision INTEGER NOT NULL CHECK(revision>0),
 event_highwater REAL NOT NULL CHECK(event_highwater>=0));
CREATE TABLE location_lease (
 location TEXT PRIMARY KEY, owner TEXT NOT NULL, fence INTEGER NOT NULL CHECK(fence>0),
 expires_ms INTEGER NOT NULL, capacity INTEGER NOT NULL CHECK(capacity>0 AND capacity<=128));
CREATE TABLE world_state (
 name TEXT PRIMARY KEY, version INTEGER NOT NULL CHECK(version>0), state TEXT NOT NULL);
CREATE TABLE entity (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, location TEXT NOT NULL,
 writer TEXT NOT NULL, fence INTEGER NOT NULL CHECK(fence>0),
 version INTEGER NOT NULL CHECK(version>0), alive INTEGER NOT NULL CHECK(alive IN (0,1)),
 state TEXT NOT NULL);
CREATE INDEX entity_location ON entity(location,kind);
CREATE TABLE group_member (
 group_id TEXT NOT NULL REFERENCES entity(id), member_id TEXT PRIMARY KEY REFERENCES entity(id));
CREATE TABLE container (
 id TEXT PRIMARY KEY REFERENCES entity(id), policy TEXT NOT NULL,
 owner TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity>=0),
 version INTEGER NOT NULL CHECK(version>0), state TEXT NOT NULL);
CREATE TABLE item (
 id TEXT PRIMARY KEY, section TEXT NOT NULL, kind TEXT NOT NULL,
 holder TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
 version INTEGER NOT NULL CHECK(version>0), state TEXT NOT NULL);
CREATE INDEX item_holder ON item(kind,holder);
CREATE TABLE character (
 id TEXT PRIMARY KEY REFERENCES entity(id), account TEXT NOT NULL,
 session_fence INTEGER NOT NULL CHECK(session_fence>0), state TEXT NOT NULL);
CREATE INDEX character_account ON character(account);
CREATE TABLE player_session (
 character_id TEXT PRIMARY KEY REFERENCES character(id), account TEXT NOT NULL,
 owner TEXT NOT NULL, fence INTEGER NOT NULL CHECK(fence>0),
 state TEXT NOT NULL CHECK(state IN('ACTIVE','FROZEN','DISCONNECTED')));
CREATE UNIQUE INDEX session_active_account ON player_session(account) WHERE state IN('ACTIVE','FROZEN');
CREATE TABLE transfer (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id),
 source TEXT NOT NULL, target TEXT NOT NULL, source_owner TEXT NOT NULL,
 source_fence INTEGER NOT NULL, target_owner TEXT, target_fence INTEGER,
 state TEXT NOT NULL CHECK(state IN ('PREPARED','CLAIMED','COMMITTED','ABORTED')),
 expires_ms INTEGER NOT NULL, token_hash TEXT NOT NULL, checkpoint TEXT NOT NULL,
 entity_version INTEGER NOT NULL, created_epoch INTEGER NOT NULL);
CREATE INDEX transfer_target ON transfer(target,state);
CREATE UNIQUE INDEX transfer_active ON transfer(entity_id) WHERE state IN ('PREPARED','CLAIMED');
CREATE TABLE quest (
 character_id TEXT NOT NULL REFERENCES character(id), id TEXT NOT NULL,
 stage INTEGER NOT NULL CHECK(stage>=0), version INTEGER NOT NULL CHECK(version>0),
 state TEXT NOT NULL, rewarded INTEGER NOT NULL CHECK(rewarded IN(0,1)),
 PRIMARY KEY(character_id,id));
CREATE TABLE quest_requirement (
 character_id TEXT NOT NULL, quest_id TEXT NOT NULL,
 entity_id TEXT NOT NULL REFERENCES entity(id), alive_required INTEGER NOT NULL,
 policy TEXT NOT NULL, PRIMARY KEY(character_id,quest_id,entity_id),
 FOREIGN KEY(character_id,quest_id) REFERENCES quest(character_id,id));
CREATE INDEX requirement_entity ON quest_requirement(entity_id);
CREATE TABLE quest_event (
 character_id TEXT NOT NULL, quest_id TEXT NOT NULL, event_sequence INTEGER NOT NULL,
 PRIMARY KEY(character_id,quest_id,event_sequence),
 FOREIGN KEY(character_id,quest_id) REFERENCES quest(character_id,id),
 FOREIGN KEY(event_sequence) REFERENCES world_event(sequence));
CREATE TABLE world_event (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 aggregate_id TEXT NOT NULL, aggregate_sequence INTEGER NOT NULL,
 epoch INTEGER NOT NULL, world_ms REAL NOT NULL, type TEXT NOT NULL,
 payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
 UNIQUE(aggregate_id,aggregate_sequence));
CREATE TABLE outbox (
 event_sequence INTEGER PRIMARY KEY REFERENCES world_event(sequence), topic TEXT NOT NULL);
CREATE TABLE outbox_ack (
 consumer TEXT NOT NULL, event_sequence INTEGER NOT NULL REFERENCES outbox(event_sequence),
 PRIMARY KEY(consumer,event_sequence));
CREATE TABLE inbox (
 consumer TEXT NOT NULL, message_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
 result TEXT NOT NULL, PRIMARY KEY(consumer,message_id));
CREATE TABLE command_result (
 actor TEXT NOT NULL, id TEXT NOT NULL, payload_hash TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(actor,id));
CREATE TABLE scheduled_event (
 id TEXT PRIMARY KEY, due_world_ms REAL NOT NULL, priority INTEGER NOT NULL,
 aggregate_id TEXT NOT NULL, expected_version INTEGER NOT NULL,
 type TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN('PENDING','APPLIED','CANCELLED')),
 payload TEXT NOT NULL, result TEXT);
CREATE INDEX scheduled_due ON scheduled_event(state,due_world_ms,priority,id);
CREATE TABLE snapshot (
 id TEXT PRIMARY KEY, schema INTEGER NOT NULL, epoch INTEGER NOT NULL,
 watermark INTEGER NOT NULL, checksum TEXT NOT NULL, payload TEXT NOT NULL);
"""

MIGRATE_V1 = """
CREATE TABLE world_state(name TEXT PRIMARY KEY,version INTEGER NOT NULL CHECK(version>0),state TEXT NOT NULL);
CREATE TABLE group_member(group_id TEXT NOT NULL REFERENCES entity(id),member_id TEXT PRIMARY KEY REFERENCES entity(id));
INSERT INTO group_member SELECT e.id,j.value FROM entity e,json_each(e.state,'$.member_ids') j WHERE e.kind='GROUP';
CREATE TABLE quest_event(character_id TEXT NOT NULL,quest_id TEXT NOT NULL,event_sequence INTEGER NOT NULL,
 PRIMARY KEY(character_id,quest_id,event_sequence),
 FOREIGN KEY(character_id,quest_id) REFERENCES quest(character_id,id),
 FOREIGN KEY(event_sequence) REFERENCES world_event(sequence));
UPDATE metadata SET value='2' WHERE key='schema';
"""


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        if existed and self.path.stat().st_size == 0:
            raise Unavailable("existing database is empty; explicit recovery is required")
        self.lock = threading.RLock()
        self.db = None
        self.epoch = None
        self._file = open(str(self.path) + ".service.lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self._file.seek(0, 2)
                if not self._file.tell():
                    self._file.write(b"\0")
                    self._file.flush()
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.db = sqlite3.connect(self.path, isolation_level=None,
                                      check_same_thread=False, timeout=5)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise Unavailable("database integrity check failed")
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not tables:
                if existed:
                    raise Unavailable("existing database has no schema; refusing to create another world")
                self.db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            row = self.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
            if row and row[0] == "1":
                self.db.executescript("BEGIN IMMEDIATE;\n" + MIGRATE_V1 + "\nCOMMIT;")
                row = self.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
            if not row or row[0] != "2":
                raise Unavailable("unsupported database schema")
            if self.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise Unavailable("database ownership references are inconsistent")
        except BaseException:
            self.close()
            raise

    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db = None
            if self._file is not None:
                # Closing the handle releases the OS lock on both platforms.
                self._file.close()
                self._file = None

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.db is None:
                raise Unavailable("store is closed")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                self.db.execute("COMMIT")
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise

    def command(self, actor, command_id, payload, apply, authorize=None):
        identifier(actor)
        persistent_id(command_id)
        digest = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
        with self.transaction() as tx:
            self.require_epoch(tx)
            if authorize is not None:
                authorize(tx)
            old = tx.execute("SELECT * FROM command_result WHERE actor=? AND id=?",
                             (actor, command_id)).fetchone()
            if old:
                if old["payload_hash"] != digest:
                    raise Conflict("idempotency key reused for another command")
                return json.loads(old["result"])
            result = apply(tx)
            tx.execute("INSERT INTO command_result VALUES(?,?,?,?)",
                       (actor, command_id, digest, canonical(result)))
            return result

    def require_epoch(self, tx):
        row = tx.execute("SELECT epoch FROM world WHERE singleton=1").fetchone()
        if row is None or self.epoch is None or row[0] != self.epoch:
            raise Unavailable("world authority is not ready")

    def event(self, tx, aggregate, event_type, payload, world_ms, topic="world", committed_ms=None):
        self.require_epoch(tx)
        identifier(aggregate)
        identifier(event_type)
        identifier(topic)
        finite(world_ms)
        committed_ms = world_ms if committed_ms is None else finite(committed_ms)
        if committed_ms < world_ms:
            raise Invalid("event cannot be committed before it occurred")
        encoded = canonical(payload)
        world = tx.execute("SELECT event_highwater FROM world WHERE singleton=1").fetchone()
        seq = tx.execute("SELECT COALESCE(MAX(aggregate_sequence),0)+1 FROM world_event WHERE aggregate_id=?",
                         (aggregate,)).fetchone()[0]
        result = tx.execute("INSERT INTO world_event(id,aggregate_id,aggregate_sequence,epoch,world_ms,type,payload,payload_hash) VALUES(?,?,?,?,?,?,?,?)",
                            (uuid.uuid4().hex, aggregate, seq, self.epoch, world_ms,
                             event_type, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()))
        tx.execute("INSERT INTO outbox VALUES(?,?)", (result.lastrowid, topic))
        tx.execute("UPDATE world SET event_highwater=?, revision=revision+1 WHERE singleton=1", (max(world[0], committed_ms),))
        return result.lastrowid

    def events(self, after=0, limit=256):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 512:
            raise Invalid("invalid event page")
        with self.lock:
            self.require_epoch(self.db)
            rows = self.db.execute("SELECT * FROM world_event WHERE sequence>? ORDER BY sequence LIMIT ?",
                                   (after, limit)).fetchall()
            return [dict(row, payload=json.loads(row["payload"])) for row in rows]

    def pending_outbox(self, consumer, limit=256):
        identifier(consumer)
        if type(limit) is not int or not 1 <= limit <= 512:
            raise Invalid("invalid outbox page")
        with self.lock:
            self.require_epoch(self.db)
            rows = self.db.execute("SELECT e.*,o.topic FROM outbox o JOIN world_event e ON e.sequence=o.event_sequence LEFT JOIN outbox_ack a ON a.consumer=? AND a.event_sequence=o.event_sequence WHERE a.consumer IS NULL ORDER BY e.sequence LIMIT ?",
                                   (consumer, limit)).fetchall()
            return [dict(row, payload=json.loads(row["payload"])) for row in rows]

    def ack_outbox(self, consumer, sequence):
        identifier(consumer)
        positive(sequence, "event sequence")
        with self.transaction() as tx:
            self.require_epoch(tx)
            if not tx.execute("SELECT 1 FROM outbox WHERE event_sequence=?", (sequence,)).fetchone():
                raise Invalid("unknown outbox event")
            tx.execute("INSERT OR IGNORE INTO outbox_ack VALUES(?,?)", (consumer, sequence))

    def consume(self, consumer, message_id, payload, apply):
        identifier(consumer)
        persistent_id(message_id)
        digest = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
        with self.transaction() as tx:
            self.require_epoch(tx)
            old = tx.execute("SELECT * FROM inbox WHERE consumer=? AND message_id=?",
                             (consumer, message_id)).fetchone()
            if old:
                if old["payload_hash"] != digest:
                    raise Conflict("message ID reused for different payload")
                return json.loads(old["result"])
            result = apply(tx)
            tx.execute("INSERT INTO inbox VALUES(?,?,?,?)",
                       (consumer, message_id, digest, canonical(result)))
            return result

    def snapshot(self):
        # SQLite owns these backend aggregates; one transaction captures all
        # projections and the journal watermark. ALife objects are not included.
        with self.transaction() as tx:
            self.require_epoch(tx)
            names = ("world", "world_state", "location_lease", "entity", "group_member", "container", "item", "character", "player_session",
                     "transfer", "quest", "quest_requirement", "quest_event", "scheduled_event")
            records = {name: [dict(row) for row in tx.execute(f"SELECT * FROM {name} ORDER BY rowid")]
                       for name in names}
            watermark = tx.execute("SELECT COALESCE(MAX(sequence),0) FROM world_event").fetchone()[0]
            encoded = canonical({"schema": 1, "epoch": self.epoch, "watermark": watermark, "records": records}, limit=128 * 1024 * 1024)
            checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            snapshot_id = uuid.uuid4().hex
            tx.execute("INSERT INTO snapshot VALUES(?,?,?,?,?,?)",
                       (snapshot_id, 1, self.epoch, watermark, checksum, encoded))
            return {"id": snapshot_id, "watermark": watermark, "checksum": checksum}

    def read_snapshot(self, snapshot_id):
        persistent_id(snapshot_id)
        with self.lock:
            self.require_epoch(self.db)
            row = self.db.execute("SELECT * FROM snapshot WHERE id=?", (snapshot_id,)).fetchone()
            if not row:
                raise Invalid("unknown snapshot")
            if hashlib.sha256(row["payload"].encode("utf-8")).hexdigest() != row["checksum"]:
                raise Unavailable("snapshot checksum mismatch")
            return json.loads(row["payload"])
