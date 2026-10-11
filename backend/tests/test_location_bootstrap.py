import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid, Unavailable
from lostzone.http import Dispatcher
from lostzone.location_bootstrap import LocationBootstrap, MAX_BYTES, MAX_ROWS


def uid():
    return uuid.uuid4().hex


class LocationBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "world.db")
        self.ns = 0
        self.world = World(self.store, world_id=71, seed=2**64-1, scale=1,
                           monotonic=lambda: self.ns, wall=lambda: 1_000_000_000 + self.ns)
        self.dispatcher = Dispatcher(self.world, b"k"*32)
        self.pager = LocationBootstrap(self.world, monotonic=lambda: self.ns)
        self.fence = self.world.claim_location("a", uid(), "cordon")["fence"]
        self.other_fence = self.world.claim_location("b", uid(), "garbage")["fence"]

    def tearDown(self):
        self.pager.close()
        self.dispatcher.location_bootstrap.close()
        self.store.close()
        self.folder.cleanup()

    def entity(self, number, location="cordon", actor="a", kind="NPC", **extra):
        key = f"{number:032x}"
        self.dispatcher.ownership.create_entity(actor, uid(), key, kind, location,
                                               self.fence if actor == "a" else self.other_fence,
                                               {"health": .8, **extra.pop("state", {})}, **extra)
        return key

    def item(self, number, kind="WORLD", holder="cordon", state=None):
        key = f"{number:032x}"
        self.dispatcher.ownership.create_item("a", uid(), key, "ammo", "cordon", self.fence,
                                             kind, holder, state=state or {})
        return key

    def first(self):
        return self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=uid())

    def rest(self, first):
        pages = [first]
        while pages[-1]["next"] is not None:
            self.assertLess(len(pages), 100)
            pages.append(self.pager.page("a", "cordon", self.fence, self.store.epoch,
                                        capture_id=first["capture_id"], after=pages[-1]["next"]))
        return pages

    def test_cut_stays_immutable_across_writes_and_other_location_is_excluded(self):
        for number in range(1, 71):
            self.entity(number)
        self.entity(100, "garbage", "b", state={"secret": "FOREIGN"})
        self.item(1000)
        first = self.first()
        self.assertEqual(len(first["entries"]), MAX_ROWS)
        self.dispatcher.ownership.update_entity("a", uid(), f"{70:032x}", self.fence, 1, {"health": .1})
        self.entity(71)
        self.item(1001)
        # Mutations on another map do not restart this pinned cut.
        self.dispatcher.ownership.update_entity("b", uid(), f"{100:032x}", self.other_fence, 1, {"secret": "FOREIGN-UPDATED"})
        pages = self.rest(first)
        entries = [entry for page in pages for entry in page["entries"]]
        self.assertEqual(len(entries), 71)
        self.assertEqual(len({entry["id"] for entry in entries}), 71)
        self.assertEqual(next(entry for entry in entries if entry["id"] == f"{70:032x}")["state"]["health"], .8)
        for page in pages:
            self.assertEqual(page["clock"], first["clock"])
            self.assertEqual(page["event_watermark"], first["event_watermark"])
            self.assertLessEqual(len(json.dumps({"result": page}).encode()), MAX_BYTES)
            self.assertNotIn("FOREIGN", json.dumps(page))

    def test_large_owned_inventories_and_empty_holders_advance_without_loss(self):
        holders = [self.entity(number) for number in range(1, 151)]
        items = {self.item(1000 + number, "NPC", holders[-1]) for number in range(130)}
        pages = self.rest(self.first())
        found = [entry["id"] for page in pages for entry in page["entries"] if entry["type"] == "item"]
        self.assertEqual(set(found), items)
        self.assertEqual(len(found), len(items))
        self.assertTrue(any(not page["entries"] and page["next"] for page in pages))

    def test_retry_cursor_tampering_cross_capture_and_expiry(self):
        for number in range(1, 66):
            self.entity(number)
        request = uid()
        first = self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=request)
        retry = self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=request)
        self.assertEqual(first, retry)
        with self.assertRaises(Invalid):
            self.pager.page("a", "cordon", self.fence, self.store.epoch, capture_id=first["capture_id"], after=first["next"] + "x")
        with self.assertRaises(Conflict):
            self.pager.page("b", "garbage", self.other_fence, self.store.epoch, capture_id=first["capture_id"], after=first["next"])
        with self.assertRaises(Conflict):
            self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=uid())
        self.ns = 15_000_000_000
        self.pager.reap()
        self.assertFalse(self.pager.captures)
        with self.assertRaises(Conflict):
            self.pager.page("a", "cordon", self.fence, self.store.epoch, capture_id=first["capture_id"], after=first["next"])

    def test_live_fencing_and_epoch_reject_old_capture(self):
        first = self.first()
        self.store.db.execute("UPDATE location_lease SET fence=fence+1 WHERE location='cordon'")
        with self.assertRaises(Conflict):
            self.pager.page("a", "cordon", self.fence, self.store.epoch, capture_id=first["capture_id"])
        with self.assertRaises(Conflict):
            self.pager.page("a", "cordon", self.fence+1, self.store.epoch, capture_id=first["capture_id"])
        self.store.db.execute("UPDATE world SET epoch=epoch+1")
        with self.assertRaises(Unavailable):
            self.pager.page("a", "cordon", self.fence+1, self.store.epoch, capture_id=first["capture_id"])

    def test_character_and_container_attachments_and_oversized_record_fail_closed(self):
        character = self.entity(1, kind="CHARACTER", account="account")
        container = self.entity(2, kind="CONTAINER", policy="PLAYER_ONLY", owner=character, capacity=7)
        first = self.first()
        rows = {row["id"]: row for row in first["entries"]}
        self.assertEqual(rows[character]["character"]["account"], "account")
        self.assertEqual(rows[character]["player_session"]["state"], "ACTIVE")
        self.assertEqual(rows[container]["container"]["policy"], "PLAYER_ONLY")
        self.pager.release("a", "cordon", self.fence, self.store.epoch, first["capture_id"])
        self.item(1000, state={"blob": "x" * 60000})
        with self.assertRaises(Conflict):
            self.first()

    def test_release_is_scoped_idempotent_and_readers_close_on_stop(self):
        first = self.first()
        db = self.pager.captures[first["capture_id"]]["db"]
        with self.assertRaises(Conflict):
            self.pager.release("b", "garbage", self.other_fence, self.store.epoch, first["capture_id"])
        self.assertEqual(self.pager.release("a", "cordon", self.fence, self.store.epoch, first["capture_id"]), {"released": True})
        self.assertEqual(self.pager.release("a", "cordon", self.fence, self.store.epoch, first["capture_id"]), {"released": True})
        self.assertFalse(self.pager.requests)
        with self.assertRaises(Exception):
            db.execute("SELECT 1")
        self.pager.close()
        with self.assertRaises(Unavailable):
            self.first()

    def test_byte_budget_unicode_and_query_indexes_bound_each_scan(self):
        for number in range(1, 4):
            self.entity(number, state={"text": "Ж" * 18000})
        pages = self.rest(self.first())
        self.assertEqual(sum(len(page["entries"]) for page in pages), 3)
        from lostzone.store import canonical
        for page in pages:
            self.assertLessEqual(len(canonical({"result": page}).encode()), MAX_BYTES)
        queries = (
            ("SELECT * FROM entity WHERE location=? AND writer=? AND fence=? AND id>? ORDER BY id LIMIT 65", ("cordon", "a", 1, "")),
            ("SELECT * FROM item WHERE holder=? AND kind NOT IN ('WORLD','DESTROYED') AND id>? ORDER BY id LIMIT 65", (f"{1:032x}", "")),
        )
        for query, args in queries:
            plan = " ".join(row[3] for row in self.store.db.execute("EXPLAIN QUERY PLAN " + query, args))
            self.assertIn("SEARCH", plan)
            self.assertNotIn("TEMP B-TREE", plan)

    def test_caller_cannot_modify_cut_clock_and_slot_budget_and_timer_fail_closed(self):
        request = uid()
        first = self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=request)
        first["clock"]["world_ms"] = 999999
        retry = self.pager.page("a", "cordon", self.fence, self.store.epoch, request_id=request)
        self.assertNotEqual(retry["clock"]["world_ms"], 999999)
        self.ns = 1
        self.pager.reap()
        self.ns = 0
        with self.assertRaises(Unavailable):
            self.pager.reap()
        # Stop must release readers even when the timer is broken.
        self.pager.close()
        self.assertFalse(self.pager.captures)


if __name__ == "__main__":
    unittest.main()
