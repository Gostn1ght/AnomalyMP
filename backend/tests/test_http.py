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
from unittest.mock import patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Invalid, Unavailable
from lostzone.scheduler import UnavailableHandler
from lostzone.quests import Quests
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

    def relay(self, order, values, token="b" * 48, account="lzadmin", command_id=None):
        headers = {"X-LostZone-Instance": "a" * 32,
                   "X-LostZone-World": f"{self.world.world_id}:{self.world.seed}:{self.store.epoch}"}
        body = {"command_id": command_id or uuid.uuid4().hex, "operation": "admin_relay",
                "arguments": {"account": account, "order": order, "values": values}}
        return self.call("POST", "/v1/command", body, token=token, headers=headers)

    def test_location_relays_an_administrators_world_orders_to_every_map(self):
        self.server.ready.set()
        status, body = self.relay("weather", {"source": "clear", "target": "w_rain2", "transition_s": 60})
        self.assertEqual(status, 200)
        state = self.world.engine_bootstrap_snapshot()["states"]["weather"]["state"]
        self.assertEqual(state["parameters"]["target"], "w_rain2")
        self.assertAlmostEqual(state["times"]["SETTLED"] - state["times"]["TRANSITION"], 60_000, delta=1)
        self.assertEqual(self.relay("emission", {"durations": [30, 60, 90], "intensity": 1})[0], 200)
        self.assertEqual(self.relay("psi_storm", {"durations": [30, 60, 90], "intensity": 1})[0], 200)
        before = self.world.now()
        command_id = uuid.uuid4().hex
        self.assertEqual(self.relay("advance", {"game_s": 3600}, command_id=command_id)[0], 200)
        after = self.world.now()
        self.assertGreaterEqual(after - before, 3_600_000)
        # The same order retried does not move the clock again.
        self.assertEqual(self.relay("advance", {"game_s": 3600}, command_id=command_id)[0], 200)
        self.assertLess(self.world.now() - after, 3_600_000)
        status, body = self.relay("scale", {"value": 20})
        self.assertEqual((status, body["result"]["scale"]), (200, 20))

    def test_world_orders_need_a_location_and_a_known_order(self):
        self.server.ready.set()
        # The administrator credential uses the console; an observer nothing.
        self.assertEqual(self.relay("advance", {"game_s": 60}, token="a" * 48)[0], 403)
        self.assertNotEqual(self.relay("advance", {"game_s": 60}, token="d" * 48)[0], 200)
        self.assertEqual(self.relay("spawn", {"section": "wpn_ak74"})[0], 400)
        self.assertEqual(self.relay("advance", {"game_s": -5})[0], 400)
        self.assertEqual(self.relay("advance", {"game_s": 60, "x": 1})[0], 400)
        self.assertEqual(self.relay("weather", {"source": "clear", "target": "bad target", "transition_s": 1})[0], 400)
        self.assertEqual(self.relay("emission", {"durations": [1, 2], "intensity": 1})[0], 400)
        self.assertEqual(self.relay("advance", {"game_s": 60}, account="")[0], 400)

    def test_master_window_console_is_for_the_administrator_only(self):
        self.server.ready.set()
        status, body = self.call("POST", "/v1/console", {"line": "clock"}, token="a" * 48)
        self.assertEqual(status, 200)
        self.assertIn("Календарь", body["result"]["text"])
        self.assertEqual(self.call("POST", "/v1/console", {"line": "nonsense"}, token="a" * 48)[1]["result"]["text"][:21],
                         "Команда не выполнена ")
        self.assertEqual(self.call("POST", "/v1/console", {"line": "quit"}, token="a" * 48)[0], 400)
        self.assertNotEqual(self.call("POST", "/v1/console", {"line": "clock"})[0], 200)
        self.assertEqual(self.call("POST", "/v1/console", {"line": "clock", "x": 1}, token="a" * 48)[0], 400)

    def command(self, operation, args, token="b" * 48, command_id=None):
        return self.call("POST", "/v1/command", {"command_id": command_id or uuid.uuid4().hex,
                                               "operation": operation, "arguments": args}, token)

    def test_actual_http_native_save_upload_read_and_scope(self):
        import base64
        import hashlib
        from lostzone.native_save import identity
        from lostzone.player_saves import CHUNK
        from test_native_save import native_fixture
        raw = native_fixture(9,progress=b"native task/position/player state"*3000)
        status,result = self.command("location_claim",{"location":"cordon"})
        self.assertEqual(status,200)
        fence = result["result"]["fence"]
        character = identity(self.world.world_id,self.world.seed,"alice",1)
        status,result = self.command("entity_create",{"entity_id":character,"kind":"CHARACTER",
                  "location":"cordon","fence":fence,"state":{},"account":"alice"})
        self.assertEqual(status,200)
        args = {"character_id":character,"fence":fence,"session_fence":1,"entity_version":1,
                "base_revision":0,"slot":1,"byte_count":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
        self.assertEqual(self.command("native_save_begin",args,token="d"*48)[0],403)
        self.assertEqual(self.command("native_save_begin",args,token="a"*48)[0],403)
        self.assertEqual(self.command("native_save_begin",args,token="c"*48)[0],403)
        status,result = self.command("native_save_begin",args)
        self.assertEqual(status,200)
        upload = result["result"]["upload_id"]
        common = {"character_id":character,"fence":fence,"session_fence":1,"upload_id":upload}
        for offset in range(0,len(raw),CHUNK):
            status,_ = self.command("native_save_append",common|{"offset":offset,"data":base64.b64encode(raw[offset:offset+CHUNK]).decode()})
            self.assertEqual(status,200)
        command = uuid.uuid4().hex
        status,result = self.command("native_save_finish",common,command_id=command)
        self.assertEqual(status,200)
        self.assertTrue(result["result"]["durable"])
        self.assertEqual(self.command("native_save_finish",common,command_id=command),(status,result))
        restored = b""
        for offset in range(0,len(raw),CHUNK):
            query = urlencode({"character_id":character,"fence":fence,"session_fence":1,"revision":1,"offset":offset})
            status,page = self.call("GET","/v1/player-save?"+query)
            self.assertEqual(status,200)
            restored += base64.b64decode(page["result"]["data"])
            self.assertEqual(self.call("GET","/v1/player-save?"+query,token="c"*48)[0],403)
            self.assertEqual(self.call("GET","/v1/player-save?"+query,token="d"*48)[0],403)
        self.assertEqual(restored,raw)

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

    def test_actual_http_player_admission_observes_upload_disconnect_and_resume(self):
        import base64
        import hashlib
        from lostzone.native_save import identity
        from test_native_save import native_fixture
        headers = {"X-LostZone-Instance": "a" * 32,
                   "X-LostZone-World": f"{self.world.world_id}:{self.world.seed}:{self.store.epoch}"}
        request = {"command_id": uuid.uuid4().hex, "operation": "location_claim", "arguments": {"location": "cordon"}}
        status, claimed = self.call("POST", "/v1/command", request, headers=headers)
        self.assertEqual(status, 200)
        fence, actor = claimed["result"]["fence"], claimed["result"]["owner"]
        path = "/v1/player-admission?" + urlencode(dict(account="ALICE", slot=1, location="cordon", fence=fence, epoch=self.store.epoch))
        before = tuple(self.store.db.iterdump())
        status, result = self.call("GET", path, headers=headers)
        self.assertEqual((status, result["result"]["status"]), (200, "ABSENT"))
        self.assertEqual(before, tuple(self.store.db.iterdump()))
        character = identity(self.world.world_id, self.world.seed, "alice", 1)
        d = self.server.dispatcher
        d.ownership.create_entity(actor, uuid.uuid4().hex, character, "CHARACTER", "cordon", fence, {}, account="alice")
        raw = native_fixture()
        upload = d.player_saves.begin(actor, uuid.uuid4().hex, character, fence, 1, 1, 0, 1,
                                      len(raw), hashlib.sha256(raw).hexdigest())["upload_id"]
        self.assertEqual(self.call("GET", path, headers=headers)[0], 409)
        d.player_saves.append(actor, uuid.uuid4().hex, character, fence, 1, upload, 0, base64.b64encode(raw).decode())
        d.player_saves.finish(actor, uuid.uuid4().hex, character, fence, 1, upload)
        status, result = self.call("GET", path, headers=headers)
        self.assertEqual((status, result["result"]["status"], result["result"]["entity_version"]), (200, "ACTIVE", 2))
        self.assertEqual(result["result"]["checkpoint"], {"revision": 1, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.assertLess(len(json.dumps(result).encode()), 1024)
        d.ownership.disconnect(actor, uuid.uuid4().hex, character, fence, 2, {})
        before = tuple(self.store.db.iterdump())
        status, result = self.call("GET", path, headers=headers)
        self.assertEqual((status, result["result"]["status"], result["result"]["session_fence"]), (200, "DISCONNECTED", 2))
        self.assertEqual(before, tuple(self.store.db.iterdump()))
        d.ownership.resume(actor, uuid.uuid4().hex, character, "cordon", fence, 3)
        status, result = self.call("GET", path, headers=headers)
        self.assertEqual((status, result["result"]["status"], result["result"]["session_fence"]), (200, "ACTIVE", 3))

    def test_player_admission_requires_exact_bound_scope_and_bounded_query(self):
        binding = f"{self.world.world_id}:{self.world.seed}:{self.store.epoch}"
        headers = {"X-LostZone-Instance": "a" * 32, "X-LostZone-World": binding}
        request = {"command_id": uuid.uuid4().hex, "operation": "location_claim", "arguments": {"location": "cordon"}}
        status, result = self.call("POST", "/v1/command", request, headers=headers)
        self.assertEqual(status, 200)
        args = dict(account="alice", slot=1, location="cordon", fence=result["result"]["fence"], epoch=self.store.epoch)
        def path(changes=None):
            return "/v1/player-admission?" + urlencode(args | (changes or {}))
        before = tuple(self.store.db.iterdump())
        for token in ("a" * 48, "d" * 48):
            self.assertEqual(self.call("GET", path(), token=token)[0], 403)
        self.assertEqual(self.call("GET", path(), token=None)[0], 401)
        self.assertEqual(self.call("GET", path())[0], 400)
        self.assertEqual(self.call("GET", path(), headers={"X-LostZone-Instance": "a" * 32})[0], 400)
        self.assertEqual(self.call("GET", path(), headers={"X-LostZone-World": binding})[0], 400)
        self.assertEqual(self.call("GET", path(), headers=headers | {"X-LostZone-Instance": "b" * 32})[0], 409)
        self.assertEqual(self.call("GET", path(), headers=headers | {"X-LostZone-World": f"{self.world.world_id+1}:{self.world.seed}:{self.store.epoch}"})[0], 409)
        for changes in ({"location": "garbage"},):
            self.assertEqual(self.call("GET", path(changes), headers=headers)[0], 403)
        for changes in ({"epoch": self.store.epoch + 1}, {"fence": args["fence"] + 1}):
            self.assertEqual(self.call("GET", path(changes), headers=headers)[0], 409)
        for changes in ({"slot": "01"}, {"slot": 11}, {"slot": ""}, {"slot": "1 "}, {"slot": "-1"},
                        {"epoch": "1.0"}, {"fence": "9" * 20}, {"account": "../bad"}, {"account": "a" * 1025}):
            self.assertEqual(self.call("GET", path(changes), headers=headers)[0], 400)
        for query in ("account=alice", urlencode(args) + "&slot=1", urlencode(args) + "&other=1", urlencode(args).replace("slot=1", "slot=")):
            self.assertEqual(self.call("GET", "/v1/player-admission?" + query, headers=headers)[0], 400)
        self.server.ready.clear()
        self.assertEqual(self.call("GET", path(), headers=headers)[0], 503)
        self.server.ready.set()
        self.assertEqual(before, tuple(self.store.db.iterdump()))

    def test_runtime_instances_cannot_share_or_renew_another_process_lease(self):
        a, b = {"X-LostZone-Instance": "a" * 32}, {"X-LostZone-Instance": "b" * 32}
        def command(operation, arguments, headers, command_id=None):
            return self.call("POST", "/v1/command", {"command_id":command_id or uuid.uuid4().hex,
                    "operation":operation, "arguments":arguments}, headers=headers)
        status, result = command("location_claim", {"location":"cordon", "ttl_ms":1000}, a)
        self.assertEqual(200, status)
        fence = result["result"]["fence"]
        self.assertTrue(result["result"]["owner"].endswith(":" + "a" * 32))
        self.assertEqual(409, command("location_claim", {"location":"cordon"}, b)[0])
        self.assertEqual(409, command("location_renew", {"location":"cordon", "fence":fence}, b)[0])
        self.assertEqual(200, self.call("GET", f"/v1/location?id=cordon&fence={fence}", headers=a)[0])
        self.assertEqual(409, self.call("GET", f"/v1/location?id=cordon&fence={fence}", headers=b)[0])
        self.assertEqual(403, command("location_claim", {"location":"garbage"}, a)[0])
        with patch.object(self.world, "real_ms", return_value=self.world.real_ms()+2000):
            status, result = command("location_claim", {"location":"cordon"}, b)
            self.assertEqual(200, status)
            self.assertEqual(fence+1, result["result"]["fence"])
            self.assertEqual(409, command("location_renew", {"location":"cordon", "fence":fence}, a)[0])

    def test_runtime_instance_header_is_bounded_location_only_and_cannot_bypass_rate_limit(self):
        from lostzone.http import RateLimit
        for instance in ("", "../bad", "A" * 32, "a" * 33):
            self.assertEqual(400, self.call("GET", "/v1/clock", headers={"X-LostZone-Instance":instance})[0])
        for token in ("a" * 48, "d" * 48):
            self.assertEqual(403, self.call("GET", "/v1/clock", token=token, headers={"X-LostZone-Instance":"a" * 32})[0])
        self.server.rate_limit = RateLimit(rate=0, burst=1)
        self.assertEqual(200, self.call("GET", "/v1/clock", headers={"X-LostZone-Instance":"a" * 32})[0])
        self.assertEqual(429, self.call("GET", "/v1/clock", headers={"X-LostZone-Instance":"b" * 32})[0])

    def test_bound_runtime_commands_refuse_wrong_world_seed_or_master_epoch_before_mutating(self):
        epoch = self.store.epoch
        correct = f"{self.world.world_id}:{self.world.seed}:{epoch}"
        body = {"command_id":uuid.uuid4().hex,"operation":"location_claim","arguments":{"location":"cordon"}}
        for binding in (f"{self.world.world_id+1}:{self.world.seed}:{epoch}",
                        f"{self.world.world_id}:{self.world.seed+1}:{epoch}",
                        f"{self.world.world_id}:{self.world.seed}:{epoch+1}"):
            self.assertEqual(409, self.call("POST", "/v1/command", body,
                             headers={"X-LostZone-Instance":"a"*32,"X-LostZone-World":binding})[0])
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM location_lease").fetchone()[0])
        for binding in ("", "0:0:1", "1:1:0", "1:01:1", "1:1:1\n", "1:1:1:1"):
            if "\n" in binding:
                continue # http.client correctly refuses header injection itself.
            self.assertEqual(400, self.call("POST", "/v1/command", body,
                             headers={"X-LostZone-Instance":"a"*32,"X-LostZone-World":binding})[0])
        self.assertEqual(400, self.call("POST", "/v1/command", body, headers={"X-LostZone-World":correct})[0])
        self.assertEqual(200, self.call("POST", "/v1/command", body,
                         headers={"X-LostZone-Instance":"a"*32,"X-LostZone-World":correct})[0])

    def test_real_http_location_quest_requirements_are_scoped_and_versioned(self):
        _, claimed = self.command("location_claim", {"location":"cordon"})
        fence = claimed["result"]["fence"]
        d = self.server.dispatcher
        player, npc = uuid.uuid4().hex, uuid.uuid4().hex
        d.ownership.create_entity("cordon-server",uuid.uuid4().hex,player,"CHARACTER","cordon",fence,
                                  {"money":500,"password":"private"},account="quest-player")
        d.ownership.create_entity("cordon-server",uuid.uuid4().hex,npc,"NPC","cordon",fence,{"secret":"private npc"})
        d.quests = Quests(self.world,{"test_task":{"steps":[{"type":"EntityDied","target":npc}],
                                                  "requirements":[{"entity_id":npc}]}})
        d.quests.grant("cordon-server",uuid.uuid4().hex,player,fence,"test_task")
        path = "/v1/quest-requirements?"+urlencode({"location":"cordon","fence":fence})
        self.wait_idle_workers()
        status, response = self.call("GET",path)
        self.assertEqual(status,200)
        result = response["result"]
        self.assertEqual(result["requirements"][0]["entity_id"],npc)
        self.assertEqual(result["requirements"][0]["quest_version"],1)
        self.assertNotIn("private",json.dumps(response))
        for token,expected in (("c"*48,403),("d"*48,403),("a"*48,403),("x"*48,401)):
            self.wait_idle_workers()
            self.assertEqual(self.call("GET",path,token=token)[0],expected)
        # A causally committed update invalidates a continuation cut.
        d.ownership.update_entity("cordon-server",uuid.uuid4().hex,npc,fence,1,{"health":.5})
        continued = path+"&"+urlencode({"after":json.dumps([player,"test_task",npc]),
                                         "epoch":result["epoch"],"revision":result["revision"]})
        self.wait_idle_workers()
        self.assertEqual(self.call("GET",continued)[0],409)
        with self.store.transaction() as tx:
            tx.execute("UPDATE location_lease SET expires_ms=0 WHERE location='cordon'")
        self.wait_idle_workers()
        self.assertEqual(self.call("GET",path)[0],409)

    def test_real_http_quest_requirement_query_rejects_invalid_cursor_and_duplicates(self):
        prefix = "/v1/quest-requirements?location=cordon&fence=1"
        suffixes = ("&epoch=1","&after=[]","&after=null","&revision=1&epoch=1&after=%5B%5D",
                    "&fence=2","&after=","&unknown=1","&epoch=", "&revision=0&epoch=1")
        for suffix in suffixes:
            self.wait_idle_workers()
            self.assertEqual(self.call("GET",prefix+suffix)[0],400,suffix)

    def test_observer_bridge_credential_cannot_claim_or_mutate_world(self):
        self.assertEqual(self.call("GET","/v1/bootstrap",token="d"*48)[0],200)
        for operation,args in (("world_scale",{"value":1}),("location_claim",{"location":"cordon"}),
                               ("entity_create",{}),("trade",{}),("offline_combat",{}),("offline_contacts",{}),("offline_hazard",{}),("offline_hazards",{}),("offline_plan",{}),("quest_reconcile",{})):
            self.assertEqual(self.command(operation,args,token="d"*48)[0],403)

    def test_native_bootstrap_is_authenticated_bounded_and_recovery_gated(self):
        d = self.server.dispatcher
        d.timelines.schedule("admin", uuid.uuid4().hex, "weather", uuid.uuid4().hex, None,
                             {"TRANSITION": 0, "SETTLED": 100000},
                             {"source": "clear", "target": "rain", "seed": 0,
                              "private": "PRIVATE-PARAMETER" + "x" * 100000})
        self.world.set_state("admin", uuid.uuid4().hex, "other_private_state", 0,
                             {"secret": "PRIVATE-STATE" + "x" * 100000})
        self.wait_idle_workers()
        status, response = self.call("GET", "/v1/engine-bootstrap", token="d"*48)
        self.assertEqual(status, 200)
        self.assertLess(len(json.dumps(response)), 4096)
        self.assertNotIn("PRIVATE-", json.dumps(response))
        self.assertEqual(set(response["result"]["states"]), {"weather"})
        self.assertEqual(response["result"]["clock"]["revision"], response["result"]["state_revision"])
        for token in (None, "x"*48):
            self.wait_idle_workers()
            self.assertEqual(self.call("GET", "/v1/engine-bootstrap", token=token)[0], 401)
        self.server.ready.clear()
        self.wait_idle_workers()
        self.assertEqual(self.call("GET", "/v1/engine-bootstrap", token="d"*48)[0], 503)

    def test_location_registry_cut_is_scoped_paged_and_released_over_http(self):
        _, response = self.command("location_claim", {"location": "cordon"})
        fence = response["result"]["fence"]
        d = self.server.dispatcher
        for number in range(1, 66):
            d.ownership.create_entity("cordon-server", uuid.uuid4().hex, f"{number:032x}", "NPC",
                                      "cordon", fence, {"health": .8})
        query = {"location": "cordon", "fence": fence, "epoch": self.store.epoch, "request_id": uuid.uuid4().hex}
        path = "/v1/location-bootstrap?" + urlencode(query)
        self.wait_idle_workers()
        status, body = self.call("GET", path)
        self.assertEqual(status, 200)
        first = body["result"]
        self.assertEqual(len(first["entries"]), 64)
        self.assertEqual(first["owner"], "cordon-server")
        for token, expected in (("c"*48, 403), ("d"*48, 403), ("a"*48, 403), ("x"*48, 401)):
            self.wait_idle_workers()
            self.assertEqual(self.call("GET", path, token=token)[0], expected)
        continued = {"location": "cordon", "fence": fence, "epoch": self.store.epoch,
                     "capture_id": first["capture_id"], "after": first["next"]}
        self.wait_idle_workers()
        status, body = self.call("GET", "/v1/location-bootstrap?" + urlencode(continued))
        self.assertEqual(status, 200)
        self.assertEqual(len(body["result"]["entries"]), 1)
        self.assertEqual(body["result"]["clock"], first["clock"])
        self.assertEqual(body["result"]["entries"][0]["id"], f"{65:032x}")
        release = {key: continued[key] for key in ("location", "fence", "epoch", "capture_id")}
        for _ in range(2):
            self.wait_idle_workers()
            self.assertEqual(self.call("POST", "/v1/location-bootstrap-release", release)[0], 200)
        self.assertFalse(d.location_bootstrap.captures)
        self.wait_idle_workers()
        self.assertEqual(self.call("GET", "/v1/location-bootstrap?" + urlencode(continued))[0], 409)

    def test_registry_bootstrap_query_recovery_and_worker_failure_close_readers(self):
        _, response = self.command("location_claim", {"location": "cordon"})
        fence = response["result"]["fence"]
        query = {"location": "cordon", "fence": fence, "epoch": self.store.epoch, "request_id": uuid.uuid4().hex}
        path = "/v1/location-bootstrap?" + urlencode(query)
        for suffix in ("&fence=1", "&unknown=1", "&capture_id=" + uuid.uuid4().hex, "&after=bad"):
            self.wait_idle_workers()
            self.assertEqual(self.call("GET", path + suffix)[0], 400)
        self.wait_idle_workers()
        self.assertEqual(self.call("GET", path)[0], 200)
        db = next(iter(self.server.dispatcher.location_bootstrap.captures.values()))["db"]
        self.server.worker_failed(RuntimeError("private"))
        self.assertFalse(self.server.dispatcher.location_bootstrap.captures)
        with self.assertRaises(Exception):
            db.execute("SELECT 1")
        self.wait_idle_workers()
        self.assertEqual(self.call("GET", path)[0], 503)

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
        # This test exercises the batch limit and admission barrier. Slow fsync
        # on CI must not turn it into an unrelated wall-time budget assertion.
        with patch("lostzone.scheduler.time") as scheduler_clock:
            scheduler_clock.monotonic.return_value=0
            processed=scheduler.run_due(limit=64,budget_ms=1000)
        self.assertEqual(processed,64);self.server.worker_succeeded(processed)
        self.assertFalse(self.server.ready.is_set())
        self.assertEqual(self.call("GET","/v1/bootstrap")[0],503)
        status,result=self.call("GET","/v1/status",token="a"*48)
        self.assertEqual(status,200);self.assertEqual(result["result"]["due_sample_count"],1)
        with patch("lostzone.scheduler.time") as scheduler_clock:
            scheduler_clock.monotonic.return_value=0
            processed=scheduler.run_due(budget_ms=1000)
        self.server.worker_succeeded(processed)
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
