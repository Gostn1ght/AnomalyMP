"""Export read-only master bindings without accessing existing world databases."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Invalid
from lostzone.__main__ import create_bridge_config, create_config, main


class BridgeBindingTest(unittest.TestCase):
    def test_distinct_checkpoint_scopes_export_one_master_without_privileged_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon", "garbage"], world_id=2**64-1, seed=0)
            original = config_path.read_bytes()
            config = json.loads(original)
            for location, local_id, seed in (("cordon", 900, 17), ("garbage", 901, 18)):
                destination = Path(folder) / location / "netcoop_world_bridge.json"
                create_bridge_config(config_path, destination, local_world_id=local_id, local_seed=seed, location=location)
                content = destination.read_bytes()
                result = json.loads(content)
                self.assertEqual((2, "shadow", 2**64-1, 0, local_id, seed, location),
                                 tuple(result[key] for key in ("schema", "mode", "master_world_id", "master_world_seed",
                                                              "local_world_id", "local_world_seed", "location")))
                self.assertEqual(config["credentials"]["observer:engine"]["token"], result["token"])
                self.assertNotIn(config["credentials"]["admin"]["token"].encode(), content)
                self.assertNotIn(config["credentials"]["location:" + location]["token"].encode(), content)
                self.assertNotIn(config["signing_key"].encode(), content)
                with self.assertRaises(FileExistsError):
                    create_bridge_config(config_path, destination, local_world_id=local_id, local_seed=seed, location=location)
                self.assertEqual(content, destination.read_bytes())
            self.assertEqual(original, config_path.read_bytes())
            self.assertFalse((Path(folder) / "world.sqlite").exists())

    def test_invalid_or_incomplete_binding_leaves_no_file_or_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon"], world_id=123, seed=17)
            destination = Path(folder) / "new" / "netcoop_world_bridge.json"
            invalid = [{"local_world_id": 900}, {"local_seed": 0}, {"location": "cordon"},
                       {"local_world_id": 0, "local_seed": 0, "location": "cordon"},
                       {"local_world_id": 2**64, "local_seed": 0, "location": "cordon"},
                       {"local_world_id": 900, "local_seed": False, "location": "cordon"},
                       {"local_world_id": 900, "local_seed": -1, "location": "cordon"},
                       {"local_world_id": 900, "local_seed": 0, "location": "garbage"},
                       {"local_world_id": 900, "local_seed": 0, "location": "bad\nmap"}]
            for options in invalid:
                with self.subTest(options=options), self.assertRaises(Invalid):
                    create_bridge_config(config_path, destination, **options)
                self.assertFalse(destination.parent.exists())
            config = json.loads(config_path.read_bytes())
            del config["world_id"]
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(Invalid):
                create_bridge_config(config_path, destination, local_world_id=900, local_seed=0, location="cordon")
            self.assertFalse(destination.parent.exists())

    def test_cli_binding_flags_are_bridge_only_and_bind_one_location(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon", "garbage"], world_id=123, seed=17)
            destination = Path(folder) / "netcoop_world_bridge.json"
            options = ["--config", str(config_path), "--local-world-id", "900", "--local-seed", "0", "--location", "cordon"]
            with patch.object(sys, "argv", ["lostzone", "bridge-config", *options, "--destination", str(destination)]), patch("lostzone.__main__.Store", side_effect=AssertionError("unexpected database open")), contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertEqual(2, json.loads(destination.read_bytes())["schema"])
            for mode in ("init", "serve", "console"):
                with patch.object(sys, "argv", ["lostzone", mode, *options]), patch("lostzone.__main__.run") as run:
                    with self.assertRaises(Invalid):
                        main()
                    run.assert_not_called()
            with patch.object(sys, "argv", ["lostzone", "bridge-config", *options, "--location", "garbage", "--destination", str(Path(folder) / "new" / destination.name)]):
                with self.assertRaises(Invalid):
                    main()
            self.assertFalse((Path(folder) / "new").exists())

    def test_legacy_export_retains_exact_same_world_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon"])
            destination = Path(folder) / "netcoop_world_bridge.json"
            create_bridge_config(config_path, destination)
            result = json.loads(destination.read_bytes())
            self.assertEqual({"schema", "mode", "host", "port", "token"}, set(result))
            self.assertEqual(1, result["schema"])


if __name__ == "__main__":
    unittest.main()
