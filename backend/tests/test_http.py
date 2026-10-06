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
from lostzone import Store, World, Invalid, Unavailable
from lostzone.scheduler import UnavailableHandler
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

    def test_authenticated_route_http_command_discovers_hazard_atomically(self):
        self.server.dispatcher.planner.enable_automatic({"horizon_ms":300000,"radius":1,"max_locations":25,"budget_ms":1000})
        status,claimed=self.command("location_claim",{"location":"cordon"})
        self.assertEqual(status,200);fence=claimed["result"]["fence"]
        npc,trap=uuid.uuid4().hex,uuid.uuid4().hex
        states = ((npc,"NPC",{"position":[0,0,0],"health":1}),
                  (trap,"TRAP",{"position":[5,0,0],"hazard_type":"fire","radius":1,"armed":True,"charges":1,"damage_bp":10000}))
        for entity_id,kind,state in states:
            self.assertEqual(self.command("entity_create",{"entity_id":entity_id,"kind":kind,"location":"cordon","fence":fence,"state":state})[0],200)
        for entity_id,kind,state in reversed(states):
            self.assertEqual(self.command("dehydrate",{"entity_id":entity_id,"location":"cordon","fence":fence,"version":1,
                                                       "captures":{entity_id:{"version":1,"state":state}}})[0],200)
        key=uuid.uuid4().hex
        status,result=self.command("route_start",{"entity_id":npc,"version":2,"points":[[0,0,0],[10,0,0]],"speed_real":1,"seed":42},token="a"*48,command_id=key)
        self.assertEqual(status,200)
        rows=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineHazard'").fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(json.loads(rows[0]["payload"])["hazard_id"],trap)
        source=json.loads(self.store.db.execute("SELECT payload FROM world_event WHERE type='ContactsReplanned' ORDER BY sequence DESC LIMIT 1").fetchone()[0])
        self.assertEqual((source["source_actor"],source["source_command"]),("admin",key))
        self.assertEqual(source["contacts"][0]["event_id"],rows[0]["id"])
        self.assertEqual(result["result"]["id"],npc)

    def test_cached_location_success_is_rejected_over_http_after_lease_takeover(self):
        _,claimed=self.command("location_claim",{"location":"cordon"})
        fence=claimed["result"]["fence"]
        key=uuid.uuid4().hex
        args={"entity_id":uuid.uuid4().hex,"kind":"NPC","location":"cordon","fence":fence,
              "state":{"position":[0,0,0],"health":1}}
        original=self.command("entity_create",args,command_id=key)
        self.assertEqual(original[0],200)
        self.assertEqual(self.command("entity_create",args,command_id=key),original)
        with self.store.transaction() as tx:
            tx.execute("UPDATE location_lease SET expires_ms=0 WHERE location='cordon'")
        _,replacement=self.command("location_claim",{"location":"cordon"},token="a"*48)
        self.assertGreater(replacement["result"]["fence"],fence)
        before=self.store.events()
        self.assertEqual(self.command("entity_create",args,command_id=key)[0],409)
        self.assertEqual(self.store.events(),before)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],1)

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

    def test_recovery_status_is_admin_only_and_remains_readable_while_held(self):
        self.server.worker_failed(RuntimeError("private token "+"z"*48))
        for token,status in ((None,401),("b"*48,403),("d"*48,403),("a"*48,200)):
            self.wait_idle_workers()
            response=self.call("GET","/v1/status",token=token)
            self.assertEqual(response[0],status)
        result=response[1]["result"]
        self.assertFalse(result["admission_ready"])
        self.assertEqual(result["worker_error_type"],"RuntimeError")
        self.assertNotIn("z"*48,json.dumps(result))
        self.assertEqual(self.command("location_claim",{"location":"cordon"},token="a"*48)[0],503)

    def test_partial_catchup_keeps_admission_closed_until_all_due_events_finish(self):
        scheduler=self.server.dispatcher.timelines.scheduler
        scheduler.handlers["ReadinessFixture"]=lambda tx,event:({},True)
        with self.store.transaction() as tx:
            for _ in range(65):
                scheduler.schedule_in(tx,uuid.uuid4().hex,0,"fixture",1,"ReadinessFixture",{})
        self.server.worker_succeeded(0)
        self.assertFalse(self.server.ready.is_set())
        processed=scheduler.run_due(limit=64,budget_ms=1000)
        self.assertEqual(processed,64);self.server.worker_succeeded(processed)
        self.assertFalse(self.server.ready.is_set())
        self.assertEqual(self.call("GET","/v1/bootstrap")[0],503)
        status,result=self.call("GET","/v1/status",token="a"*48)
        self.assertEqual(status,200);self.assertEqual(result["result"]["due_sample_count"],1)
        self.server.worker_succeeded(scheduler.run_due(budget_ms=1000))
        self.assertTrue(self.server.ready.is_set())
        self.assertEqual(self.call("GET","/v1/bootstrap")[0],200)
        self.assertEqual(self.server.recovery_status()["events_processed"],65)

    def test_missing_resolver_status_identifies_held_event_without_disclosing_payload(self):
        scheduler=self.server.dispatcher.timelines.scheduler;event_id=uuid.uuid4().hex
        with self.store.transaction() as tx:
            scheduler.schedule_in(tx,event_id,0,"fixture",1,"MissingResolverFixture",{"private_token":"secret-transfer-token"})
        try:
            scheduler.run_due(budget_ms=1000)
        except UnavailableHandler as error:
            self.server.worker_failed(error)
        else:
            self.fail("missing resolver must hold its event")
        result=self.call("GET","/v1/status",token="a"*48)[1]["result"]
        self.assertEqual(result["worker_error_type"],"UnavailableHandler")
        self.assertEqual(result["oldest_pending"]["id"],event_id)
        self.assertFalse(result["oldest_pending"]["handler_registered"])
        self.assertNotIn("secret-transfer-token",json.dumps(result))
        scheduler.handlers["MissingResolverFixture"]=lambda tx,event:({},True)
        self.server.worker_succeeded(scheduler.run_due(budget_ms=1000))
        self.assertTrue(self.server.ready.is_set())
        self.assertIsNone(self.server.recovery_status()["worker_error_type"])

    def test_recovery_status_samples_bounded_metadata_and_preserves_durable_state(self):
        scheduler=self.server.dispatcher.timelines.scheduler
        with self.store.transaction() as tx:
            for _ in range(1030):
                scheduler.schedule_in(tx,uuid.uuid4().hex,1e9,"fixture",1,"FutureFixture",{"hidden":"payload"})
        before=tuple(self.store.db.execute("SELECT * FROM world").fetchone())
        result=self.call("GET","/v1/status",token="a"*48)[1]["result"]
        self.assertEqual((result["pending_sample_count"],result["pending_has_more"],result["due_sample_count"]),(1024,True,0))
        self.assertEqual(tuple(self.store.db.execute("SELECT * FROM world").fetchone()),before)
        self.assertNotIn("payload",json.dumps(result))

    def test_loaded_due_backlog_is_not_ready_when_a_transport_starts(self):
        scheduler=self.server.dispatcher.timelines.scheduler
        with self.store.transaction() as tx:
            scheduler.schedule_in(tx,uuid.uuid4().hex,0,"fixture",1,"StartupFixture",{})
        second=Server(("127.0.0.1",0),self.server.dispatcher,self.credentials)
        try:
            self.assertFalse(second.ready.is_set())
        finally:
            second.server_close()

    def test_recovery_status_is_available_even_when_monotonic_clock_is_held(self):
        self.server.worker_failed(Unavailable("clock regression"))
        self.world._last_ns+=1_000_000_000_000
        status,response=self.call("GET","/v1/status",token="a"*48)
        self.assertEqual(status,200)
        self.assertIsNone(response["result"]["observed_world_ms"])
        self.assertIsNone(response["result"]["due_sample_count"])
        self.assertFalse(response["result"]["admission_ready"])

    def test_early_rejection_delivers_response_with_an_unread_post_body(self):
        for _ in range(8):
            for expected,args in ((401,{"raw":"{}","token":None}),
                                  (400,{"raw":"{}","headers":{"Content-Type":"text/plain"}}),
                                  (413,{"raw":"x"*65537})):
                # A received response does not mean the bounded worker has
                # finished draining/closing its socket. Isolate delivery from
                # overload admission, rather than relying on OS scheduling.
                self.wait_idle_workers()
                self.assertEqual(self.call("POST", "/v1/command", **args)[0],expected)

    def wait_idle_workers(self):
        acquired=0
        try:
            for _ in range(2):
                self.assertTrue(self.server._slots.acquire(timeout=2),"HTTP worker cleanup did not finish")
                acquired+=1
        finally:
            for _ in range(acquired):
                self.server._slots.release()

    def test_response_delivery_does_not_release_a_worker_before_socket_cleanup(self):
        gate=threading.Event();closing=queue.Queue()
        original=self.server.shutdown_request
        def held_cleanup(request):
            closing.put(True)
            if not gate.wait(2):
                raise AssertionError("cleanup gate was not released")
            original(request)
        self.server.shutdown_request=held_cleanup
        try:
            for _ in range(2):
                self.assertEqual(self.call("GET","/v1/clock")[0],200)
                closing.get(timeout=2)
            # The accept thread also closes overload sockets. Restore its
            # closer while both admitted workers remain at the captured gate.
            self.server.shutdown_request=original
            self.assertEqual(self.call("GET","/v1/clock")[0],503)
        finally:
            self.server.shutdown_request=original
            gate.set()
        self.wait_idle_workers()
        self.assertEqual(self.call("GET","/v1/clock")[0],200)

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
