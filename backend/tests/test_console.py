import contextlib
import io
from pathlib import Path
import signal
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Invalid, Unavailable
from lostzone.console import Console, run_console
from lostzone.http import Credentials, Dispatcher
from lostzone.__main__ import create_config, run


def recovery(dispatcher, ready):
    return {"world": {"world_id": dispatcher.world.world_id, "epoch": dispatcher.store.epoch},
            "admission_ready": ready.is_set(), "due_sample_count": 0,
            "events_processed": 0, "worker_error_type": None}


class ConsoleTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "world.sqlite")
        self.ticks = 0
        self.world = World(self.store, world_id=42, seed=17, initial_ms=1000,
                           monotonic=lambda: self.ticks, wall=lambda: 1_000_000_000)
        dispatcher = Dispatcher(self.world, b"k" * 32)
        credentials = Credentials({"master": {"role": "admin", "token": "a" * 48}})
        ready = threading.Event(); ready.set()
        self.server = SimpleNamespace(dispatcher=dispatcher, credentials=credentials, ready=ready,
                                      recovery_status=lambda: recovery(dispatcher, ready))
        self.stop = threading.Event()
        self.console = Console(self.server, self.stop)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def test_reads_real_registry_without_disclosing_state_or_changing_journal(self):
        before = self.store.db.execute("SELECT COUNT(*) FROM world_event").fetchone()[0]
        for command in ("status", "clock", "locations", "characters", "npcs", "transfers", "events"):
            self.assertTrue(self.console.execute(command))
        self.assertIn("WorldID=42", self.console.execute("status"))
        self.world.claim_location("map-server", uuid.uuid4().hex, "cordon")
        self.server.dispatcher.ownership.create_entity("map-server", uuid.uuid4().hex,
                                                     uuid.uuid4().hex, "NPC", "cordon", 1,
                                                     {"private": "DO-NOT-PRINT"})
        self.assertIn("cordon", self.console.execute("locations"))
        self.assertIn("записей=1", self.console.execute("npcs"))
        count = self.store.db.execute("SELECT COUNT(*) FROM world_event").fetchone()[0]
        self.assertGreater(count, before)
        output = "\n".join(self.console.execute(c) for c in ("status", "locations", "npcs", "events"))
        self.assertNotIn("DO-NOT-PRINT", output)
        self.assertNotIn("a" * 48, output)
        self.assertEqual(count, self.store.db.execute("SELECT COUNT(*) FROM world_event").fetchone()[0])

    def test_scale_uses_real_durable_dispatcher_and_preserves_calendar(self):
        self.ticks = 2_000_000_000
        before = self.world.now()
        self.assertIn("3.0", self.console.execute("scale 3"))
        self.assertEqual(before, self.world.now())
        self.ticks += 1_000_000_000
        self.assertEqual(before + 3000, self.world.now())
        event = self.store.db.execute("SELECT type FROM world_event ORDER BY sequence DESC LIMIT 1").fetchone()
        self.assertEqual("ScaleChanged", event[0])
        self.server.ready.clear()
        with self.assertRaises(Unavailable):
            self.console.execute("scale 6")
        self.assertIn("восстанавливается", self.console.execute("status"))

    def test_registry_summary_is_bounded_and_labels_the_sample(self):
        with self.store.transaction() as tx:
            tx.executemany("INSERT INTO entity VALUES(?,?,?,?,?,1,1,?)",
                           [(f"{i:032x}", "NPC", "cordon", "map-server", 1, '{}') for i in range(1100)])
        output = self.console.execute("npcs")
        self.assertIn("записей=1024", output)
        self.assertIn("Есть ещё записи", output)
        self.assertNotIn("1100", output)

    def test_invalid_commands_fail_without_mutation_or_secret_output(self):
        commands = ("scale nan", "scale inf", "scale 0", "scale -1", "scale 1001",
                    "scale", "scale 1 2", "status extra", "unknown", "x" * 257)
        for command in commands:
            with self.assertRaises((Invalid, ValueError)):
                self.console.execute(command)
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM world_event").fetchone()[0])
        output = []
        lines = iter(["status", "secret password", "quit"])
        run_console(self.server, self.stop, read=lambda _: next(lines), write=output.append)
        self.assertTrue(self.stop.is_set())
        self.assertNotIn("secret password", "\n".join(output))

    def test_admin_is_required_and_stale_epoch_fails_closed(self):
        self.server.credentials = Credentials({"observer": {"role": "observer", "token": "b" * 48}})
        with self.assertRaises(Invalid):
            Console(self.server, self.stop)
        self.store.db.execute("UPDATE world SET epoch=epoch+1")
        with self.assertRaises(Unavailable):
            self.console.execute("locations")

    def test_eof_and_interrupt_request_saved_stop(self):
        for error in (EOFError, KeyboardInterrupt):
            stop = threading.Event()
            def read(_):
                raise error
            run_console(self.server, stop, read=read, write=lambda _: None)
            self.assertTrue(stop.is_set())


class ConsoleLifecycleTest(unittest.TestCase):
    def test_console_lifecycle_uses_same_store_saves_on_quit_and_releases_lock(self):
        # Exercise run()/checkpoint/final-save, replacing only the network
        # listener. No game/server process or production config is launched.
        class Listener:
            closed = False
            def __init__(self, address, dispatcher, credentials):
                self.server_address, self.dispatcher, self.credentials = address, dispatcher, credentials
                self.ready = threading.Event(); self.ready.set()
                self.done = threading.Event()
            def serve_forever(self):
                self.done.wait()
            def shutdown(self):
                self.done.set()
            def server_close(self):
                Listener.closed = True
            def worker_succeeded(self, processed):
                self.ready.set()
            def worker_failed(self, error):
                self.ready.clear()
            def recovery_status(self):
                return recovery(self.dispatcher, self.ready)
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            create_config(config, ["cordon"])
            initial = config.read_bytes()
            prior_signal = signal.getsignal(signal.SIGINT)
            lines = iter(["clock", "scale 2", "quit"])
            def interact(server, stop):
                run_console(server, stop, read=lambda _: next(lines), write=lambda _: None)
            with patch("lostzone.__main__.Server", Listener), patch("lostzone.console.run_console", interact), contextlib.redirect_stdout(io.StringIO()):
                run(config, interactive=True)
            self.assertTrue(Listener.closed)
            self.assertEqual(prior_signal, signal.getsignal(signal.SIGINT))
            self.assertEqual(initial, config.read_bytes(), "console does not replace credentials")
            with contextlib.closing(Store(Path(folder) / "world.sqlite")) as store:
                world = World(store)
                self.assertEqual(2, store.epoch)
                self.assertEqual(2, store.db.execute("SELECT scale FROM world").fetchone()[0])
                self.assertGreaterEqual(world.now(), 0)


if __name__ == "__main__":
    unittest.main()
