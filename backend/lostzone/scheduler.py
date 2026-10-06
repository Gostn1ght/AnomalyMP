"""Durable event-driven global timelines; bounded ordered catch-up.

No anonymous population regeneration, loot TTL or per-NPC ticks. NPC route
and encounter resolvers must register their own ownership-aware handlers.
"""
import json
import time

from .store import Conflict, Invalid, Unavailable, canonical, finite, identifier, persistent_id, positive


class Scheduler:
    def __init__(self, world):
        self.world, self.store = world, world.store
        self.handlers = world.scheduler_handlers
        self.handlers.setdefault("TimelinePhase",self.timeline_phase)
        world.mutation_drain = self.drain_due_in

    def apply_event_in(self, tx, row, now):
        handler = self.handlers.get(row["type"])
        if handler is None:
            raise UnavailableHandler(row["type"])
        result, applied = handler(tx, row)
        tx.execute("UPDATE scheduled_event SET state=?,result=? WHERE id=? AND state='PENDING'",
                   ("APPLIED" if applied else "CANCELLED", canonical(result), row["id"]))
        self.store.event(tx, row["aggregate_id"], "ScheduledEventApplied" if applied else "ScheduledEventCancelled",
                         {"event_id": row["id"], "result": result, "applied_world_ms": now},
                         row["due_world_ms"], committed_ms=now)
        # Publish causal continuations only after the source projection is
        # APPLIED, in this same transaction. A follow-up must not invalidate
        # its own still-PENDING source during reservation discovery.
        if applied:
            for observer in self.world.scheduler_event_observers.values():
                observer(tx, row, result)

    def drain_due_in(self, tx, cutoff, limit=64, budget_ms=5):
        """Resolve earlier dependencies inside the caller's mutation transaction.

        Exhaustion refuses the entire command, including this catch-up. The
        background runner can commit separate bounded batches before a retry.
        Handlers must not recursively enter a world mutation or replan their
        currently PENDING event; continuations publish after its APPLIED write.
        """
        finite(cutoff)
        if type(limit) is not int or not 1 <= limit <= 256 or not 0 < budget_ms <= 1000:
            raise Invalid("invalid scheduler work budget")
        self.store.require_epoch(tx)
        start, count = time.monotonic(), 0
        while True:
            row = tx.execute("SELECT * FROM scheduled_event WHERE state='PENDING' AND due_world_ms<=? ORDER BY due_world_ms,priority,id LIMIT 1", (cutoff,)).fetchone()
            if row is None:
                return count
            if count >= limit or (time.monotonic()-start)*1000 >= budget_ms:
                raise Unavailable("earlier world events require background catch-up before mutation")
            self.apply_event_in(tx, row, cutoff)
            count += 1

    def schedule_in(self, tx, event_id, due_ms, aggregate, version, event_type, payload, priority=0):
        persistent_id(event_id)
        finite(due_ms)
        identifier(aggregate)
        positive(version)
        identifier(event_type)
        if type(priority) is not int or not 0 <= priority <= 100:
            raise Invalid("invalid event priority")
        encoded = canonical(payload)
        existing = tx.execute("SELECT * FROM scheduled_event WHERE id=?", (event_id,)).fetchone()
        if existing:
            if (existing["due_world_ms"], existing["aggregate_id"], existing["expected_version"], existing["type"], existing["payload"], existing["priority"]) != (due_ms, aggregate, version, event_type, encoded, priority):
                raise Conflict("scheduled event ID reused with different input")
            return
        tx.execute("INSERT INTO scheduled_event VALUES(?,?,?,?,?,?,'PENDING',?,NULL)",
                   (event_id, due_ms, priority, aggregate, version, event_type, encoded))

    def run_due(self, limit=64, budget_ms=5):
        if type(limit) is not int or not 1 <= limit <= 256 or not 0 < budget_ms <= 1000:
            raise Invalid("invalid scheduler work budget")
        start = time.monotonic()
        count = 0
        while count < limit and (time.monotonic() - start) * 1000 < budget_ms:
            with self.store.transaction() as tx:
                self.store.require_epoch(tx)
                now = self.world.now()
                row = tx.execute("SELECT * FROM scheduled_event WHERE state='PENDING' AND due_world_ms<=? ORDER BY due_world_ms,priority,id LIMIT 1", (now,)).fetchone()
                if row is None:
                    break
                self.apply_event_in(tx, row, now)
            count += 1
        return count

    def timeline_phase(self, tx, event):
        payload = json.loads(event["payload"])
        name = payload["name"]
        row = tx.execute("SELECT * FROM world_state WHERE name=?", (name,)).fetchone()
        if not row or row["version"] != event["expected_version"]:
            return {"reason": "timeline version changed"}, False
        state = json.loads(row["state"])
        if state.get("timeline_id") != payload["timeline_id"]:
            return {"reason": "timeline replaced"}, False
        state["phase"] = payload["phase"]
        tx.execute("UPDATE world_state SET state=?,version=version+1 WHERE name=?", (canonical(state), name))
        return {"name": name, "phase": payload["phase"], "version": row["version"] + 1,
                "timeline_id": payload["timeline_id"]}, True


class UnavailableHandler(RuntimeError):
    pass
