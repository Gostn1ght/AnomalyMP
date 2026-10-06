"""World-authoritative weather/emission schedule and local analytic playback."""
import hashlib
import json

from .scheduler import Scheduler
from .store import Conflict, Invalid, canonical, finite, identifier, persistent_id


class Timelines:
    def __init__(self, world):
        self.world, self.store = world, world.store
        self.scheduler = Scheduler(world)

    def schedule(self, actor, command_id, name, timeline_id, version, times, parameters):
        if name not in ("weather", "emission") or type(version) is not int or not 0 <= version < 2**63:
            raise Invalid("invalid timeline name/version")
        persistent_id(timeline_id)
        if not isinstance(times, dict) or not isinstance(parameters, dict):
            raise Invalid("invalid timeline schedule")
        phases = ("TRANSITION", "SETTLED") if name == "weather" else ("WARNING", "ACTIVE", "PEAK", "ENDED")
        if set(times) != set(phases):
            raise Invalid("timeline phases are incomplete")
        values = [finite(times[phase]) for phase in phases]
        if any(b <= a for a, b in zip(values, values[1:])):
            raise Invalid("timeline phases must be strictly ordered")
        if name == "weather":
            identifier(parameters.get("source"))
            identifier(parameters.get("target"))
        elif not 0 < finite(parameters.get("intensity"), 0, 100) <= 100:
            raise Invalid("invalid emission intensity")
        seed = parameters.get("seed")
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("timeline requires a stable seed")
        payload = {"type": "timeline_schedule", "name": name, "timeline_id": timeline_id,
                   "version": version, "times": times, "parameters": parameters}
        def apply(tx):
            old = tx.execute("SELECT * FROM world_state WHERE name=?", (name,)).fetchone()
            if (old["version"] if old else 0) != version:
                raise Conflict("timeline version changed")
            if tx.execute("SELECT 1 FROM scheduled_event WHERE id=?", (self.event_id(name, timeline_id, phases[0]),)).fetchone():
                raise Conflict("timeline ID cannot be reused")
            state = {"timeline_id": timeline_id, "phase": "SCHEDULED", "times": times, "parameters": parameters}
            tx.execute("INSERT INTO world_state VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET version=excluded.version,state=excluded.state",
                       (name, version + 1, canonical(state)))
            for index, phase in enumerate(phases):
                self.scheduler.schedule_in(tx, self.event_id(name, timeline_id, phase), times[phase],
                                           "world:" + name, version + 1 + index, "TimelinePhase",
                                           {"name": name, "timeline_id": timeline_id, "phase": phase})
            event = self.store.event(tx, "world:" + name, "TimelineScheduled", payload, self.world.now())
            return {"timeline_id": timeline_id, "version": version + 1, "event": event}
        return self.store.command(actor, command_id, payload, self.world.mutation(apply))

    @staticmethod
    def event_id(name, timeline_id, phase):
        return hashlib.sha256(f"timeline:{name}:{timeline_id}:{phase}".encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def evaluate(name, state, world_ms):
        finite(world_ms)
        times = state["times"]
        phases = ("TRANSITION", "SETTLED") if name == "weather" else ("WARNING", "ACTIVE", "PEAK", "ENDED")
        phase = "SCHEDULED"
        for candidate in phases:
            if world_ms >= times[candidate]:
                phase = candidate
        result = {"timeline_id": state["timeline_id"], "phase": phase, "parameters": state["parameters"]}
        if name == "weather":
            result["blend"] = min(1, max(0, (world_ms - times["TRANSITION"]) / (times["SETTLED"] - times["TRANSITION"])))
        return result
