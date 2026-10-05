import http.client
import json
from pathlib import Path
import socket
import subprocess
import queue
import sys
import tempfile
import threading
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Invalid
from lostzone.http import Credentials, Dispatcher, RateLimit, Server
from lostzone.__main__ import create_config, create_bridge_config


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "world.db")
        self.world = World(self.store)
        self.credentials = Credentials({
            "admin": {"role": "admin", "token": "a" * 48},
            "cordon-server": {"role": "location", "token": "b" * 48, "locations": ["cordon"]},
            "garbage-server": {"role": "location", "token": "c" * 48, "locations": ["garbage"]},
            "engine-observer":{"role":"observer","token":"d"*48,"locations":[]}})
        self.server = Server(("127.0.0.1", 0), Dispatcher(self.world, b"key-" * 8), self.credentials, max_workers=2)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.close()
        self.folder.cleanup()

    def call(self, method, path, body=None, token="b" * 48, raw=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        request_headers = {"Content-Type": "application/json"}
        if token is not None:
            request_headers["Authorization"] = "Bearer " + token
        request_headers.update(headers or {})
        data = raw if raw is not None else (json.dumps(body) if body is not None else None)
        try:
            connection.request(method, path, data, request_headers)
            response = connection.getresponse()
            content = response.read()
            return response.status, json.loads(content) if content else {}
        finally:
            connection.close()

    def command(self, operation, args, token="b" * 48, command_id=None):
        return self.call("POST", "/v1/command", {"command_id": command_id or uuid.uuid4().hex,
                                               "operation": operation, "arguments": args}, token)

    def test_authentication_and_no_client_assigned_principal(self):
        self.assertEqual(self.call("GET", "/v1/clock", token=None)[0], 401)
        self.assertEqual(self.call("GET", "/v1/clock", token="x" * 48)[0], 401)
        status, result = self.command("location_claim", {"location": "cordon"})
        self.assertEqual(status, 200)
        self.assertEqual(result["result"]["owner"], "cordon-server")
        self.assertEqual(self.command("location_claim", {"actor": "admin", "location": "cordon"})[0], 400)
        self.assertEqual(self.command("location_claim", {"location": "garbage"})[0], 403)
        self.assertEqual(self.command("world_scale", {"value": 1})[0], 403)
        self.assertEqual(self.command("stash_visit", {})[0], 403)
        self.assertEqual(self.command("offline_contacts", {"location":"cordon","horizon_ms":1000,"seed":17})[0],403)
        self.assertEqual(self.command("offline_hazard", {})[0],403)
        self.assertEqual(self.command("offline_hazards", {})[0],403)
        self.assertEqual(self.command("offline_plan", {})[0],403)
        self.assertEqual(self.command("quest_reconcile", {})[0],403)
        self.assertEqual(self.command("trade", {"location": "garbage"})[0], 403)
        self.assertEqual(self.call("GET", "/v1/events")[0], 404)

    def test_observer_bridge_credential_cannot_claim_or_mutate_world(self):
        self.assertEqual(self.call("GET","/v1/bootstrap",token="d"*48)[0],200)
        for operation,args in (("world_scale",{"value":1}),("location_claim",{"location":"cordon"}),
                               ("entity_create",{}),("trade",{}),("offline_combat",{}),("offline_contacts",{}),("offline_hazard",{}),("offline_hazards",{}),("offline_plan",{}),("quest_reconcile",{})):
            self.assertEqual(self.command(operation,args,token="d"*48)[0],403)

    def test_duplicate_command_over_real_http_and_contract_rejection(self):
        key = uuid.uuid4().hex
        first = self.command("location_claim", {"location": "cordon"}, command_id=key)
        self.assertEqual(self.command("location_claim", {"location": "cordon"}, command_id=key), first)
        self.assertEqual(self.command("location_claim", {"location": "cordon", "capacity": 1}, command_id=key)[0], 409)
        self.assertEqual(self.call("POST", "/v1/command", raw='{"command_id":"x","command_id":"y"}')[0], 400)
        self.assertEqual(self.call("POST", "/v1/command", raw='{"value":NaN}')[0], 400)
        self.assertEqual(self.call("POST", "/v1/command", raw='x' * 65537)[0], 413)
        self.assertEqual(self.call("POST", "/v1/command", raw='{}', headers={"Content-Type": "text/plain"})[0], 400)
        self.assertEqual(self.call("POST", "/v1/command", raw='{}', headers={"Transfer-Encoding": "chunked"})[0], 400)

    def test_clock_admin_snapshot_and_read_scope(self):
        status, clock = self.call("GET", "/v1/clock")
        self.assertEqual(status, 200)
        self.assertEqual(clock["result"]["world_id"], self.world.world_id)
        self.assertEqual(self.command("world_scale", {"value": 2}, token="a" * 48)[0], 200)
        self.assertEqual(self.command("quest_reconcile", {}, token="a"*48)[0],200)
        self.assertEqual(self.call("POST", "/v1/snapshot", {}, token="a" * 48)[0], 200)
        self.assertEqual(self.call("POST", "/v1/snapshot", {})[0], 404)
        self.assertEqual(self.call("GET", "/v1/location?id=garbage&fence=1")[0], 403)
        self.server.ready.clear()
        self.assertEqual(self.call("GET", "/v1/clock")[0], 503)

    def test_early_rejection_delivers_response_with_an_unread_post_body(self):
        for _ in range(8):
            self.assertEqual(self.call("POST", "/v1/command", raw='{}', token=None)[0],401)
            self.assertEqual(self.call("POST", "/v1/command", raw='{}', headers={"Content-Type":"text/plain"})[0],400)
            self.assertEqual(self.call("POST", "/v1/command", raw='x'*65537)[0],413)

    def test_request_backpressure_rate_and_worker_bound(self):
        self.server.rate_limit = RateLimit(rate=0, burst=1)
        self.assertEqual(self.call("GET", "/v1/clock")[0], 200)
        self.assertEqual(self.call("GET", "/v1/clock")[0], 429)
        self.server.rate_limit = RateLimit()
        blockers = []
        try:
            for _ in range(2):
                sock = socket.create_connection(self.server.server_address, timeout=2)
                sock.sendall(("POST /v1/command HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " + "b" * 48 +
                              "\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n").encode("ascii"))
                blockers.append(sock)
            # The two requests wait for a body. A third connection receives
            # overload rather than allocating an unbounded worker/SQL queue.
            for _ in range(20):
                status, _ = self.call("GET", "/v1/clock")
                if status == 503:
                    break
                time.sleep(.01)
            self.assertEqual(status, 503)
        finally:
            for sock in blockers:
                sock.close()

    def test_private_configuration_is_stable_and_loopback_is_enforced(self):
        path = Path(self.folder.name) / "config.json"
        create_config(path, ["cordon", "garbage"])
        original = path.read_bytes()
        config = json.loads(original)
        self.assertEqual(len(config["signing_key"]), 64)
        Credentials(config["credentials"])
        with self.assertRaises(Invalid):
            create_config(path, ["new"])
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(Invalid):
            Server(("0.0.0.0", 38477), self.server.dispatcher, self.credentials)

    def test_native_bridge_config_exports_only_observer_and_never_replaces_credentials(self):
        config_path = Path(self.folder.name)/"backend.json"
        create_config(config_path,["cordon"])
        config = json.loads(config_path.read_text())
        destination = Path(self.folder.name)/"userdata"/"netcoop_world_bridge.json"
        create_bridge_config(config_path,destination)
        result = json.loads(destination.read_text())
        self.assertEqual((result["host"],result["mode"]),("127.0.0.1","shadow"))
        self.assertEqual(result["token"],config["credentials"]["observer:engine"]["token"])
        self.assertNotEqual(result["token"],config["credentials"]["admin"]["token"])
        with self.assertRaises(FileExistsError):
            create_bridge_config(config_path,destination)
        config["credentials"]["observer:engine"]["role"]="admin"
        config_path.write_text(json.dumps(config))
        with self.assertRaises(Invalid):
            create_bridge_config(config_path,Path(self.folder.name)/"other"/"netcoop_world_bridge.json")

    def test_real_cli_service_restart_and_private_bootstrap(self):
        folder = Path(self.folder.name) / "service"
        config_path = folder / "config.json"
        create_config(config_path, ["cordon"])
        config = json.loads(config_path.read_text(encoding="utf-8"))
        token = config["credentials"]["location:cordon"]["token"]
        samples = []
        for _ in range(2):
            process = subprocess.Popen([sys.executable, "-m", "lostzone", "serve", "--config", str(config_path), "--port", "0"],
                                       cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            lines = queue.Queue()
            reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()))
            reader.start()
            try:
                line = lines.get(timeout=10)
                self.assertIn("World listening", line)
                self.assertNotIn(token, line)
                port = int(line.split("127.0.0.1:")[1].split(";")[0])
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("GET", "/v1/bootstrap", headers={"Authorization": "Bearer " + token})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                samples.append(json.loads(response.read())["result"])
                connection.close()
            finally:
                process.terminate()
                process.wait(timeout=10)
                reader.join(timeout=10)
                process.stdout.close()
                process.stderr.close()
        self.assertEqual(samples[0]["clock"]["world_id"], samples[1]["clock"]["world_id"])
        self.assertEqual(samples[1]["clock"]["authority_epoch"], samples[0]["clock"]["authority_epoch"] + 1)


if __name__ == "__main__":
    unittest.main()
