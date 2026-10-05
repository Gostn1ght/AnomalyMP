import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid, Unavailable
from lostzone.ownership import Ownership
from lostzone.transfers import Transfers


def uid():
    return uuid.uuid4().hex


class Clock:
    def __init__(self):
        self.ns, self.utc_ns = 1_000_000_000, 1_800_000_000_000_000_000

    def advance(self, ms):
        self.ns += ms * 1_000_000
        self.utc_ns += ms * 1_000_000


class WorldTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.clock = Clock()
        self.open()
        self.a = self.world.claim_location("a", uid(), "cordon")["fence"]
        self.b = self.world.claim_location("b", uid(), "garbage")["fence"]

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=71, seed=2**64 - 1,
                           monotonic=lambda: self.clock.ns, wall=lambda: self.clock.utc_ns)
        self.ownership = Ownership(self.world)
        self.transfers = Transfers(self.world, b"test-key-" * 4)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def entity(self, kind="NPC", state=None, location="cordon", actor="a", fence=None, **options):
        result = uid()
        self.ownership.create_entity(actor, uid(), result, kind, location,
                                     fence or self.a, state or {"health": 0.75, "position": [1, 2, 3]}, **options)
        return result

    def character(self, account="account"):
        return self.entity("CHARACTER", {"health": .37, "radiation": .14, "bleeding": .07,
                                          "hunger": .25, "faction": "stalker"}, account=account)

    def item(self, kind="WORLD", holder=None, state=None):
        result = uid()
        self.ownership.create_item("a", uid(), result, "wpn_ak74", "cordon", self.a,
                                   kind, holder, state=state or {"condition": .51, "ammo": 17, "attachments": ["scope"]})
        return result

    def move(self, command, item, requester, source_kind="WORLD", source_holder="cordon", target_kind="NPC", target_holder=None, version=1):
        return self.ownership.move_item("a", command, item, "cordon", self.a, version,
                                       source_kind, source_holder, target_kind, target_holder or requester, requester)

    def test_clock_continuity_scale_retry_and_monotonic_failure(self):
        self.clock.advance(1000)
        self.assertEqual(self.world.now(), 10000)
        key = uid()
        self.world.set_scale("admin", key, 2)
        self.clock.advance(1000)
        self.assertEqual(self.world.now(), 12000)
        self.world.set_scale("admin", uid(), 4)
        self.clock.advance(1000)
        self.world.set_scale("admin", key, 2)
        self.assertEqual(self.world.now(), 16000)
        self.clock.advance(1000)
        self.assertEqual(self.world.now(), 20000)
        self.clock.ns -= 10
        with self.assertRaises(Unavailable):
            self.world.now()
        for bad in (0, -1, float("nan"), float("inf"), True, 1001):
            with self.assertRaises(Invalid):
                self.world.set_scale("admin", uid(), bad)

    def test_restart_preserves_identity_and_committed_event_clock_floor(self):
        self.clock.advance(1234)
        self.entity()
        highwater = self.world.now()
        old_epoch = self.store.epoch
        self.store.close()
        self.clock.advance(60_000)
        self.open()
        self.assertEqual(self.world.now(), highwater)
        self.assertEqual(self.world.seed, 2**64 - 1)
        self.assertEqual(self.store.epoch, old_epoch + 1)
        with self.assertRaises(Conflict):
            World(self.store)

    def test_local_process_lock(self):
        child = subprocess.run([sys.executable, "-c",
                                "from lostzone import Store; import sys; Store(sys.argv[1])", str(self.path)],
                               env={**__import__("os").environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                               capture_output=True, timeout=10)
        self.assertNotEqual(child.returncode, 0)

    def test_transaction_rollback_has_no_event_or_outbox(self):
        before = self.store.events()
        command = uid()
        def fail(tx):
            tx.execute("INSERT INTO entity VALUES(?, 'NPC','cordon','a',1,1,1,'{}')", (uid(),))
            self.store.event(tx, "test", "Failure", {}, self.world.now())
            raise RuntimeError("injected")
        with self.assertRaises(RuntimeError):
            self.store.command("a", command, {"test": 1}, fail)
        self.assertEqual(self.store.events(), before)
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM command_result WHERE id=?", (command,)).fetchone())
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 0)

    def test_idempotency_key_payload_conflict_and_inbox_atomicity(self):
        key = uid()
        self.assertEqual(self.store.command("a", key, {"x": 1}, lambda tx: {"ok": 1}), {"ok": 1})
        self.assertEqual(self.store.command("a", key, {"x": 1}, lambda tx: self.fail("repeated effect")), {"ok": 1})
        with self.assertRaises(Conflict):
            self.store.command("a", key, {"x": 2}, lambda tx: {})
        message = uid()
        apply = lambda tx: {"sequence": self.store.event(tx, "bus", "Message", {}, self.world.now())}
        result = self.store.consume("receiver", message, {"x": 1}, apply)
        self.assertEqual(self.store.consume("receiver", message, {"x": 1}, apply), result)
        with self.assertRaises(Conflict):
            self.store.consume("receiver", message, {"x": 2}, apply)
        pending = self.store.pending_outbox("receiver")
        self.store.ack_outbox("receiver", pending[0]["sequence"])
        self.assertEqual(len(self.store.pending_outbox("receiver")), len(pending) - 1)
        self.assertEqual(len(self.store.pending_outbox("another")), len(pending))

    def test_two_pickups_one_owner_and_state_conservation(self):
        npc = self.entity()
        item = self.item()
        commands = [uid() for _ in range(16)]
        def attempt(key):
            try:
                return self.move(key, item, npc)
            except Conflict:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, commands))
        self.assertEqual(sum(value is not None for value in results), 1)
        row = self.store.db.execute("SELECT * FROM item WHERE id=?", (item,)).fetchone()
        self.assertEqual((row["kind"], row["holder"], row["quantity"], row["version"]), ("NPC", npc, 1, 2))
        self.assertEqual(json.loads(row["state"])["ammo"], 17)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0], 1)

    def test_duplicate_pickup_result_survives_restart(self):
        npc, item, key = self.entity(), self.item(), uid()
        old = self.move(key, item, npc)
        self.store.close()
        self.open()
        self.assertEqual(self.move(key, item, npc), old)
        self.assertEqual(self.store.db.execute("SELECT version FROM item WHERE id=?", (item,)).fetchone()[0], 2)

    def test_container_access_capacity_and_no_reroll(self):
        npc, player = self.entity(), self.character()
        stash = self.entity("STASH", policy="PLAYER_ONLY", owner=player, capacity=1)
        item = self.item()
        with self.assertRaises(Conflict):
            self.move(uid(), item, npc, target_kind="STASH", target_holder=stash)
        self.move(uid(), item, player, target_kind="STASH", target_holder=stash)
        another = self.item()
        with self.assertRaises(Conflict):
            self.move(uid(), another, player, target_kind="STASH", target_holder=stash)
        with self.assertRaises(Conflict):
            self.move(uid(), item, npc, "STASH", stash, version=2)
        self.store.close()
        self.open()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item WHERE holder=?", (stash,)).fetchone()[0], 1)

    def test_permanent_death_and_cleanup_preserve_every_item(self):
        npc = self.entity()
        items = [self.item("NPC", npc) for _ in range(5)]
        self.ownership.kill("a", uid(), npc, self.a, 1, "combat")
        with self.assertRaises(Conflict):
            self.ownership.update_entity("a", uid(), npc, self.a, 2, {"health": 1})
        result = self.ownership.cleanup_corpse("a", uid(), npc, self.a, 2)
        self.assertEqual(set(result["items"]), set(items))
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?", (npc,)).fetchone()
        self.assertEqual(row["alive"], 0)
        self.assertTrue(json.loads(row["state"])["corpse_removed"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item WHERE kind='WORLD' AND holder='cordon'").fetchone()[0], 5)
        with self.assertRaises(Conflict):
            self.ownership.create_entity("a", uid(), npc, "NPC", "cordon", self.a, {})

    def test_fencing_after_location_expiry_preserves_state(self):
        npc = self.entity()
        item = self.item("NPC", npc)
        self.clock.advance(16000)
        with self.assertRaises(Conflict):
            self.ownership.update_entity("a", uid(), npc, self.a, 1, {})
        new = self.world.claim_location("new-a", uid(), "cordon")["fence"]
        self.assertEqual(new, self.a + 1)
        self.ownership.recover_location("new-a", uid(), "cordon", new)
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?", (npc,)).fetchone()
        self.assertEqual((row["writer"], row["fence"]), ("new-a", new))
        self.assertEqual(json.loads(row["state"])["health"], .75)
        self.assertEqual(self.store.db.execute("SELECT holder FROM item WHERE id=?", (item,)).fetchone()[0], npc)

    def test_lease_clock_rollback_blocks_mutation(self):
        self.clock.utc_ns -= 1_000_000
        with self.assertRaises(Unavailable):
            self.entity()

    def prepare_character(self):
        character = self.character()
        item = self.item("PLAYER", character)
        key = uid()
        prepared = self.transfers.prepare("a", key, character, "cordon", self.a, "garbage", 1)
        return character, item, key, prepared

    def test_transfer_frozen_source_repeated_claim_commit_and_no_duplicate(self):
        character, item, key, prepared = self.prepare_character()
        self.assertEqual(self.transfers.prepare("a", key, character, "cordon", self.a, "garbage", 1), prepared)
        with self.assertRaises(Conflict):
            self.ownership.update_entity("a", uid(), character, self.a, 2, {})
        with self.assertRaises(Conflict):
            self.move(uid(), item, character, "PLAYER", character, "WORLD", "cordon")
        claim = self.transfers.claim("b", uid(), prepared["token"], self.b)
        self.assertEqual(self.transfers.claim("b", uid(), prepared["token"], self.b), claim)
        committed = self.transfers.commit("b", uid(), prepared["transfer_id"], self.b)
        self.assertEqual(self.transfers.commit("b", uid(), prepared["transfer_id"], self.b), committed)
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?", (character,)).fetchone()
        self.assertEqual((row["location"], row["writer"]), ("garbage", "b"))
        self.assertEqual(json.loads(row["state"])["radiation"], .14)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM character").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT holder FROM item WHERE id=?", (item,)).fetchone()[0], character)
        with self.assertRaises(Conflict):
            self.transfers.abort("a", uid(), prepared["transfer_id"], self.a)

    def test_transfer_restart_and_expiry_after_claim_cannot_resume_source(self):
        character, _, _, prepared = self.prepare_character()
        self.transfers.claim("b", uid(), prepared["token"], self.b)
        self.store.close()
        self.clock.advance(61000)
        self.open()
        new_a = self.world.claim_location("a", uid(), "cordon")["fence"]
        new_b = self.world.claim_location("replacement-b", uid(), "garbage")["fence"]
        with self.assertRaises(Conflict):
            self.transfers.abort("a", uid(), prepared["transfer_id"], new_a)
        with self.assertRaises(Conflict):
            self.transfers.commit("b", uid(), prepared["transfer_id"], self.b)
        self.transfers.claim("replacement-b", uid(), prepared["token"], new_b)
        self.transfers.commit("replacement-b", uid(), prepared["transfer_id"], new_b)
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?", (character,)).fetchone()
        self.assertEqual((row["writer"], row["fence"]), ("replacement-b", new_b))

    def test_expired_unclaimed_transfer_can_only_abort(self):
        character, _, _, prepared = self.prepare_character()
        self.clock.advance(61000)
        a = self.world.claim_location("a", uid(), "cordon")["fence"]
        b = self.world.claim_location("b", uid(), "garbage")["fence"]
        with self.assertRaises(Conflict):
            self.transfers.claim("b", uid(), prepared["token"], b)
        self.transfers.abort("a", uid(), prepared["transfer_id"], a)
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?", (character,)).fetchone()
        self.assertEqual((row["writer"], row["fence"]), ("a", a))

    def test_transfer_token_tamper_wrong_destination(self):
        _, _, _, prepared = self.prepare_character()
        with self.assertRaises(Invalid):
            self.transfers.claim("b", uid(), prepared["token"][:-1] + "z", self.b)
        with self.assertRaises(Conflict):
            self.transfers.claim("a", uid(), prepared["token"], self.a)

    def test_target_capacity_reservation_and_global_conservation(self):
        self.world.claim_location("b", uid(), "garbage", capacity=1)
        _, _, _, prepared = self.prepare_character()
        other = self.character("second")
        with self.assertRaises(Conflict):
            self.transfers.prepare("a", uid(), other, "cordon", self.a, "garbage", 1)
        self.transfers.claim("b", uid(), prepared["token"], self.b)
        self.transfers.commit("b", uid(), prepared["transfer_id"], self.b)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM player_session WHERE state='ACTIVE'").fetchone()[0], 2)

    def test_group_handoff_keeps_member_ids_dead_members_and_items(self):
        members = [self.entity(), self.entity("MUTANT")]
        item = self.item("NPC", members[0])
        self.ownership.kill("a", uid(), members[1], self.a, 1, "anomaly")
        group = self.entity("GROUP", {"member_ids": members, "route": "r1"})
        prepared = self.transfers.prepare("a", uid(), group, "cordon", self.a, "garbage", 1)
        self.transfers.claim("b", uid(), prepared["token"], self.b)
        self.transfers.commit("b", uid(), prepared["transfer_id"], self.b)
        rows = self.store.db.execute("SELECT * FROM entity ORDER BY id").fetchall()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["location"] == "garbage" and row["writer"] == "b" for row in rows))
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?", (members[1],)).fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT holder FROM item WHERE id=?", (item,)).fetchone()[0], members[0])

    def test_snapshot_consistency_and_integrity(self):
        npc = self.entity()
        self.item("NPC", npc)
        snapshot = self.store.snapshot()
        records = self.store.read_snapshot(snapshot["id"])
        self.assertEqual(records["watermark"], self.store.events()[-1]["sequence"])
        self.assertEqual(records["records"]["item"][0]["holder"], npc)
        with self.store.transaction() as tx:
            tx.execute("UPDATE snapshot SET payload='{}' WHERE id=?", (snapshot["id"],))
        with self.assertRaises(Unavailable):
            self.store.read_snapshot(snapshot["id"])

    def test_schema_migration_preserves_world_members_and_inventory(self):
        npc, mutant = self.entity(), self.entity("MUTANT")
        group = self.entity("GROUP", {"member_ids": [npc, mutant]})
        item = self.item("NPC", npc)
        with self.store.transaction() as tx:
            tx.execute("DROP TABLE quest_event")
            tx.execute("DROP TABLE group_member")
            tx.execute("DROP TABLE world_state")
            tx.execute("UPDATE metadata SET value='1' WHERE key='schema'")
        self.store.close()
        self.open()
        self.assertEqual(self.store.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0], "2")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM group_member WHERE group_id=?", (group,)).fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT holder FROM item WHERE id=?", (item,)).fetchone()[0], npc)

    def test_existing_empty_or_unknown_database_fails_closed(self):
        empty = Path(self.folder.name) / "empty.sqlite"
        empty.touch()
        with self.assertRaises(Unavailable):
            Store(empty)
        with self.store.transaction() as tx:
            tx.execute("UPDATE metadata SET value='999' WHERE key='schema'")
        self.store.close()
        with self.assertRaises(Unavailable):
            Store(self.path)

    def test_group_member_cannot_be_duplicated_or_silently_replaced(self):
        npc = self.entity()
        group = self.entity("GROUP", {"member_ids": [npc]})
        with self.assertRaises(Conflict):
            self.entity("GROUP", {"member_ids": [npc]})
        with self.assertRaises(Conflict):
            self.ownership.update_entity("a", uid(), group, self.a, 1, {"member_ids": [uid()]})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM group_member").fetchone()[0], 1)

    def test_disconnect_resume_preserves_checkpoint_and_releases_admission(self):
        player = self.character()
        self.world.claim_location("a", uid(), "cordon", capacity=1)
        item = self.item("PLAYER", player)
        self.ownership.disconnect("a", uid(), player, self.a, 1, {"health": .42, "radiation": .33})
        replacement = self.character("other")
        with self.assertRaises(Conflict):
            self.ownership.resume("a", uid(), player, "cordon", self.a, 2)
        self.ownership.disconnect("a", uid(), replacement, self.a, 1, {"health": 1})
        resumed = self.ownership.resume("a", uid(), player, "cordon", self.a, 2)
        self.assertEqual(resumed["state"], {"health": .42, "radiation": .33})
        self.assertGreater(resumed["session_fence"], 1)
        self.assertEqual(self.store.db.execute("SELECT holder FROM item WHERE id=?", (item,)).fetchone()[0], player)

    def test_abort_to_full_source_keeps_checkpoint_without_exceeding_capacity(self):
        player = self.character()
        self.world.claim_location("a", uid(), "cordon", capacity=1)
        prepared = self.transfers.prepare("a", uid(), player, "cordon", self.a, "garbage", 1)
        self.character("new-arrival")
        aborted = self.transfers.abort("a", uid(), prepared["transfer_id"], self.a)
        self.assertEqual(aborted["session_state"], "DISCONNECTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM player_session WHERE state='ACTIVE'").fetchone()[0], 1)
        self.assertEqual(self.transfers.abort("a", uid(), prepared["transfer_id"], self.a), aborted)

    def test_process_crash_before_and_after_commit_preserves_one_ledger(self):
        npc, item = self.entity(), self.item()
        command = uid()
        code = """
import os,sys
from lostzone import Store,World
s=Store(sys.argv[1]);w=World(s,world_id=71,seed=2**64-1)
def apply(tx):
 tx.execute("UPDATE item SET kind='NPC',holder=?,version=version+1 WHERE id=?",(sys.argv[2],sys.argv[3]))
 s.event(tx,'item:'+sys.argv[3],'ItemMoved',{'holder':sys.argv[2]},w.now())
 if sys.argv[5]=='before': os._exit(23)
 return {'ok':True}
s.command('a',sys.argv[4],{'move':sys.argv[3]},apply)
os._exit(24)
"""
        environment = {**__import__("os").environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
        for phase, expected_kind, expected_version in (("before", "WORLD", 1), ("after", "NPC", 2)):
            self.store.close()
            child = subprocess.run([sys.executable, "-c", code, str(self.path), npc, item, command, phase],
                                   env=environment, capture_output=True, timeout=10)
            self.assertEqual(child.returncode, 23 if phase == "before" else 24, child.stderr)
            self.open()
            row = self.store.db.execute("SELECT * FROM item WHERE id=?", (item,)).fetchone()
            self.assertEqual((row["kind"], row["version"]), (expected_kind, expected_version))
            self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0], 1)
            saved = self.store.db.execute("SELECT * FROM command_result WHERE actor='a' AND id=?", (command,)).fetchone()
            self.assertEqual(saved is not None, phase == "after")
        self.assertEqual(self.store.command("a", command, {"move": item}, lambda tx: self.fail("commit repeated after crash")), {"ok": True})


if __name__ == "__main__":
    unittest.main()
