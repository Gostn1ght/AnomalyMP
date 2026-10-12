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
from lostzone.__main__ import create_config, create_writer_config, main
from lostzone.http import Credentials


class WriterBindingTest(unittest.TestCase):
    def test_export_is_one_map_only_and_preserves_private_master(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon", "garbage"], world_id=71, seed=0)
            original = config_path.read_bytes()
            config = json.loads(original)
            for location in ("cordon", "garbage"):
                destination = Path(folder) / "maps" / ("netcoop_world_writer_" + location + ".json")
                create_writer_config(config_path, destination, location)
                content = destination.read_bytes()
                result = json.loads(content)
                self.assertLess(len(content), 4096)
                self.assertEqual((1, "writer", "127.0.0.1", 71, 0, location),
                                 tuple(result[k] for k in ("schema", "mode", "host", "master_world_id", "master_world_seed", "location")))
                principal = Credentials(config["credentials"]).authenticate("Bearer " + result["token"])
                self.assertEqual(("location", (location,)), (principal.role, principal.locations))
                for actor, entry in config["credentials"].items():
                    if actor != "location:" + location:
                        self.assertNotIn(entry["token"].encode(), content)
                self.assertNotIn(config["signing_key"].encode(), content)
                create_writer_config(config_path, destination, location)
                self.assertEqual(content, destination.read_bytes())
            self.assertEqual(original, config_path.read_bytes())
            self.assertFalse((Path(folder) / "world.sqlite").exists())

    def test_invalid_scopes_and_names_do_not_create_files(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            create_config(config_path, ["cordon"], world_id=71, seed=0)
            for location in ("../cordon", "cordon:other", "", "unknown", "a" * 65):
                dest = Path(folder) / "new" / "netcoop_world_writer_unknown.json"
                with self.assertRaises(Invalid):
                    create_writer_config(config_path, dest, location)
                self.assertFalse(dest.parent.exists())
            config = json.loads(config_path.read_bytes())
            config["credentials"]["location:cordon"]["locations"].append("garbage")
            config_path.write_text(json.dumps(config))
            with self.assertRaises(Invalid):
                create_writer_config(config_path, Path(folder) / "netcoop_world_writer_cordon.json", "cordon")

    def test_existing_different_file_requires_explicit_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            create_config(config, ["cordon"], world_id=71, seed=0)
            dest = Path(folder) / "netcoop_world_writer_cordon.json"
            dest.write_bytes(b"previous private config")
            with self.assertRaises(FileExistsError):
                create_writer_config(config, dest, "cordon")
            self.assertEqual(b"previous private config", dest.read_bytes())
            create_writer_config(config, dest, "cordon", replace=True)
            self.assertEqual("cordon", json.loads(dest.read_bytes())["location"])
            self.assertFalse(list(Path(folder).glob("*.tmp")))

    def test_cli_exports_without_starting_or_opening_a_world(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            create_config(config, ["cordon"], world_id=71, seed=0)
            dest = Path(folder) / "netcoop_world_writer_cordon.json"
            args = ["lostzone", "writer-config", "--config", str(config), "--destination", str(dest), "--location", "cordon"]
            output = io.StringIO()
            with patch.object(sys, "argv", args), patch("lostzone.__main__.Store", side_effect=AssertionError("unexpected world open")), contextlib.redirect_stdout(output):
                main()
            self.assertEqual("", output.getvalue())
            self.assertEqual("writer", json.loads(dest.read_bytes())["mode"])
            with patch.object(sys, "argv", args + ["--location", "garbage"]), self.assertRaises(Invalid):
                main()
