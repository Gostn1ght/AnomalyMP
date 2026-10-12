"""World director: the master plans the world's weather, emissions and psi
storms itself (owner 2026-10-12: "the master syncs weather, emissions and
similar events to the maps"). Every location server plays the same schedule
from the master's bootstrap; none decides them locally any more.

The rules follow GAMMA's single-player managers on the game calendar:
* weather: a cycle (clear, partly, cloudy, rain, storm, foggy) lasts 2/3..1
  of its 6-hour period, the next one is never the current one and not one
  already seen twice since the last reset (level_weathers.get_next_weather_cycle);
  the change is a one-hour transition;
* emission: every frequency/2..frequency game hours after the previous one
  (GAMMA's next_interval, frequency 24 h), 222 real s at time factor 10;
* psi storm: the same with frequency 48 h, 103 real s;
* an emission and a psi storm never overlap or follow within 2 game hours.
Rolls come from the world seed and a durable counter, so a restart replays
nothing and decides nothing twice. Administrator commands still replace any
schedule; the director continues after it.
"""
import random
import uuid

from .store import Conflict, Invalid, Unavailable
from .timelines import Timelines

HOUR = 3600 * 1000.0
DEFAULTS = {
    "enabled": True,
    "weather_cycles": ["clear", "partly", "cloudy", "rain", "storm", "foggy"],
    "weather_period_hours": 6,
    "weather_transition_hours": 1,
    "emission_frequency_hours": 24,
    "emission_seconds": 2220,
    "psi_storm_frequency_hours": 48,
    "psi_storm_seconds": 1030,
    "event_gap_hours": 2,
    "lead_seconds": 60,
}


class Director:
    def __init__(self, world, timelines, config=None):
        self.world, self.timelines, self.store = world, timelines, world.store
        self.config = dict(DEFAULTS)
        for key, value in (config or {}).items():
            if key not in DEFAULTS:
                raise Invalid(f"unknown director setting {key}")
            self.config[key] = value
        cycles = self.config["weather_cycles"]
        if not isinstance(cycles, list) or len(cycles) < 2 or len(set(cycles)) != len(cycles):
            raise Invalid("director needs at least two distinct weather cycles")

    # -- durable state -------------------------------------------------
    def _read(self, name):
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            row = self.store.db.execute("SELECT version,state FROM world_state WHERE name=?", (name,)).fetchone()
        import json
        return (row[0], json.loads(row[1])) if row else (0, None)

    def _rng(self, state, purpose):
        counter = state.setdefault("counter", 0)
        state["counter"] = counter + 1
        return random.Random(f"{self.world.seed}:{purpose}:{counter}")

    def _save(self, version, state):
        self.world.set_state("director", uuid.uuid4().hex, "director", version, state)

    def _schedule(self, name, times, parameters):
        self.timelines.schedule("director", uuid.uuid4().hex, name, uuid.uuid4().hex, None, times, parameters)

    # -- one pass, called by the service worker ------------------------
    def tick(self):
        if not self.config["enabled"]:
            return []
        now = self.world.now()
        version, state = self._read("director")
        state = dict(state or {})
        done = []
        for step in (self._weather, self._event_emission, self._event_psi):
            try:
                result = step(now, state)
            except (Conflict, Unavailable):
                result = None  # an administrator changed it meanwhile; next pass
            if result:
                done.append(result)
        if done:
            self._save(version, state)
        return done

    def _next_cycle(self, rng, current, history):
        cycles = self.config["weather_cycles"]
        counts = {cycle: history.count(cycle) for cycle in cycles}
        allowed = [cycle for cycle in cycles if cycle != current and counts[cycle] < 2]
        if not allowed:
            history.clear()
            allowed = [cycle for cycle in cycles if cycle != current]
        pick = rng.choice(allowed)
        history.append(pick)
        return pick

    def _weather(self, now, state):
        _, timeline = self._read("weather")
        change_at = state.get("weather_change_at")
        if timeline is not None and change_at is not None and now < change_at:
            return None
        rng = self._rng(state, "weather")
        history = state.setdefault("weather_history", [])
        current = timeline["parameters"]["target"] if timeline else self.config["weather_cycles"][0]
        target = self._next_cycle(rng, current, history) if timeline else current
        start = now + self.config["lead_seconds"] * 1000.0
        transition = self.config["weather_transition_hours"] * HOUR
        self._schedule("weather", {"TRANSITION": start, "SETTLED": start + transition},
                       {"source": current, "target": target, "seed": rng.getrandbits(63)})
        period = self.config["weather_period_hours"]
        hours = rng.randint(max(1, -(-period * 2 // 3)), period)
        state["weather_change_at"] = start + hours * HOUR
        return f"weather {current} -> {target}, next change in {hours} h"

    def _event(self, now, state, name, frequency_key, seconds_key, other):
        _, timeline = self._read(name)
        planned = state.get(name + "_at")
        if timeline is not None and planned is not None and timeline["times"]["WARNING"] == planned:
            if now < timeline["times"]["ENDED"]:
                return None  # scheduled or running
            last_end = timeline["times"]["ENDED"]
        elif timeline is not None and now < timeline["times"]["ENDED"]:
            state[name + "_at"] = timeline["times"]["WARNING"]  # an administrator's one
            return None
        else:
            last_end = timeline["times"]["ENDED"] if timeline else now
        rng = self._rng(state, name)
        frequency = float(self.config[frequency_key])
        start = max(now + self.config["lead_seconds"] * 1000.0,
                    last_end + rng.uniform(frequency / 2, frequency) * HOUR)
        length = float(self.config[seconds_key]) * 1000.0
        # Never together with the other event, nor right after it.
        _, other_timeline = self._read(other)
        gap = self.config["event_gap_hours"] * HOUR
        if other_timeline is not None:
            begin, end = other_timeline["times"]["WARNING"], other_timeline["times"]["ENDED"]
            if start < end + gap and start + length + gap > begin:
                start = end + gap
        times = {"WARNING": start, "ACTIVE": start + length * 0.25, "PEAK": start + length * 0.6,
                 "ENDED": start + length}
        self._schedule(name, times, {"intensity": 100, "seed": rng.getrandbits(63)})
        state[name + "_at"] = start
        return f"{name} at +{(start - now) / HOUR:.1f} h"

    def _event_emission(self, now, state):
        return self._event(now, state, "emission", "emission_frequency_hours", "emission_seconds", "psi_storm")

    def _event_psi(self, now, state):
        return self._event(now, state, "psi_storm", "psi_storm_frequency_hours", "psi_storm_seconds", "emission")


__all__ = ["Director", "DEFAULTS", "Timelines"]
