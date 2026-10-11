"""Bounded, immutable registry cuts for a future location runtime adapter.

WAL read transactions preserve a single cut while the service keeps writing.
Every page still checks the LIVE authority. Captures expire, are bounded and
are never an authorization to spawn or mutate engine objects.
"""
import json
import base64
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
import uuid

from .store import Conflict, Invalid, Unavailable, canonical, identifier, persistent_id, positive

MAX_ROWS = 64
MAX_BYTES = 60000
MAX_CAPTURES = 32
LIFETIME_NS = 15_000_000_000


class LocationBootstrap:
    def __init__(self, world, *, monotonic=time.monotonic_ns):
        self.world, self.store = world, world.store
        self.monotonic = monotonic
        self.lock = threading.RLock()
        self.captures, self.requests = {}, {}
        self.last_ns = 0
        self.closed = False
        self.cursor_key = secrets.token_bytes(32)

    def _now(self):
        now = self.monotonic()
        if type(now) is not int or now < self.last_ns:
            raise Unavailable("capture monotonic clock regressed")
        self.last_ns = now
        return now

    def _drop(self, capture_id):
        capture = self.captures.pop(capture_id)
        self.requests.pop((capture["actor"], capture["request"]), None)
        capture["db"].close()

    def reap(self):
        with self.lock:
            now = self._now()
            for key, capture in list(self.captures.items()):
                if now >= capture["until"]:
                    self._drop(key)

    def invalidate(self):
        with self.lock:
            for key in list(self.captures):
                self._drop(key)

    def close(self):
        with self.lock:
            self.invalidate()
            self.closed = True

    def release(self, actor, location, fence, epoch, capture_id):
        identifier(actor); identifier(location); positive(fence); positive(epoch); persistent_id(capture_id)
        with self.lock:
            capture = self.captures.get(capture_id)
            if capture is not None:
                if (capture["actor"], capture["location"], capture["fence"], capture["epoch"]) != (actor, location, fence, epoch):
                    raise Conflict("registry capture scope changed")
                self._drop(capture_id)
            return {"released": True}

    def _token(self, capture_id, position):
        data = base64.urlsafe_b64encode(canonical([capture_id, *position]).encode()).rstrip(b"=")
        signature = hmac.new(self.cursor_key, data, hashlib.sha256).hexdigest()
        return data.decode("ascii") + "." + signature

    def _position(self, capture_id, token):
        if not isinstance(token, str) or len(token) > 512:
            raise Invalid("invalid registry cursor")
        try:
            data, signature = token.encode("ascii").split(b".")
            expected = hmac.new(self.cursor_key, data, hashlib.sha256).hexdigest().encode()
            if not hmac.compare_digest(signature, expected):
                raise Invalid("invalid registry cursor signature")
            value = json.loads(base64.b64decode(data + b"=" * (-len(data) % 4), altchars=b"-_", validate=True))
        except (ValueError, UnicodeError) as error:
            raise Invalid("invalid registry cursor") from error
        if not isinstance(value, list) or len(value) != 4 or value[0] != capture_id:
            raise Invalid("registry cursor belongs to another capture")
        return value[1:]

    def _open(self, actor, location, fence, request, now):
        if len(self.captures) >= MAX_CAPTURES:
            raise Unavailable("registry capture slots are full")
        # One pinned cut per owner/map bounds WAL retention and prevents a
        # caller abandoning captures from filling all slots by itself.
        if any(c["actor"] == actor and c["location"] == location for c in self.captures.values()):
            raise Conflict("a location capture is already active")
        self.world.sample()
        db = sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True,
                             isolation_level=None, check_same_thread=False, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            row = db.execute("SELECT * FROM world WHERE singleton=1").fetchone()
            watermark = db.execute("SELECT COALESCE(MAX(sequence),0) FROM world_event").fetchone()[0]
            clock = {"schema": 1, "world_id": int(row["world_id"]), "seed": int(row["seed"]),
                     "authority_epoch": row["epoch"], "sequence": row["sequence"],
                     "world_ms": row["world_ms"], "time_scale": row["scale"], "revision": row["revision"]}
            key = uuid.uuid4().hex
            capture = {"db": db, "actor": actor, "location": location, "fence": fence,
                       "request": request, "epoch": row["epoch"], "until": now + LIFETIME_NS,
                       "metadata": {"schema": 1, "capture_id": key, "request_id": request,
                                    "location": location, "owner": actor, "fence": fence,
                                    "world_seed": int(row["seed"]), "state_revision": row["revision"],
                                    "clock": clock, "event_watermark": watermark}}
            self.captures[key] = capture
            self.requests[(actor, request)] = key
            return key
        except BaseException:
            db.close()
            raise

    @staticmethod
    def _decode(row, *, json_state=True):
        result = dict(row)
        if "state" in result and json_state:
            result["state"] = json.loads(result["state"])
        return result

    def _entry(self, db, phase, row):
        # Reject a single unsupported mod capture before parsing a large state.
        if len(row["state"].encode("utf-8")) > MAX_BYTES - 4096:
            raise Conflict("registry record exceeds page budget")
        result = {"type": phase, **self._decode(row)}
        if phase == "entity":
            for table, key in (("character", "id"), ("player_session", "character_id"),
                               ("container", "id"), ("route", "entity_id")):
                extra = db.execute(f"SELECT * FROM {table} WHERE {key}=?", (row["id"],)).fetchone()
                if extra is not None:
                    if "state" in extra.keys() and len(extra["state"].encode("utf-8")) > MAX_BYTES - 4096:
                        raise Conflict("registry attachment exceeds page budget")
                    result[table] = self._decode(extra, json_state=table != "player_session")
            if row["kind"] == "GROUP":
                members = db.execute("SELECT member_id FROM group_member WHERE group_id=? ORDER BY member_id LIMIT 513",
                                     (row["id"],)).fetchall()
                if len(members) > 512:
                    raise Conflict("group capture exceeds member budget")
                result["members"] = [member[0] for member in members]
        return result

    @staticmethod
    def _candidates(capture, position):
        db = capture["db"]
        location, actor, fence = capture["location"], capture["actor"], capture["fence"]
        phase, holder, lower = position or ("entity", "", "")
        if phase == "entity":
            for row in db.execute("SELECT * FROM entity WHERE location=? AND writer=? AND fence=? AND id>? ORDER BY id LIMIT 65",
                                  (location, actor, fence, lower)):
                yield ("entity", "", row["id"]), row
        if phase in ("entity", "world"):
            start = lower if phase == "world" else ""
            for row in db.execute("SELECT * FROM item WHERE kind='WORLD' AND holder=? AND id>? ORDER BY id LIMIT 65",
                                  (location, start)):
                yield ("world", location, row["id"]), row
        start_holder = holder if phase == "inventory" else ""
        # An empty item cursor marks a completely scanned holder. A nonempty
        # item cursor resumes INSIDE that holder. Empty inventories also advance.
        comparison = ">=" if phase == "inventory" and lower else ">"
        holders = db.execute(f"SELECT id FROM entity WHERE location=? AND writer=? AND fence=? AND id{comparison}? ORDER BY id LIMIT 65",
                             (location, actor, fence, start_holder)).fetchall()
        for owned in holders:
            item_start = lower if phase == "inventory" and owned[0] == start_holder else ""
            for row in db.execute("SELECT * FROM item WHERE holder=? AND kind NOT IN ('WORLD','DESTROYED') AND id>? ORDER BY id LIMIT 65",
                                  (owned[0], item_start)):
                yield ("inventory", owned[0], row["id"]), row
            yield ("inventory", owned[0], ""), None

    def page(self, actor, location, fence, epoch, *, request_id=None, capture_id=None, after=None):
        identifier(actor); identifier(location); positive(fence); positive(epoch)
        if (request_id is None) == (capture_id is None):
            raise Invalid("one request_id or capture_id is required")
        persistent_id(request_id if request_id is not None else capture_id)
        if after is not None and request_id is not None:
            raise Invalid("initial registry request does not take a cursor")
        with self.lock:
            if self.closed:
                raise Unavailable("registry capture service is closed")
            self.reap()
            now = self._now()
            with self.store.lock:
                self.store.require_epoch(self.store.db)
                if epoch != self.store.epoch:
                    raise Conflict("registry authority epoch changed")
                self.world.require_location(self.store.db, actor, location, fence)
                if request_id is not None:
                    capture_id = self.requests.get((actor, request_id))
                    if capture_id is None:
                        capture_id = self._open(actor, location, fence, request_id, now)
                capture = self.captures.get(capture_id)
                if capture is None:
                    raise Conflict("registry capture expired or is unavailable")
                if (capture["actor"], capture["location"], capture["fence"], capture["epoch"]) != (actor, location, fence, epoch):
                    raise Conflict("registry capture scope changed")
            # The pinned reader does not hold the writer's service lock while
            # decoding and assembling a page. No full registry fetchall().
            db = capture["db"]
            entries, used, steps, more, last = [], 0, 0, False, None
            position = self._position(capture_id, after) if after is not None else None
            for current, row in self._candidates(capture, position):
                if steps == MAX_ROWS:
                    more = True
                    break
                if row is not None:
                    entry = self._entry(db, "entity" if current[0] == "entity" else "item", row)
                    size = len(canonical(entry).encode("utf-8")) + 1
                    if used + size > MAX_BYTES - 4096:
                        if not steps:
                            raise Conflict("registry record exceeds page budget")
                        more = True
                        break
                    entries.append(entry)
                    used += size
                steps += 1
                last = current
            with self.store.lock:
                # Recheck live admission after serialization work: an expired
                # or replaced writer must not receive the old cut as authority.
                self.store.require_epoch(self.store.db)
                lease = self.world.require_location(self.store.db, actor, location, fence)
                live_ns = self._now()
                if (capture["until"] - live_ns) // 1_000_000 <= 0:
                    self._drop(capture_id)
                    raise Conflict("registry capture expired")
                lease_ms = lease["expires_ms"] - self.world.real_ms()
                if lease_ms <= 0:
                    raise Conflict("location lease expired")
            next_cursor = self._token(capture_id, last) if more else None
            result = {**capture["metadata"], "after": after, "next": next_cursor, "entries": entries,
                      "clock": dict(capture["metadata"]["clock"]),
                      "lease_remaining_ms": lease_ms, "capture_remaining_ms": (capture["until"] - live_ns) // 1_000_000}
            canonical({"result": result}, limit=MAX_BYTES)
            return result
