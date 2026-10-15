"""Native checkpoint protocol: real SQLite, leases, sessions and handoff."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Conflict, Invalid, Store, Unavailable, World
from lostzone.http import Dispatcher, Principal
from lostzone.native_save import identity
from lostzone.ownership import Ownership
from lostzone.player_saves import CHUNK, PlayerSaves
from lostzone.transfers import Transfers
from test_native_save import native_fixture


def uid():
    return uuid.uuid4().hex


class PlayerSavesTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/"world.sqlite"
        self.millis = 1000
        self.open()
        self.source = self.world.claim_location("source", uid(), "cordon")["fence"]
        self.target = self.world.claim_location("target", uid(), "marsh")["fence"]
        self.character = identity(42, 7, "alice", 1)
        self.ownership.create_entity("source", uid(), self.character, "CHARACTER", "cordon", self.source,
                                     {"position": [1, 2, 3]}, account="alice")

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=42, seed=7, monotonic=lambda: self.millis*1_000_000,
                           wall=lambda: self.millis*1_000_000)
        self.ownership = Ownership(self.world)
        self.saves = PlayerSaves(self.world)
        self.transfers = Transfers(self.world, b"fixture-"*4)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def begin(self, raw, *, version=1, revision=0, session=1, actor="source", fence=None):
        return self.saves.begin(actor, uid(), self.character, fence or self.source, session, version,
                                revision, 1, len(raw), hashlib.sha256(raw).hexdigest())["upload_id"]

    def append(self, raw, upload):
        for offset in range(0,len(raw),CHUNK):
            self.saves.append("source", uid(), self.character, self.source, 1, upload, offset,
                               base64.b64encode(raw[offset:offset+CHUNK]).decode())

    def complete(self, raw, *, version=1, revision=0):
        upload = self.begin(raw, version=version, revision=revision)
        self.append(raw,upload)
        command = uid()
        result = self.saves.finish("source", command, self.character, self.source, 1, upload)
        return result, command, upload

    def test_chunked_complete_commit_and_lossless_read(self):
        raw = native_fixture(9, progress=b"task/info/behavior"*5000)
        result, command, upload = self.complete(raw)
        self.assertEqual((result["revision"],result["entity_version"],result["durable"]),(1,2,True))
        restored = b""
        for offset in range(0,len(raw),CHUNK):
            page = self.saves.read("source",self.character,self.source,1,1,offset)
            restored += base64.b64decode(page["data"])
            self.assertLess(len(json.dumps(page).encode()),65536)
        self.assertEqual(restored,raw)
        self.assertEqual(self.saves.finish("source",command,self.character,self.source,1,upload),result)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_save").fetchone()[0],1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_upload").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_part").fetchone()[0],0)
        state = json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(self.character,)).fetchone()[0])
        self.assertEqual(state["position"],[1,2,3])
        self.assertEqual(state["native_save"]["sha256"],hashlib.sha256(raw).hexdigest())

    def test_incomplete_corrupt_and_wrong_digest_never_replace_previous(self):
        raw = native_fixture()
        self.complete(raw)
        upload = self.begin(raw,version=2,revision=1)
        with self.assertRaises(Conflict):
            self.saves.finish("source",uid(),self.character,self.source,1,upload)
        self.assertEqual(self.saves.read("source",self.character,self.source,1,1)["revision"],1)
        self.saves.cancel("source",uid(),self.character,self.source,1,upload)
        for changed in (raw[:-1]+b"\xff",native_fixture(progress=b"different but internally valid")):
            upload = self.saves.begin("source",uid(),self.character,self.source,1,2,1,1,len(changed),hashlib.sha256(raw).hexdigest())["upload_id"]
            self.append(changed,upload)
            with self.assertRaises(Invalid):
                self.saves.finish("source",uid(),self.character,self.source,1,upload)
            self.saves.cancel("source",uid(),self.character,self.source,1,upload)
        self.assertEqual(self.store.db.execute("SELECT MAX(revision) FROM native_player_save").fetchone()[0],1)

    def test_chunk_replay_reordering_and_tiny_nonfinal_chunks(self):
        raw = native_fixture(progress=b"x"*40000)
        upload = self.begin(raw)
        data = base64.b64encode(raw[:CHUNK]).decode()
        command = uid()
        args = ("source",command,self.character,self.source,1,upload,0,data)
        first = self.saves.append(*args)
        self.assertEqual(self.saves.append(*args),first)
        with self.assertRaises(Conflict):
            self.saves.append("source",uid(),self.character,self.source,1,upload,0,data)
        with self.assertRaises(Invalid):
            self.saves.append("source",uid(),self.character,self.source,1,upload,1,data)
        self.saves.append("source",uid(),self.character,self.source,1,upload,CHUNK,base64.b64encode(raw[CHUNK:]).decode())
        self.saves.finish("source",uid(),self.character,self.source,1,upload)
        upload = self.begin(raw,version=2,revision=1)
        with self.assertRaises(Conflict):
            self.saves.append("source",uid(),self.character,self.source,1,upload,0,base64.b64encode(b"x").decode())

    def test_wrong_writer_session_identity_version_and_world_cannot_write(self):
        raw = native_fixture()
        for options in ({"actor":"target","fence":self.target},{"session":2},{"version":2},{"revision":1}):
            with self.assertRaises(Conflict):
                self.begin(raw,**options)
        with self.assertRaises(Conflict):
            self.saves.begin("source",uid(),self.character,self.source,1,1,0,2,len(raw),hashlib.sha256(raw).hexdigest())
        with self.assertRaises(Invalid):
            self.saves.begin("source",uid(),self.character,self.source,1,1,0,True,len(raw),hashlib.sha256(raw).hexdigest())
        with self.assertRaises(Conflict):
            self.saves.read("target",self.character,self.target,1,1)

    def test_entity_changes_before_finish_preserve_previous_checkpoint(self):
        raw = native_fixture()
        self.complete(raw)
        upload = self.begin(raw,version=2,revision=1)
        self.append(raw,upload)
        self.ownership.update_entity("source",uid(),self.character,self.source,2,{"position":[4,5,6]})
        with self.assertRaises(Conflict):
            self.saves.finish("source",uid(),self.character,self.source,1,upload)
        self.assertEqual(self.store.db.execute("SELECT MAX(revision) FROM native_player_save").fetchone()[0],1)

    def test_chunk_decode_releases_world_lock_and_rechecks_cas(self):
        previous = native_fixture(progress=b"previous complete checkpoint")
        self.complete(previous)
        raw = native_fixture(progress=b"new progress"*4000)
        upload = self.begin(raw,version=2,revision=1)
        self.append(raw,upload)
        entered,release = threading.Event(),threading.Event()
        decode = base64.b64decode
        errors = []
        def paused_decode(*args,**kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("decode test barrier expired")
            return decode(*args,**kwargs)
        def finish():
            try:
                self.saves.finish("source",uid(),self.character,self.source,1,upload)
            except Exception as error:
                errors.append(error)
        with patch("lostzone.player_saves.base64.b64decode",side_effect=paused_decode):
            worker = threading.Thread(target=finish)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                acquired = self.store.lock.acquire(timeout=0.5)
                if acquired:
                    self.store.lock.release()
                self.assertTrue(acquired,"base64 decode holds the shared world lock")
                self.ownership.update_entity("source",uid(),self.character,self.source,2,{"position":[4,5,6]})
            finally:
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],Conflict)
        self.assertEqual(self.store.db.execute("SELECT MAX(revision) FROM native_player_save").fetchone()[0],1)
        self.assertEqual(base64.b64decode(self.saves.read("source",self.character,self.source,1,1)["data"]),previous)

    def test_corrupt_staged_parts_never_replace_complete_checkpoint(self):
        previous = native_fixture(progress=b"previous complete checkpoint")
        self.complete(previous)
        raw = native_fixture(progress=b"new progress"*4000)
        upload = self.begin(raw,version=2,revision=1)
        self.append(raw,upload)
        original = [tuple(row) for row in self.store.db.execute("SELECT upload_id,offset,payload_base64 FROM native_player_part ORDER BY offset")]
        cases = (("UPDATE native_player_part SET offset=1 WHERE upload_id=? AND offset=0",(upload,)),
                 ("UPDATE native_player_part SET payload_base64='!!!' WHERE upload_id=? AND offset=0",(upload,)),
                 ("UPDATE native_player_part SET payload_base64=? WHERE upload_id=? AND offset=0",(base64.b64encode(b"short").decode(),upload)),
                 ("UPDATE native_player_part SET payload_base64=? WHERE upload_id=? AND offset=0",("A"*(CHUNK*4//3+4),upload)),
                 ("DELETE FROM native_player_part WHERE upload_id=? AND offset=?",(upload,original[-1][1])))
        for sql,parameters in cases:
            with self.subTest(sql=sql):
                self.store.db.execute(sql,parameters)
                with self.assertRaises(Invalid):
                    self.saves.finish("source",uid(),self.character,self.source,1,upload)
                self.assertEqual(self.store.db.execute("SELECT MAX(revision) FROM native_player_save").fetchone()[0],1)
                self.assertEqual(base64.b64decode(self.saves.read("source",self.character,self.source,1,1)["data"]),previous)
                self.store.db.execute("DELETE FROM native_player_part WHERE upload_id=?",(upload,))
                self.store.db.executemany("INSERT INTO native_player_part VALUES(?,?,?)",original)
        self.assertTrue(self.saves.finish("source",uid(),self.character,self.source,1,upload)["durable"])

    def test_generic_state_and_disconnect_preserve_the_durable_reference(self):
        raw = native_fixture()
        self.complete(raw)
        self.ownership.update_entity("source",uid(),self.character,self.source,2,{"position":[4,5,6]})
        state = json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(self.character,)).fetchone()[0])
        self.assertEqual(state["native_save"]["revision"],1)
        with self.assertRaises(Conflict):
            self.ownership.update_entity("source",uid(),self.character,self.source,3,{"native_save":{"revision":99}})
        self.ownership.disconnect("source",uid(),self.character,self.source,3,{"position":[7,8,9]})
        resumed = self.ownership.resume("source",uid(),self.character,"cordon",self.source,4)
        self.assertEqual(resumed["state"]["native_save"]["revision"],1)
        self.assertEqual(base64.b64decode(self.saves.read("source",self.character,self.source,3,1)["data"]),raw)

    def test_incomplete_save_blocks_disconnect_and_handoff(self):
        raw = native_fixture()
        self.complete(raw)
        self.begin(raw,version=2,revision=1)
        with self.assertRaises(Conflict):
            self.ownership.disconnect("source",uid(),self.character,self.source,2,{})
        with self.assertRaises(Conflict):
            self.transfers.prepare("source",uid(),self.character,"cordon",self.source,"marsh",2)
        self.assertEqual(self.store.db.execute("SELECT state FROM player_session").fetchone()[0],"ACTIVE")

    def test_handoff_reference_reads_before_activation_and_fences_source(self):
        raw = native_fixture(9,progress=b"cross-map-task-progress")
        self.complete(raw)
        prepared = self.transfers.prepare("source",uid(),self.character,"cordon",self.source,"marsh",2)
        with self.assertRaises(Conflict):
            self.saves.read("source",self.character,self.source,1,1)
        claimed = self.transfers.claim("target",uid(),prepared["token"],self.target)
        self.assertEqual(json.loads(claimed["checkpoint"]["entities"][0]["state"])["native_save"]["revision"],1)
        page = self.saves.read("target",self.character,self.target,2,1,transfer_id=prepared["transfer_id"])
        self.assertEqual(base64.b64decode(page["data"]),raw)
        with self.assertRaises(Conflict):
            self.saves.read("target",self.character,self.target,2,2,transfer_id=prepared["transfer_id"])
        self.transfers.commit("target",uid(),prepared["transfer_id"],self.target)
        self.assertEqual(base64.b64decode(self.saves.read("target",self.character,self.target,3,1)["data"]),raw)
        with self.assertRaises(Conflict):
            self.saves.read("target",self.character,self.target,2,1,transfer_id=prepared["transfer_id"])

    def test_master_restart_rejects_old_partial_upload_and_retains_complete_save(self):
        raw = native_fixture()
        self.complete(raw)
        partial = self.begin(raw,version=2,revision=1)
        self.append(raw,partial)
        self.store.close()
        self.open()
        with self.assertRaises(Conflict):
            self.saves.finish("source",uid(),self.character,self.source,1,partial)
        self.assertEqual(base64.b64decode(self.saves.read("source",self.character,self.source,1,1)["data"]),raw)
        new = self.begin(raw,version=2,revision=1)
        self.assertNotEqual(partial,new)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_upload").fetchone()[0],1)

    def test_location_takeover_fences_old_writer_and_reclaims_partial_budget(self):
        raw = native_fixture()
        self.complete(raw)
        partial = self.begin(raw,version=2,revision=1)
        self.append(raw,partial)
        self.millis += 20000
        fence = self.world.claim_location("replacement",uid(),"cordon")["fence"]
        self.ownership.recover_location("replacement",uid(),"cordon",fence)
        with self.assertRaises(Conflict):
            self.saves.finish("source",uid(),self.character,self.source,1,partial)
        upload = self.begin(raw,actor="replacement",fence=fence,session=2,version=3,revision=1)
        self.assertNotEqual(upload,partial)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_upload").fetchone()[0],1)
        self.assertEqual(base64.b64decode(self.saves.read("replacement",self.character,fence,2,1)["data"]),raw)

    def test_bounded_history_and_snapshot_excludes_incomplete_uploads(self):
        for revision in range(4):
            self.complete(native_fixture(progress=str(revision).encode()),version=revision+1,revision=revision)
        self.assertEqual([row[0] for row in self.store.db.execute("SELECT revision FROM native_player_save ORDER BY revision")],[3,4])
        with self.assertRaises(Invalid):
            self.saves.read("source",self.character,self.source,1,1)
        self.begin(native_fixture(),version=5,revision=4)
        snapshot = self.store.read_snapshot(self.store.snapshot()["id"])["records"]
        self.assertEqual(len(snapshot["native_player_save"]),2)
        self.assertNotIn("native_player_upload",snapshot)

    def test_admission_budget_replay_expiry_and_cancel(self):
        raw = native_fixture()
        with patch("lostzone.player_saves.UPLOAD_BUDGET",len(raw)-1),self.assertRaises(Unavailable):
            self.begin(raw)
        command = uid()
        args = ("source",command,self.character,self.source,1,1,0,1,len(raw),hashlib.sha256(raw).hexdigest())
        result = self.saves.begin(*args)
        self.assertEqual(self.saves.begin(*args),result)
        self.store.db.execute("UPDATE native_player_upload SET expires_ms=0")
        with self.assertRaises(Conflict):
            self.saves.begin(*args)
        self.saves.cancel("source",uid(),self.character,self.source,1,result["upload_id"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM native_player_part").fetchone()[0],0)

    def test_dispatcher_requires_location_scope_and_disallows_observer_admin(self):
        dispatcher = Dispatcher(self.world,b"fixture-"*4)
        args = {"character_id":self.character,"fence":self.source,"session_fence":1,"entity_version":1,
                "base_revision":0,"slot":1,"byte_count":len(native_fixture()),"sha256":hashlib.sha256(native_fixture()).hexdigest()}
        request = {"command_id":uid(),"operation":"native_save_begin","arguments":args}
        for principal in (Principal("source","observer",()),Principal("source","admin",()),Principal("source","location",("marsh",))):
            with self.assertRaises(PermissionError):
                dispatcher.execute(principal,request)
        self.assertIn("upload_id",dispatcher.execute(Principal("source","location",("cordon",)),request))
        dispatcher.location_bootstrap.close()


if __name__ == "__main__":
    unittest.main()
