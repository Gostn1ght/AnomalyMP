"""World-authoritative weather/emission schedule and local analytic playback."""
import hashlib
import json

from .scheduler import Scheduler
from .store import Conflict, Invalid, canonical, finite, identifier, persistent_id, positive


PHASES = {"weather": ("TRANSITION", "SETTLED"),
          "emission": ("WARNING", "ACTIVE", "PEAK", "ENDED"),
          "psi_storm": ("WARNING", "ACTIVE", "PEAK", "ENDED")}


class Timelines:
    def __init__(self, world):
        self.world, self.store = world, world.store
        self.scheduler = Scheduler(world)

    def schedule(self, actor, command_id, name, timeline_id, version, times, parameters):
        # None is an administrator's explicit replacement after mutation catchup.
        # Integer versions retain compare-and-swap semantics for API clients.
        if name not in PHASES or (version is not None and
                (type(version) is not int or not 0 <= version < 2**63)):
            raise Invalid("invalid timeline name/version")
        persistent_id(timeline_id)
        if not isinstance(times, dict) or not isinstance(parameters, dict):
            raise Invalid("invalid timeline schedule")
        phases = PHASES[name]
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
            current = old["version"] if old else 0
            if version is not None and current != version:
                raise Conflict("timeline version changed")
            positive(current + len(phases) + 1, "final timeline version")
            next_version = current + 1
            if tx.execute("SELECT 1 FROM scheduled_event WHERE id=?", (self.event_id(name, timeline_id, phases[0]),)).fetchone():
                raise Conflict("timeline ID cannot be reused")
            state = {"timeline_id": timeline_id, "phase": "SCHEDULED", "times": times, "parameters": parameters}
            tx.execute("INSERT INTO world_state VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET version=excluded.version,state=excluded.state",
                       (name, next_version, canonical(state)))
            for index, phase in enumerate(phases):
                self.scheduler.schedule_in(tx, self.event_id(name, timeline_id, phase), times[phase],
                                           "world:" + name, next_version + index, "TimelinePhase",
                                           {"name": name, "timeline_id": timeline_id, "phase": phase})
            event = self.store.event(tx, "world:" + name, "TimelineScheduled", payload, self.world.now())
            return {"timeline_id": timeline_id, "version": next_version, "event": event}
        return self.store.command(actor, command_id, payload, self.world.mutation(apply))

    @staticmethod
    def event_id(name, timeline_id, phase):
        return hashlib.sha256(f"timeline:{name}:{timeline_id}:{phase}".encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def public_state(name, envelope):
        """Bounded native wire contract, excluding arbitrary admin parameters."""
        if name not in PHASES or not isinstance(envelope, dict):
            raise Invalid("invalid public timeline")
        version = positive(envelope.get("version"))
        state = envelope.get("state")
        if not isinstance(state, dict):
            raise Invalid("invalid public timeline state")
        timeline_id = persistent_id(state.get("timeline_id"))
        phases = PHASES[name]
        phase = state.get("phase")
        if phase not in ("SCHEDULED", *phases):
            raise Invalid("invalid public timeline phase")
        times, parameters = state.get("times"), state.get("parameters")
        if not isinstance(times, dict) or set(times) != set(phases) or not isinstance(parameters, dict):
            raise Invalid("incomplete public timeline")
        values = [finite(times[key]) for key in phases]
        if any(b <= a for a, b in zip(values, values[1:])):
            raise Invalid("invalid public timeline times")
        seed = parameters.get("seed")
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid public timeline seed")
        public = {"seed": seed}
        if name == "weather":
            public.update(source=identifier(parameters.get("source")), target=identifier(parameters.get("target")))
        else:
            intensity = finite(parameters.get("intensity"), 0, 100)
            if intensity == 0:
                raise Invalid("invalid public timeline intensity")
            public["intensity"] = intensity
        return {"version": version, "state": {"timeline_id": timeline_id, "phase": phase,
                "times": dict(zip(phases, values)), "parameters": public}}

    @staticmethod
    def evaluate(name, state, world_ms):
        finite(world_ms)
        times = state["times"]
        phases = PHASES[name]
        phase = "SCHEDULED"
        for candidate in phases:
            if world_ms >= times[candidate]:
                phase = candidate
        result = {"timeline_id": state["timeline_id"], "phase": phase, "parameters": state["parameters"]}
        if name == "weather":
            result["blend"] = min(1, max(0, (world_ms - times["TRANSITION"]) / (times["SETTLED"] - times["TRANSITION"])))
        return result
