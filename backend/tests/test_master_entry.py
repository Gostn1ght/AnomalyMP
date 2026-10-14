import io
import contextlib
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from master_entry import AuditStream


class MasterEntryTest(unittest.TestCase):
    def test_packaged_native_import_dry_run_and_durable_stage(self):
        import base64
        import json
        import sqlite3
        from test_native_save import native_fixture
        executable = os.environ.get("LOSTZONE_MASTER_TEST_EXE")
        command = [executable] if executable else [sys.executable, str(Path(__file__).resolve().parents[1] / "master_entry.py")]
        with tempfile.TemporaryDirectory(prefix="master migration test ") as temporary:
            root = Path(temporary)
            config = root / "private config.json"
            subprocess.run([*command, "init", "--config", str(config), "--location", "cordon", "--world-id", "42", "--seed", "7"],
                           check=True, capture_output=True, timeout=60)
            original = config.read_bytes()
            save = root / "netcoop_character_alice_1.bin"
            save.write_bytes(native_fixture())
            args = [*command, "player-migration", "--config", str(config), "--source", str(root),
                    "--location", "cordon", "--world-id", "42", "--seed", "7"]
            dry = subprocess.run(args, check=True, capture_output=True, text=True, timeout=60)
            self.assertEqual(json.loads(dry.stdout)["validated"], 1)
            self.assertFalse((root / "world.sqlite").exists())
            subprocess.run([*command, "console", "--config", str(config), "--port", "0"], input="quit\n",
                           check=True, capture_output=True, text=True, timeout=60)
            committed = subprocess.run([*args, "--commit-import"], check=True, capture_output=True, text=True, timeout=60)
            self.assertEqual(json.loads(committed.stdout)["staged"], 1)
            with contextlib.closing(sqlite3.connect(root / "world.sqlite")) as db:
                raw = db.execute("SELECT payload_base64 FROM native_player_import").fetchone()[0]
                self.assertEqual(base64.b64decode(raw), save.read_bytes())
                self.assertEqual(db.execute("SELECT COUNT(*) FROM player_session").fetchone()[0], 0)
            self.assertEqual(config.read_bytes(), original)
            self.assertNotIn("alice", dry.stdout + committed.stdout)

    def test_split_sensitive_lines_are_redacted_without_delaying_console(self):
        console, log = io.StringIO(), io.StringIO()
        stream = AuditStream(console, log, threading.RLock())
        stream.write("\x1b[32mmaster > \x1b[0mstatus\n")
        stream.write("signing_")
        stream.flush()
        stream.write("key=fixture-private-value\n")
        stream.write("Authorization: fixture-private-value")
        stream.finish()
        self.assertNotIn("fixture-private-value", log.getvalue())
        self.assertNotIn("\x1b", log.getvalue())
        self.assertIn("master > status", log.getvalue())
        self.assertEqual(log.getvalue().count("[redacted sensitive diagnostic line]"), 2)
        self.assertIn("signing_key=fixture-private-value", console.getvalue())

    def test_console_creates_durable_database_and_private_log_with_spaces(self):
        executable = os.environ.get("LOSTZONE_MASTER_TEST_EXE")
        command = [executable] if executable else [sys.executable, str(Path(__file__).resolve().parents[1] / "master_entry.py")]
        with tempfile.TemporaryDirectory(prefix="master console test ") as temporary:
            config = Path(temporary) / "private config.json"
            subprocess.run([*command, "init", "--config", str(config), "--location", "l01_escape", "--location", "k00_marsh"],
                           check=True, capture_output=True, timeout=60)
            result = subprocess.run([*command, "console", "--config", str(config), "--port", "0"],
                                    input="status\nquit\n", text=True, encoding="utf-8", errors="replace",
                                    capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Lost Zone World listening on 127.0.0.1:", result.stdout)
            log = config.parent / "logs" / "master.log"
            self.assertTrue(log.is_file())
            self.assertIn("Lost Zone World listening", log.read_text(encoding="utf-8"))
            self.assertTrue(list(config.parent.glob("*.sqlite*")))
            # Generated credentials remain in this temporary private config only.
            import json
            data = json.loads(config.read_text(encoding="utf-8"))
            outputs = result.stdout + result.stderr + log.read_text(encoding="utf-8")
            self.assertNotIn(data["signing_key"], outputs)
            for account in data["credentials"].values():
                self.assertNotIn(account["token"], outputs)


if __name__ == "__main__":
    unittest.main()
