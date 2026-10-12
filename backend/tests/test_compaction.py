"""Journal retention and compaction (doc 43 G11)."""
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Invalid, Unavailable


def uid():
    return uuid.uuid4().hex


class CompactionTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.ns = [1_000_000_000]
        self.open()

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, world_id=9, seed=5, monotonic=lambda: self.ns[0])

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def emit(self, aggregate, n=1):
        out = []
        for _ in range(n):
            self.ns[0] += 1_000_000
            with self.store.transaction() as tx:
                out.append(self.store.event(tx, aggregate, "Changed", {"n": len(out)}, self.world.now()))
        return out

    def ack(self, consumer, sequences):
        for s in sequences:
            self.store.ack_outbox(consumer, s)

    def sequences(self):
        return [r[0] for r in self.store.db.execute("SELECT sequence FROM world_event ORDER BY sequence")]

    def test_only_covered_delivered_history_goes(self):
        a = self.emit("npc-a", 3)          # 1..3
        b = self.emit("npc-b", 2)          # 4..5
        self.ack("loc_a", a + b)
        self.ack("loc_b", a + b[:1])       # loc_b has not seen b[1]
        snap = self.store.snapshot()
        late = self.emit("npc-a", 1)       # after the snapshot
        result = self.store.compact(snap["id"], ["loc_a", "loc_b"])
        # a[0], a[1] go; a[2] stays (newest of npc-a below the watermark is
        # not newest overall, but late[0] is newer: a[2] goes too); b[0] goes;
        # b[1] is undelivered to loc_b; late is above the watermark.
        self.assertEqual(self.sequences(), [b[1]] + late)
        self.assertEqual(result["removed"], 4)
        self.assertEqual(result["floor"], snap["watermark"])
        # readers below the floor restart from the snapshot, above it page on
        with self.assertRaises(Unavailable):
            self.store.events(after=0)
        page = self.store.events(after=snap["watermark"])
        self.assertEqual([e["sequence"] for e in page], late)
        # undelivered outbox is still pending for its consumer
        self.assertEqual([e["sequence"] for e in self.store.pending_outbox("loc_b")], [b[1]] + late)

    def test_newest_event_of_an_aggregate_survives_and_sequences_continue(self):
        a = self.emit("npc-a", 3)
        self.ack("loc", a)
        snap = self.store.snapshot()
        self.store.compact(snap["id"], ["loc"])
        self.assertEqual(self.sequences(), [a[2]])
        nxt = self.emit("npc-a", 1)[0]
        row = self.store.db.execute("SELECT aggregate_sequence FROM world_event WHERE sequence=?", (nxt,)).fetchone()
        self.assertEqual(row[0], 4)
        self.assertGreater(nxt, a[2])

    def test_quest_evidence_is_kept(self):
        a = self.emit("npc-q", 3)
        self.ack("loc", a)
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,?,?,?,?,?,?,?)", ("c" * 32, "CHARACTER", "cordon", "x", 1, 1, 1, "{}"))
            tx.execute("INSERT INTO character VALUES(?,?,?,?)", ("c" * 32, "acc", 1, "{}"))
            tx.execute("INSERT INTO quest VALUES(?,?,?,?,?,?)", ("c" * 32, "q1", 0, 1, "{}", 0))
            tx.execute("INSERT INTO quest_event VALUES(?,?,?)", ("c" * 32, "q1", a[0]))
        snap = self.store.snapshot()
        self.store.compact(snap["id"], ["loc"])
        self.assertEqual(self.sequences(), [a[0], a[2]])
        self.assertIsNone(self.store.db.execute("PRAGMA foreign_key_check").fetchone())

    def test_snapshot_retention_and_refusals(self):
        a = self.emit("npc-a", 2)
        self.ack("loc", a)
        snaps = []
        for _ in range(4):
            snaps.append(self.store.snapshot())
            self.ack("loc", self.emit("npc-a", 1))
        result = self.store.compact(snaps[2]["id"], ["loc"], keep_snapshots=2)
        left = {r[0] for r in self.store.db.execute("SELECT id FROM snapshot")}
        self.assertEqual(left, {snaps[2]["id"], snaps[3]["id"]})
        self.assertEqual(result["snapshots_removed"], 2)
        # an older snapshot than the floor: nothing to do
        again = self.store.compact(snaps[2]["id"], ["loc"])
        self.assertEqual(again["removed"], 0)
        # corrupted snapshot: refused, journal untouched
        before = self.sequences()
        self.store.db.execute("UPDATE snapshot SET payload=payload||' ' WHERE id=?", (snaps[3]["id"],))
        with self.assertRaises(Unavailable):
            self.store.compact(snaps[3]["id"], ["loc"])
        self.assertEqual(self.sequences(), before)
        for bad in ([], None, ["bad consumer!"]):
            with self.assertRaises(Invalid):
                self.store.compact(snaps[2]["id"], bad)
        with self.assertRaises(Invalid):
            self.store.compact(uid(), ["loc"])

    def test_floor_and_projections_survive_restart(self):
        a = self.emit("npc-a", 3)
        self.ack("loc", a)
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,?,?,?,?,?,?,?)", ("e" * 32, "NPC", "cordon", "x", 1, 7, 1, '{"hp":1}'))
        snap = self.store.snapshot()
        self.store.compact(snap["id"], ["loc"])
        self.store.close()
        self.open()
        self.assertEqual(self.store.journal_floor(), snap["watermark"])
        with self.assertRaises(Unavailable):
            self.store.events(after=0)
        row = self.store.db.execute("SELECT version,state FROM entity WHERE id=?", ("e" * 32,)).fetchone()
        self.assertEqual(tuple(row), (7, '{"hp":1}'))
        # the snapshot the journal starts from is still readable and verified
        self.assertEqual(self.store.read_snapshot(snap["id"])["watermark"], snap["watermark"])


if __name__ == "__main__":
    unittest.main()
