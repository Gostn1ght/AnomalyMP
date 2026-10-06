import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid
from lostzone.scheduler import Scheduler
from lostzone.timelines import Timelines


def uid():
    return uuid.uuid4().hex


class TimelineTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.ns = 0
        self.open()

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=71, seed=42, scale=1, monotonic=lambda: self.ns)
        self.timelines = Timelines(self.world)
        self.scheduler = self.timelines.scheduler

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def state(self, name):
        return self.world.bootstrap_snapshot()["states"][name]

    def test_world_state_cas_bootstrap_is_consistent_and_clock_highwater(self):
        key = uid()
        result = self.world.set_state("admin", key, "factions", 0, {"duty": {"territory": "rostok"}})
        self.assertEqual(self.world.set_state("admin", key, "factions", 0, {"duty": {"territory": "rostok"}}), result)
        with self.assertRaises(Conflict):
            self.world.set_state("admin", uid(), "factions", 0, {})
        bootstrap = self.world.bootstrap_snapshot()
        self.assertEqual(bootstrap["clock"]["revision"], bootstrap["state_revision"])
        self.assertEqual(bootstrap["event_watermark"], self.store.events()[-1]["sequence"])
        self.assertEqual(bootstrap["states"]["factions"]["version"], 1)

    def test_weather_analytic_blend_and_replacement_cancels_old_events(self):
        first, second = uid(), uid()
        self.timelines.schedule("admin", uid(), "weather", first, 0,
                                {"TRANSITION": 100, "SETTLED": 500},
                                {"source": "clear", "target": "rain", "seed": 42})
        preview = Timelines.evaluate("weather", self.state("weather")["state"], 300)
        self.assertEqual((preview["phase"], preview["blend"]), ("TRANSITION", .5))
        self.timelines.schedule("admin", uid(), "weather", second, 1,
                                {"TRANSITION": 200, "SETTLED": 400},
                                {"source": "clear", "target": "fog", "seed": 99})
        self.ns = 600_000_000
        self.assertEqual(self.scheduler.run_due(limit=64, budget_ms=1000), 4)
        state = self.state("weather")
        self.assertEqual((state["state"]["timeline_id"], state["state"]["phase"], state["version"]), (second, "SETTLED", 4))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='CANCELLED'").fetchone()[0], 2)

    def test_emission_restart_in_peak_and_end_once(self):
        event_id = uid()
        self.timelines.schedule("admin", uid(), "emission", event_id, 0,
                                {"WARNING": 100, "ACTIVE": 200, "PEAK": 300, "ENDED": 400},
                                {"intensity": .8, "seed": 123})
        self.ns = 350_000_000
        self.assertEqual(self.scheduler.run_due(limit=64, budget_ms=1000), 3)
        self.world.sample()
        self.store.close()
        self.ns = 10_000_000_000
        self.open()
        state = self.state("emission")["state"]
        self.assertEqual(Timelines.evaluate("emission", state, self.world.now())["phase"], "PEAK")
        self.ns += 100_000_000
        self.assertEqual(self.scheduler.run_due(limit=64, budget_ms=1000), 1)
        self.assertEqual(self.scheduler.run_due(limit=64, budget_ms=1000), 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='APPLIED'").fetchone()[0], 4)
        self.assertEqual(self.state("emission")["state"]["phase"], "ENDED")

    def test_catchup_is_bounded_by_events_and_late_event_time_does_not_rollback_clock(self):
        self.timelines.schedule("admin", uid(), "emission", uid(), 0,
                                {"WARNING": 100, "ACTIVE": 200, "PEAK": 300, "ENDED": 400},
                                {"intensity": 1, "seed": 123})
        self.ns = 7 * 3600 * 1_000_000_000
        self.world.sample()
        floor = self.world.now()
        self.assertEqual(self.scheduler.run_due(limit=2, budget_ms=1000), 2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='PENDING'").fetchone()[0], 2)
        self.assertEqual(self.scheduler.run_due(limit=2, budget_ms=1000), 2)
        self.store.close()
        self.open()
        self.assertEqual(self.world.now(), floor)
        self.assertEqual(self.state("emission")["state"]["phase"], "ENDED")

    def test_phase_failure_rolls_back_state_event_and_application(self):
        self.timelines.schedule("admin", uid(), "weather", uid(), 0,
                                {"TRANSITION": 100, "SETTLED": 200},
                                {"source": "clear", "target": "rain", "seed": 0})
        original = self.scheduler.handlers["TimelinePhase"]
        def fail(tx, event):
            original(tx, event)
            raise RuntimeError("injected failure before phase commit")
        self.scheduler.handlers["TimelinePhase"] = fail
        self.ns = 100_000_000
        with self.assertRaises(RuntimeError):
            self.scheduler.run_due()
        self.assertEqual(self.state("weather")["state"]["phase"], "SCHEDULED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='APPLIED'").fetchone()[0], 0)
        self.scheduler.handlers["TimelinePhase"] = original
        self.assertEqual(self.scheduler.run_due(budget_ms=1000), 1)

    def test_invalid_schedule_and_id_reuse(self):
        with self.assertRaises(Invalid):
            self.timelines.schedule("admin", uid(), "emission", uid(), 0,
                                    {"WARNING": 100, "ACTIVE": 100, "PEAK": 300, "ENDED": 400},
                                    {"intensity": 1, "seed": 0})
        event_id = uid()
        self.timelines.schedule("admin", uid(), "weather", event_id, 0,
                                {"TRANSITION": 100, "SETTLED": 200},
                                {"source": "clear", "target": "rain", "seed": 0})
        with self.assertRaises(Conflict):
            self.timelines.schedule("admin", uid(), "weather", event_id, 1,
                                    {"TRANSITION": 300, "SETTLED": 400},
                                    {"source": "clear", "target": "rain", "seed": 0})


if __name__ == "__main__":
    unittest.main()
