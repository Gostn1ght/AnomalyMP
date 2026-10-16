"""Read-only native slot observations over actual SQLite authority state."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Conflict, Invalid, Store, Unavailable, World
from lostzone.native_save import identity, parse_native_save
from lostzone.ownership import Ownership
from lostzone.player_saves import CHUNK, PlayerSaves
from lostzone.store import canonical
from lostzone.transfers import Transfers
from test_native_save import native_fixture


def uid():
    return uuid.uuid4().hex


class PlayerAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "world.sqlite")
        self.millis = 1000
        self.world = World(self.store, world_id=42, seed=7, monotonic=lambda: self.millis * 1_000_000,
                           wall=lambda: self.millis * 1_000_000)
        self.ownership, self.saves = Ownership(self.world), PlayerSaves(self.world)
        self.transfers = Transfers(self.world, b"fixture-" * 4)
        self.source = self.world.claim_location("source", uid(), "cordon")["fence"]
        self.target = self.world.claim_location("target", uid(), "marsh")["fence"]
        self.character = identity(42, 7, "alice", 1)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def inspect(self, **changes):
        args = dict(actor="source", account="alice", slot=1, location="cordon", fence=self.source, epoch=self.store.epoch)
        return self.saves.inspect(**(args | changes))

    def create(self, account="alice"):
        self.ownership.create_entity("source", uid(), self.character, "CHARACTER", "cordon", self.source,
                                     {"position": [1, 2, 3], "private_behavior": "not returned"}, account=account)

    def begin(self, raw, version=1, revision=0):
        return self.saves.begin("source", uid(), self.character, self.source, 1, version, revision, 1,
                                len(raw), hashlib.sha256(raw).hexdigest())["upload_id"]

    def complete(self, raw, version=1, revision=0):
        upload = self.begin(raw, version, revision)
        for offset in range(0, len(raw), CHUNK):
            self.saves.append("source", uid(), self.character, self.source, 1, upload, offset,
                              base64.b64encode(raw[offset:offset + CHUNK]).decode())
        return self.saves.finish("source", uid(), self.character, self.source, 1, upload)

    def dump(self):
        return tuple(self.store.db.iterdump())

    def stage(self, location="cordon"):
        raw = native_fixture()
        saved = parse_native_save(raw)
        self.store.db.execute("INSERT INTO native_player_import VALUES(?,?,?,?,?,?,?,?,?)",
                              (self.character, "alice", 1, location, "42", "7", saved.sha256,
                               canonical(saved.summary()), base64.b64encode(raw).decode()))

    def test_absent_observation_is_bounded_stable_and_never_creates_anything(self):
        before = self.dump()
        result = self.inspect(account="ALICE")
        self.assertEqual(result, self.inspect())
        self.assertEqual((result["status"], result["character_id"], result["checkpoint"]), ("ABSENT", self.character, None))
        self.assertEqual((result["schema"], result["world_id"], result["seed"], result["account"]), (1, "42", "7", "alice"))
        self.assertEqual((result["entity_version"], result["session_fence"]), (0, 0))
        self.assertLess(len(canonical(result)), 1024)
        self.assertEqual(before, self.dump())

    def test_live_head_tracks_latest_durable_bytes_without_reading_payload(self):
        self.create()
        initial = self.inspect()
        self.assertEqual((initial["status"], initial["entity_version"], initial["session_fence"], initial["checkpoint"]),
                         ("ACTIVE", 1, 1, None))
        self.complete(native_fixture(progress=b"older"))
        raw = native_fixture(9, progress=b"opaque tasks/behavior" * 2000)
        self.complete(raw, 2, 1)
        before, queries = self.dump(), []
        self.store.db.set_trace_callback(queries.append)
        try:
            with patch("lostzone.player_saves.parse_native_save", side_effect=AssertionError("inspection parsed payload")):
                result = self.inspect()
        finally:
            self.store.db.set_trace_callback(None)
        self.assertEqual(result["checkpoint"], {"revision": 2, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.assertEqual((result["entity_version"], result["session_fence"]), (3, 1))
        self.assertEqual(before, self.dump())
        self.assertTrue(all(query.lstrip().upper().startswith("SELECT ") for query in queries))
        self.assertFalse(any("payload_base64" in query.lower() for query in queries))
        self.assertNotIn("private_behavior", canonical(result))
        self.assertEqual(set(result), {"schema", "world_id", "seed", "epoch", "location", "fence", "account", "slot",
                                       "character_id", "entity_version", "session_fence", "checkpoint", "status"})

    def test_disconnected_observation_does_not_resume_and_reflects_later_resume(self):
        self.create()
        self.complete(native_fixture())
        self.ownership.disconnect("source", uid(), self.character, self.source, 2, {"position": [4, 5, 6]})
        before = self.dump()
        result = self.inspect()
        self.assertEqual((result["status"], result["entity_version"], result["session_fence"]), ("DISCONNECTED", 3, 2))
        self.assertEqual(before, self.dump())
        self.ownership.resume("source", uid(), self.character, "cordon", self.source, 3)
        resumed = self.inspect()
        self.assertEqual((resumed["status"], resumed["entity_version"], resumed["session_fence"]), ("ACTIVE", 4, 3))
        self.assertEqual(resumed["checkpoint"], result["checkpoint"])

    def test_other_active_or_frozen_account_slot_cannot_be_offered_as_new(self):
        self.create(account="Alice")
        self.assertEqual(self.inspect()["status"], "ACTIVE")
        for account in ("alice", "ALICE", "Alice"):
            with self.assertRaises(Conflict):
                self.inspect(account=account, slot=2)
        self.transfers.prepare("source", uid(), self.character, "cordon", self.source, "marsh", 1)
        with self.assertRaises(Conflict):
            self.inspect(slot=2)

    def test_pending_even_expired_upload_is_not_erased_or_hidden_by_old_head(self):
        self.create()
        raw = native_fixture()
        self.complete(raw)
        upload = self.begin(raw, 2, 1)
        for expiry in (self.millis + 100, 0):
            self.store.db.execute("UPDATE native_player_upload SET expires_ms=? WHERE id=?", (expiry, upload))
            before = self.dump()
            with self.assertRaises(Conflict):
                self.inspect()
            self.assertEqual(before, self.dump())
        self.saves.cancel("source", uid(), self.character, self.source, 1, upload)
        self.assertEqual(self.inspect()["checkpoint"]["revision"], 1)

    def test_wrong_authority_epoch_and_expired_lease_refuse_without_mutation(self):
        self.create()
        for changes in ({"actor": "other"}, {"fence": self.source + 1}, {"epoch": self.store.epoch + 1},
                        {"location": "marsh", "actor": "target", "fence": self.target}):
            before = self.dump()
            with self.assertRaises(Conflict):
                self.inspect(**changes)
            self.assertEqual(before, self.dump())
        self.millis += 20000
        with self.assertRaises(Conflict):
            self.inspect()
        with self.assertRaises(Conflict):
            self.inspect(account="nobody")

    def test_handoff_refuses_both_sides_until_commit_and_then_follows_owner(self):
        self.create()
        self.complete(native_fixture())
        prepared = self.transfers.prepare("source", uid(), self.character, "cordon", self.source, "marsh", 2)
        with self.assertRaises(Conflict):
            self.inspect()
        self.transfers.claim("target", uid(), prepared["token"], self.target)
        with self.assertRaises(Conflict):
            self.inspect(actor="target", location="marsh", fence=self.target)
        self.transfers.commit("target", uid(), prepared["transfer_id"], self.target)
        with self.assertRaises(Conflict):
            self.inspect()
        result = self.inspect(actor="target", location="marsh", fence=self.target)
        self.assertEqual((result["status"], result["session_fence"], result["checkpoint"]["revision"]), ("ACTIVE", 3, 1))

    def test_takeover_requires_explicit_recovery_and_fences_old_reader(self):
        self.create()
        self.complete(native_fixture())
        self.millis += 20000
        fence = self.world.claim_location("replacement", uid(), "cordon")["fence"]
        with self.assertRaises(Conflict):
            self.inspect(actor="replacement", fence=fence)
        self.ownership.recover_location("replacement", uid(), "cordon", fence)
        result = self.inspect(actor="replacement", fence=fence)
        self.assertEqual((result["entity_version"], result["session_fence"], result["checkpoint"]["revision"]), (3, 2, 1))
        with self.assertRaises(Conflict):
            self.inspect()

    def test_dead_character_is_never_reported_as_an_absent_slot(self):
        self.create()
        self.ownership.kill("source", uid(), self.character, self.source, 1, "fixture")
        before = self.dump()
        with self.assertRaises(Conflict):
            self.inspect()
        self.assertEqual(before, self.dump())

    def test_staged_archive_stays_distinct_and_never_becomes_a_live_session(self):
        self.stage()
        before = self.dump()
        result = self.inspect()
        self.assertEqual((result["status"], result["checkpoint"], result["session_fence"]), ("STAGED", None, 0))
        self.assertEqual(before, self.dump())
        with self.assertRaises(Conflict):
            self.inspect(actor="target", location="marsh", fence=self.target)
        self.create()
        with self.assertRaises(Conflict):
            self.inspect()
        self.complete(native_fixture(progress=b"activated native state"))
        self.assertEqual(self.inspect()["checkpoint"]["revision"], 1)

    def test_bad_checkpoint_or_reference_fails_closed_without_repairing_data(self):
        self.create()
        self.complete(native_fixture())
        original = self.store.db.execute("SELECT state FROM entity WHERE id=?", (self.character,)).fetchone()[0]
        for state in ("{}", "[]", "{bad", canonical({"native_save": {"revision": 99}}),
                      original.replace('"revision":1', '"revision":true'),
                      json.dumps({"huge": "x" * (1024 * 1024)})):
            self.store.db.execute("UPDATE entity SET state=? WHERE id=?", (state, self.character))
            before = self.dump()
            with self.assertRaises(Unavailable):
                self.inspect()
            self.assertEqual(before, self.dump())
        self.store.db.execute("UPDATE entity SET state=? WHERE id=?", (original, self.character))
        valid_head = self.store.db.execute("SELECT sha256,byte_count FROM native_player_save").fetchone()
        for sql, value in (("sha256", "A" * 64), ("byte_count", 3), ("byte_count", 20 * 1024 * 1024 + 1)):
            self.store.db.execute("UPDATE native_player_save SET sha256=?,byte_count=?", tuple(valid_head))
            self.store.db.execute(f"UPDATE native_player_save SET {sql}=?", (value,))
            before = self.dump()
            with self.assertRaises(Unavailable):
                self.inspect()
            self.assertEqual(before, self.dump())

    def test_staged_foreign_identity_and_dangling_null_reference_are_not_new_players(self):
        self.stage()
        self.store.db.execute("UPDATE native_player_import SET id=?", (uid(),))
        with self.assertRaises(Unavailable):
            self.inspect()
        self.store.db.execute("UPDATE native_player_import SET id=?,seed='99'", (self.character,))
        with self.assertRaises(Unavailable):
            self.inspect()
        self.store.db.execute("UPDATE native_player_import SET seed='7',account='other-account'")
        with self.assertRaises(Unavailable):
            self.inspect()
        self.store.db.execute("UPDATE native_player_import SET account='alice',slot=2")
        with self.assertRaises(Unavailable):
            self.inspect()
        self.store.db.execute("UPDATE native_player_import SET slot=1,id=?", (uid(),))
        other = parse_native_save(native_fixture())
        self.store.db.execute("INSERT INTO native_player_import VALUES(?,?,?,?,?,?,?,?,?)",
                             (self.character, "another-account", 1, "cordon", "42", "7", other.sha256,
                              canonical(other.summary()), base64.b64encode(other.raw).decode()))
        with self.assertRaises(Unavailable):
            self.inspect()
        self.store.db.execute("DELETE FROM native_player_import")
        self.create()
        self.store.db.execute("UPDATE entity SET state=? WHERE id=?", ('{"native_save":null}', self.character))
        with self.assertRaises(Unavailable):
            self.inspect()

    def test_invalid_identity_and_numeric_bounds_fail_without_queries(self):
        for changes in ({"account": "../alice"}, {"account": "a" * 21}, {"slot": True}, {"slot": 0},
                        {"slot": 11}, {"epoch": True}, {"fence": 0}, {"fence": 2**63}):
            with self.assertRaises(Invalid):
                self.inspect(**changes)

    def test_inspection_is_one_consistent_cut_against_concurrent_upload(self):
        self.create()
        self.complete(native_fixture(progress=b"old"))
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        results, errors = [], []
        original = self.world.require_location

        def pause(*args, **kwargs):
            if threading.current_thread().name == "slot-reader":
                entered.set()
                if not release.wait(5):
                    raise AssertionError("inspection release timeout")
            return original(*args, **kwargs)

        def read():
            try:
                results.append(self.inspect())
            except BaseException as error:
                errors.append(type(error).__name__)

        def write():
            try:
                self.complete(native_fixture(progress=b"new"), 2, 1)
            except BaseException as error:
                errors.append(type(error).__name__)
            finally:
                finished.set()

        with patch.object(self.world, "require_location", side_effect=pause):
            reader = threading.Thread(target=read, name="slot-reader")
            writer = threading.Thread(target=write, name="slot-writer")
            reader.start()
            try:
                self.assertTrue(entered.wait(5))
                writer.start()
                self.assertFalse(finished.wait(.05))
            finally:
                release.set()
                reader.join(5)
                if writer.ident is not None:
                    writer.join(5)
        self.assertFalse(reader.is_alive() or writer.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual((results[0]["entity_version"], results[0]["checkpoint"]["revision"]), (2, 1))
        current = self.inspect()
        self.assertEqual((current["entity_version"], current["checkpoint"]["revision"]), (3, 2))


if __name__ == "__main__":
    unittest.main()
