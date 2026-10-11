"""Master identity bootstrap without launching a listener or game process."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Conflict, Invalid, Store, World
from lostzone.__main__ import create_config, main


class MasterConfigTest(unittest.TestCase):
    def test_explicit_u64_identity_and_calendar_survive_durable_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            create_config(path, ["cordon"], world_id=2**64-1, seed=2**64-1,
                          initial_ms=61_364_764_800_000, scale=3)
            original = path.read_bytes()
            config = json.loads(original)
            bootstrap = {key: config[key] for key in ("world_id", "seed", "initial_ms", "scale")}
            ticks = [0]
            database = path.parent / config["database"]
            with contextlib.closing(Store(database)) as store:
                world = World(store, **bootstrap, monotonic=lambda: ticks[0])
                self.assertEqual((2**64-1, 2**64-1), (world.world_id, world.seed))
                self.assertEqual(bootstrap["initial_ms"], world.now())
                ticks[0] += 1_000_000_000
                world.set_scale("admin", uuid.uuid4().hex, 6)
                world.sample()
                calendar = world.now()
            ticks[0] = 99_000_000_000
            with contextlib.closing(Store(database)) as store:
                world = World(store, **bootstrap, monotonic=lambda: ticks[0])
                self.assertEqual(calendar, world.now(), "initial calendar cannot overwrite a saved world")
                self.assertEqual(6, world.sample()["time_scale"], "initial scale cannot overwrite the saved scale")
                self.assertEqual(2, store.epoch)
                self.assertEqual((2**64-1, 2**64-1), (world.world_id, world.seed))
            self.assertEqual(original, path.read_bytes(), "credentials/config remain unchanged")
            for changed in ({"world_id": 42}, {"seed": 17}):
                with contextlib.closing(Store(database)) as store:
                    with self.assertRaises(Conflict):
                        World(store, **(bootstrap | changed))
                    self.assertIsNone(store.epoch)
                    self.assertEqual(2, store.db.execute("SELECT epoch FROM world").fetchone()[0])

    def test_invalid_bootstrap_creates_no_credentials_or_parent_directory(self):
        invalid = [{"world_id": 42}, {"seed": 17},
                   {"world_id": 0, "seed": 0}, {"world_id": 2**64, "seed": 0},
                   {"world_id": True, "seed": 0}, {"world_id": 42, "seed": -1},
                   {"world_id": 42, "seed": 2**64}, {"world_id": 42, "seed": False},
                   {"initial_ms": -1}, {"initial_ms": float("nan")},
                   {"initial_ms": 2**53}, {"scale": 0}, {"scale": float("inf")}, {"scale": 1001}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "new" / "config.json"
            for options in invalid:
                with self.subTest(options=options), self.assertRaises(Invalid):
                    create_config(path, ["cordon"], **options)
                self.assertFalse(path.parent.exists())

    def test_cli_options_are_init_only_and_do_not_open_the_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            args = ["lostzone", "init", "--config", str(path), "--world-id", str(2**64-1),
                    "--seed", "0", "--initial-ms", "1000", "--scale", "6"]
            with patch.object(sys, "argv", args), patch("lostzone.__main__.Store", side_effect=AssertionError("unexpected database open")), contextlib.redirect_stdout(io.StringIO()):
                main()
            config = json.loads(path.read_bytes())
            self.assertEqual((2**64-1, 0, 1000, 6),
                             tuple(config[key] for key in ("world_id", "seed", "initial_ms", "scale")))
            original = path.read_bytes()
            for mode in ("serve", "console", "bridge-config"):
                with patch.object(sys, "argv", ["lostzone", mode, *args[2:]]), patch("lostzone.__main__.run") as run:
                    with self.assertRaises(Invalid):
                        main()
                    run.assert_not_called()
            with self.assertRaises(Invalid):
                create_config(path, [], world_id=42, seed=17)
            self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
