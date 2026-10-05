"""A local World Service clock; DB checkpoints freeze service downtime."""
import json
import secrets
import time

from .store import Conflict, Invalid, Unavailable, canonical, finite, identifier, positive


class World:
    def __init__(self, store, *, world_id=None, seed=None, initial_ms=0, scale=10,
                 monotonic=time.monotonic_ns, wall=time.time_ns):
        self.store = store
        self.monotonic = monotonic
        self.wall = wall
        if store.epoch is not None:
            raise Conflict("world service already bootstrapped")
        finite(initial_ms)
        finite(scale, 0.001, 1000)
        if world_id is not None and (type(world_id) is not int or not 0 < world_id < 2**64):
            raise Invalid("invalid WorldID")
        if seed is not None and (type(seed) is not int or not 0 <= seed < 2**64):
            raise Invalid("invalid world seed")
        with store.transaction() as tx:
            row = tx.execute("SELECT * FROM world WHERE singleton=1").fetchone()
            if row is None:
                tx.execute("INSERT INTO world VALUES(1,?,?,?,?,?,1,1,0)",
                           (str(world_id or secrets.randbits(63) or 1),
                            str(seed if seed is not None else secrets.randbits(64)), 1, initial_ms, scale))
            else:
                if world_id is not None and str(world_id) != row["world_id"]:
                    raise Conflict("database belongs to a different world")
                if seed is not None and str(seed) != row["seed"]:
                    raise Conflict("world seed cannot be changed on restart")
                positive(row["epoch"] + 1, "authority epoch")
                tx.execute("UPDATE world SET epoch=epoch+1,world_ms=MAX(world_ms,event_highwater),sequence=1,revision=revision+1 WHERE singleton=1")
            row = tx.execute("SELECT * FROM world WHERE singleton=1").fetchone()
        store.epoch = row["epoch"]
        self.world_id, self.seed = int(row["world_id"]), int(row["seed"])
        self._anchor_ms, self._scale = row["world_ms"], row["scale"]
        self._anchor_ns = self._last_ns = monotonic()
        self._last_wall_ms = wall() // 1_000_000

    def now(self):
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            now = self.monotonic()
            if now < self._last_ns:
                raise Unavailable("monotonic clock regressed")
            self._last_ns = now
            result = self._anchor_ms + (now - self._anchor_ns) / 1_000_000 * self._scale
            return finite(result)

    def real_ms(self):
        # Single-host lease clock. A wall-clock rollback closes mutation
        # admission until time catches up; it cannot resurrect an expired lease.
        with self.store.lock:
            value = self.wall() // 1_000_000
            if value < self._last_wall_ms:
                raise Unavailable("lease clock regressed")
            self._last_wall_ms = value
            return value

    def sample(self):
        with self.store.transaction() as tx:
            now = self.now()
            tx.execute("UPDATE world SET world_ms=?,sequence=sequence+1 WHERE singleton=1", (now,))
            row = tx.execute("SELECT * FROM world WHERE singleton=1").fetchone()
            return {"schema": 1, "world_id": int(row["world_id"]), "seed": int(row["seed"]),
                    "authority_epoch": row["epoch"], "sequence": row["sequence"],
                    "world_ms": now, "time_scale": self._scale, "revision": row["revision"]}

    def set_scale(self, actor, command_id, value):
        finite(value, 0.001, 1000)
        # In-memory anchor changes only after the durable command succeeds.
        with self.store.lock:
            now = self.now()
            anchor_ns = self._last_ns
            def apply(tx):
                tx.execute("UPDATE world SET world_ms=?,scale=?,sequence=sequence+1 WHERE singleton=1", (now, value))
                event = self.store.event(tx, "world", "ScaleChanged", {"scale": value}, now)
                return {"world_ms": now, "scale": value, "event": event}
            result = self.store.command(actor, command_id, {"type": "scale", "value": value}, apply)
            # A retry after later changes returns its old result without
            # rebasing to that stale result or applying the scale twice.
            current = self.store.db.execute("SELECT scale FROM world WHERE singleton=1").fetchone()[0]
            if current != self._scale:
                self._anchor_ms, self._anchor_ns, self._scale = now, anchor_ns, current
            return result

    def claim_location(self, actor, command_id, location, capacity=128, ttl_ms=15000):
        identifier(actor)
        identifier(location)
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise Invalid("invalid location capacity")
        if type(ttl_ms) is not int or not 1000 <= ttl_ms <= 60000:
            raise Invalid("invalid lease duration")
        def apply(tx):
            real, now = self.real_ms(), self.now()
            row = tx.execute("SELECT * FROM location_lease WHERE location=?", (location,)).fetchone()
            if row and row["expires_ms"] > real:
                if row["owner"] != actor:
                    raise Conflict("location already has an active owner")
                fence = row["fence"]
            else:
                fence = positive(row["fence"] + 1 if row else 1, "location fence")
            tx.execute("INSERT INTO location_lease VALUES(?,?,?,?,?) ON CONFLICT(location) DO UPDATE SET owner=excluded.owner,fence=excluded.fence,expires_ms=excluded.expires_ms,capacity=excluded.capacity",
                       (location, actor, fence, real + ttl_ms, capacity))
            event = self.store.event(tx, "location:" + location, "LocationClaimed",
                                     {"owner": actor, "fence": fence, "expires_ms": real + ttl_ms}, now)
            return {"location": location, "owner": actor, "fence": fence, "expires_ms": real + ttl_ms, "event": event}
        return self.store.command(actor, command_id, {"type": "claim_location", "location": location,
                                                     "capacity": capacity, "ttl_ms": ttl_ms}, apply)

    def renew_location(self, actor, command_id, location, fence, ttl_ms=15000):
        positive(fence, "location fence")
        identifier(location)
        if type(ttl_ms) is not int or not 1000 <= ttl_ms <= 60000:
            raise Invalid("invalid lease duration")
        def apply(tx):
            self.require_location(tx, actor, location, fence)
            expiry = self.real_ms() + ttl_ms
            tx.execute("UPDATE location_lease SET expires_ms=? WHERE location=?", (expiry, location))
            return {"location": location, "fence": fence, "expires_ms": expiry}
        return self.store.command(actor, command_id, {"type": "renew", "location": location,
                                                     "fence": fence, "ttl_ms": ttl_ms}, apply)

    def require_location(self, tx, actor, location, fence):
        row = tx.execute("SELECT * FROM location_lease WHERE location=?", (location,)).fetchone()
        if not row or row["owner"] != actor or row["fence"] != fence or row["expires_ms"] <= self.real_ms():
            raise Conflict("location lease/fence is no longer active")
        return row
