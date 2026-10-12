"""World director: the master plans weather, emissions and psi storms."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World
from lostzone.director import Director, HOUR
from lostzone.timelines import Timelines


class DirectorTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.ns = [1_000_000_000]
        self.open()

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=5, seed=99, initial_ms=1_000_000, scale=10,
                           monotonic=lambda: self.ns[0])
        self.timelines = Timelines(self.world)
        self.director = Director(self.world, self.timelines)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def advance_game(self, ms):
        self.ns[0] += int(ms / 10 * 1_000_000)  # scale 10: game ms -> real ns
        self.timelines.scheduler.run_due(limit=64, budget_ms=1000)

    def state(self, name):
        row = self.store.db.execute("SELECT state FROM world_state WHERE name=?", (name,)).fetchone()
        return json.loads(row[0]) if row else None

    def test_first_pass_plans_everything_once(self):
        lines = self.director.tick()
        self.assertEqual(len(lines), 3, lines)
        weather, emission, psi = self.state("weather"), self.state("emission"), self.state("psi_storm")
        self.assertEqual(weather["parameters"]["source"], "clear")
        now = self.world.now()
        self.assertTrue(12 * HOUR <= emission["times"]["WARNING"] - now <= 24 * HOUR + 60000)
        self.assertTrue(24 * HOUR <= psi["times"]["WARNING"] - now <= 48 * HOUR + 60000 + 4 * HOUR)
        self.assertEqual(self.director.tick(), [])  # nothing new until something is due

    def test_events_never_overlap_and_follow_each_other(self):
        self.director.tick()
        starts = {"emission": [], "psi_storm": []}
        cycles = []
        for _ in range(400):  # 400 game hours
            self.advance_game(HOUR)
            self.director.tick()
            for name in starts:
                s = self.state(name)
                if not starts[name] or starts[name][-1] != (s["times"]["WARNING"], s["times"]["ENDED"]):
                    starts[name].append((s["times"]["WARNING"], s["times"]["ENDED"]))
            cycles.append(self.state("weather")["parameters"]["target"])
        self.assertGreaterEqual(len(starts["emission"]), 12)
        self.assertGreaterEqual(len(starts["psi_storm"]), 6)
        for a in starts["emission"]:
            for b in starts["psi_storm"]:
                self.assertFalse(a[0] < b[1] + 2 * HOUR and b[0] < a[1] + 2 * HOUR, (a, b))
        for prev, nxt in zip(starts["emission"], starts["emission"][1:]):
            self.assertGreaterEqual(nxt[0] - prev[1], 12 * HOUR - 1)
        changes = [b for a, b in zip(cycles, cycles[1:]) if a != b]
        self.assertGreater(len(changes), 50)
        self.assertEqual(set(cycles), {"clear", "partly", "cloudy", "rain", "storm", "foggy"})

    def test_restart_continues_without_replanning(self):
        self.director.tick()
        before = {name: self.state(name)["timeline_id"] for name in ("weather", "emission", "psi_storm")}
        self.store.close()
        self.open()
        self.assertEqual(self.director.tick(), [])
        self.assertEqual(before, {name: self.state(name)["timeline_id"] for name in before})

    def test_engine_bootstrap_carries_all_three(self):
        self.director.tick()
        snapshot = self.world.engine_bootstrap_snapshot()
        self.assertEqual(set(snapshot["states"]), {"weather", "emission", "psi_storm"})
        public = snapshot["states"]["psi_storm"]["state"]
        self.assertEqual(set(public["times"]), {"WARNING", "ACTIVE", "PEAK", "ENDED"})


if __name__ == "__main__":
    unittest.main()
