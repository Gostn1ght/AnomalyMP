"""Public player entry of the master (owner 2026-10-17)."""
import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from lostzone.gateway import Gateway, read_cluster, serve

PLAN = """; comment
[cluster]
max_players = 512
[locations]
k00_marsh = 127.0.0.1:1267
l01_escape = 203.0.113.7:1277 ; public host
bad name = 127.0.0.1:1
l02_garbage = 127.0.0.1:99999
[launch]
k00_marsh = hidden_base
"""


class FakeStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.leases = {}

    @property
    def db(self):
        store = self

        class DB:
            def execute(self, query, args):
                return [(name,) for name, expiry in store.leases.items() if expiry > args[0]]
        return DB()


class FakeWorld:
    ms = 1000

    def real_ms(self):
        return self.ms


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.plan = Path(self.folder.name) / "netcoop_cluster.ltx"
        self.plan.write_text(PLAN, encoding="cp1251")
        self.store, self.world = FakeStore(), FakeWorld()
        self.gateway = Gateway(self.store, self.world, self.plan, rate=3, window=60)

    def tearDown(self):
        self.folder.cleanup()

    def test_plan_keeps_file_order_and_drops_invalid_rows(self):
        self.assertEqual(read_cluster(self.plan), [("k00_marsh", "127.0.0.1", 1267), ("l01_escape", "203.0.113.7", 1277)])
        self.assertEqual(read_cluster(Path(self.folder.name) / "missing.ltx"), [])

    def test_entry_is_the_first_running_location(self):
        self.assertIsNone(self.gateway.entry())
        self.store.leases = {"l01_escape": 5000}
        # A public host in the plan is not sent: the location is on this machine,
        # and a VPN player reaches it at the master's address.
        self.assertEqual(self.gateway.entry(), {"schema": 1, "location": "l01_escape", "host": "", "port": 1277})
        self.store.leases["k00_marsh"] = 5000
        # Loopback in the plan means this machine: the client keeps the master's address.
        self.assertEqual(self.gateway.entry(), {"schema": 1, "location": "k00_marsh", "host": "", "port": 1267})
        self.world.ms = 6000  # both leases expired
        self.assertIsNone(self.gateway.entry())

    def test_rate_limit_per_address(self):
        self.assertTrue(all(self.gateway.allowed("198.51.100.1") for _ in range(3)))
        self.assertFalse(self.gateway.allowed("198.51.100.1"))
        self.assertTrue(self.gateway.allowed("198.51.100.2"))

    def test_http_answers_only_the_entry(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
        stop = threading.Event()
        self.store.leases = {"k00_marsh": 10 ** 12}
        gateway = Gateway(self.store, self.world, self.plan, rate=50, window=60)
        server, thread = serve(gateway, port, stop)
        try:
            def get(method, path):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request(method, path)
                response = connection.getresponse()
                body = json.loads(response.read())
                connection.close()
                return response.status, body
            self.assertEqual(get("GET", "/v1/entry"), (200, {"schema": 1, "location": "k00_marsh", "host": "", "port": 1267}))
            self.assertEqual(get("GET", "/v1/command")[0], 404)
            self.assertEqual(get("POST", "/v1/entry")[0], 405)
            self.store.leases = {}
            self.assertEqual(get("GET", "/v1/entry")[0], 503)
        finally:
            stop.set()
            thread.join(5)


if __name__ == "__main__":
    unittest.main()
