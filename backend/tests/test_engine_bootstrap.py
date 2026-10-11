import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Invalid
from lostzone.timelines import Timelines


class EngineBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.store = Store(self.path)
        self.world = World(self.store, world_id=71, seed=2**64-1, initial_ms=1500,
                           scale=1, monotonic=lambda: 0)
        self.timelines = Timelines(self.world)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def schedule(self):
        self.timelines.schedule("admin", uuid.uuid4().hex, "weather", uuid.uuid4().hex, 0,
                                {"TRANSITION": 1000, "SETTLED": 2000},
                                {"source": "clear", "target": "rain", "seed": 2**64-1,
                                 "private": "PRIVATE-PARAMETER" + "x" * 100000})

    def test_projection_is_bounded_coherent_and_excludes_unrelated_states_and_parameters(self):
        self.schedule()
        self.world.set_state("admin", uuid.uuid4().hex, "large_private_state", 0,
                             {"payload": "PRIVATE-WORLD-STATE" + "x" * 100000})
        result = self.world.engine_bootstrap_snapshot()
        self.assertEqual(set(result["states"]), {"weather"})
        self.assertEqual(set(result["states"]["weather"]["state"]["parameters"]), {"source", "target", "seed"})
        encoded = json.dumps(result)
        self.assertLess(len(encoded.encode()), 4096)
        self.assertNotIn("PRIVATE-", encoded)
        self.assertEqual(result["clock"]["revision"], result["state_revision"])
        self.assertEqual(result["event_watermark"], self.store.events()[-1]["sequence"])
        self.assertEqual(result["world_seed"], 2**64-1)
        full = self.world.bootstrap_snapshot()
        self.assertIn("large_private_state", full["states"])
        self.assertIn("private", full["states"]["weather"]["state"]["parameters"])

    def test_restart_keeps_calendar_schedule_watermark_and_raises_only_master_epoch(self):
        self.schedule()
        before = self.world.engine_bootstrap_snapshot()
        self.store.close()
        self.store = Store(self.path)
        self.world = World(self.store, world_id=71, seed=2**64-1, monotonic=lambda: 999999999999)
        after = self.world.engine_bootstrap_snapshot()
        self.assertEqual(after["clock"]["world_ms"], before["clock"]["world_ms"])
        self.assertEqual(after["states"], before["states"])
        self.assertEqual(after["event_watermark"], before["event_watermark"])
        self.assertGreater(after["clock"]["authority_epoch"], before["clock"]["authority_epoch"])

    def test_invalid_known_timeline_fails_without_committing_clock_sample(self):
        self.world.set_state("admin", uuid.uuid4().hex, "weather", 0, {"private": "secret"})
        before = self.store.db.execute("SELECT sequence FROM world").fetchone()[0]
        with self.assertRaises(Invalid):
            self.world.engine_bootstrap_snapshot()
        self.assertEqual(before, self.store.db.execute("SELECT sequence FROM world").fetchone()[0])
        self.assertEqual(self.world.bootstrap_snapshot()["states"]["weather"]["state"], {"private": "secret"})


if __name__ == "__main__":
    unittest.main()
