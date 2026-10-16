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
    def test_packaged_player_admission_is_read_only_and_bound_to_runtime(self):
        import base64
        import hashlib
        import http.client
        import json
        import re
        import sqlite3
        import time
        import uuid
        from urllib.parse import urlencode
        from lostzone.native_save import identity
        from test_native_save import native_fixture
        executable = os.environ.get("LOSTZONE_MASTER_TEST_EXE")
        command = [executable] if executable else [sys.executable, str(Path(__file__).resolve().parents[1] / "master_entry.py")]
        with tempfile.TemporaryDirectory(prefix="master admission test ") as temporary:
            root = Path(temporary)
            config = root / "private config.json"
            subprocess.run([*command, "init", "--config", str(config), "--location", "cordon", "--world-id", "42", "--seed", "7"],
                           check=True, capture_output=True, timeout=60)
            original = config.read_bytes()
            credential = json.loads(original)["credentials"]["location:cordon"]["token"]
            instance = uuid.uuid4().hex
            with (root / "stdout.log").open("wb") as output, (root / "stderr.log").open("wb") as errors:
                process = subprocess.Popen([*command, "console", "--config", str(config), "--port", "0"],
                    stdin=subprocess.PIPE, stdout=output, stderr=errors, text=True, encoding="utf-8",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    deadline, port = time.monotonic() + 30, None
                    while time.monotonic() < deadline:
                        self.assertIsNone(process.poll(), "isolated admission master exited before readiness")
                        match = re.search(rb"listening on 127\.0\.0\.1:(\d+)", (root / "stdout.log").read_bytes())
                        if match:
                            port = int(match[1])
                            break
                        time.sleep(.05)
                    self.assertIsNotNone(port, "isolated admission master readiness timeout")
                    epoch = None

                    def call(method, path, body=None, extra=None):
                        headers = {"Authorization": "Bearer " + credential, "Content-Type": "application/json",
                                   "X-LostZone-Instance": instance}
                        if epoch is not None:
                            headers["X-LostZone-World"] = f"42:7:{epoch}"
                        headers.update(extra or {})
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                        try:
                            connection.request(method, path, None if body is None else json.dumps(body), headers)
                            response = connection.getresponse()
                            return response.status, json.loads(response.read())
                        finally:
                            connection.close()

                    def mutate(operation, arguments, command_id=None):
                        status, data = call("POST", "/v1/command", {"command_id": command_id or uuid.uuid4().hex,
                                             "operation": operation, "arguments": arguments})
                        self.assertEqual(status, 200, "isolated admission master command refused")
                        return data["result"]

                    status, clock = call("GET", "/v1/clock")
                    self.assertEqual(status, 200)
                    epoch = clock["result"]["authority_epoch"]
                    fence = mutate("location_claim", {"location": "cordon"})["fence"]
                    path = "/v1/player-admission?" + urlencode(dict(account="pilot", slot=1, location="cordon", fence=fence, epoch=epoch))
                    status, observation = call("GET", path)
                    self.assertEqual((status, observation["result"]["status"]), (200, "ABSENT"))
                    character = identity(42, 7, "pilot", 1)
                    mutate("entity_create", dict(entity_id=character, kind="CHARACTER", location="cordon", fence=fence, account="pilot", state={}))
                    raw = native_fixture(9)
                    digest = hashlib.sha256(raw).hexdigest()
                    upload = mutate("native_save_begin", dict(character_id=character, fence=fence, session_fence=1,
                        entity_version=1, base_revision=0, slot=1, byte_count=len(raw), sha256=digest))["upload_id"]
                    scope = dict(character_id=character, fence=fence, session_fence=1, upload_id=upload)
                    self.assertEqual(call("GET", path)[0], 409)
                    mutate("native_save_append", scope | dict(offset=0, data=base64.b64encode(raw).decode()))
                    command_id = uuid.uuid4().hex
                    saved = mutate("native_save_finish", scope, command_id)
                    self.assertEqual(mutate("native_save_finish", scope, command_id), saved)
                    for _ in range(3):
                        status, observation = call("GET", path)
                        self.assertEqual((status, observation["result"]["status"], observation["result"]["entity_version"]), (200, "ACTIVE", 2))
                        self.assertEqual(observation["result"]["checkpoint"], dict(revision=1, sha256=digest, bytes=len(raw)))
                    status, page = call("GET", "/v1/player-save?" + urlencode(dict(character_id=character, fence=fence, session_fence=1, revision=1)))
                    self.assertEqual(status, 200)
                    self.assertEqual(base64.b64decode(page["result"]["data"]), raw)
                    mutate("session_disconnect", dict(character_id=character, fence=fence, version=2, state={}))
                    status, observation = call("GET", path)
                    self.assertEqual((status, observation["result"]["status"], observation["result"]["session_fence"]), (200, "DISCONNECTED", 2))
                    mutate("session_resume", dict(character_id=character, location="cordon", fence=fence, version=3))
                    status, observation = call("GET", path)
                    self.assertEqual((status, observation["result"]["status"], observation["result"]["entity_version"],
                                      observation["result"]["session_fence"]), (200, "ACTIVE", 4, 3))
                    self.assertEqual(call("GET", path, extra={"X-LostZone-Instance": uuid.uuid4().hex})[0], 409)
                    self.assertEqual(call("GET", path, extra={"X-LostZone-World": f"43:7:{epoch}"})[0], 409)
                finally:
                    if process.poll() is None:
                        try:
                            process.communicate("quit\n", timeout=15)
                        except (subprocess.TimeoutExpired, OSError):
                            process.kill()
                            process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0)
            self.assertEqual(config.read_bytes(), original)
            with contextlib.closing(sqlite3.connect(root / "world.sqlite")) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT version FROM entity WHERE id=?", (character,)).fetchone()[0], 4)
                self.assertEqual(db.execute("SELECT state,fence FROM player_session").fetchone(), ("ACTIVE", 3))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM native_player_save").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM native_player_upload").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM command_result").fetchone()[0], 7)
                self.assertEqual(base64.b64decode(db.execute("SELECT payload_base64 FROM native_player_save").fetchone()[0]), raw)

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
