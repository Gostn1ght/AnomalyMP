import io
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
