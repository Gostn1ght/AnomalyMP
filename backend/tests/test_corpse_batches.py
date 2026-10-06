import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.ownership import Ownership
from lostzone.scheduler import Scheduler
from lostzone.quests import Quests


def uid():
    return uuid.uuid4().hex


class CorpseBatchesTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/"world.db"
        self.ns=0;self.utc=1_800_000_000_000_000_000
        self.open()
        self.fence=self.world.claim_location("a",uid(),"cordon")["fence"]
        self.corpse=uid();self.player=uid()
        self.ownership.create_entity("a",uid(),self.corpse,"NPC","cordon",self.fence,{"position":[1,2,3],"health":1})
        self.ownership.create_entity("a",uid(),self.player,"CHARACTER","cordon",self.fence,{"position":[1,2,3],"health":1},account="player")

    def open(self):
        self.store=Store(self.path)
        self.world=World(self.store,monotonic=lambda:self.ns,wall=lambda:self.utc)
        self.ownership=Ownership(self.world);self.scheduler=Scheduler(self.world)

    def tearDown(self):
        self.store.close();self.folder.cleanup()

    def populate(self,count=130,payload=""):
        self.ids=[f"{index:032x}" for index in range(count)]
        state=json.dumps({"condition":.51,"attachments":["scope"],"ammo":17,"payload":payload})
        with self.store.transaction() as tx:
            tx.executemany("INSERT INTO item VALUES(?,'wpn','NPC',?,3,1,?)",[(item,self.corpse,state) for item in self.ids])
        self.death=self.ownership.kill("a",uid(),self.corpse,self.fence,1,"combat")

    def cleanup(self,actor="a",fence=None):
        version=self.store.db.execute("SELECT version FROM entity WHERE id=?",(self.corpse,)).fetchone()[0]
        return self.ownership.cleanup_corpse(actor,uid(),self.corpse,fence or self.fence,version)

    def state(self):
        return json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(self.corpse,)).fetchone()[0])

    def count(self,kind):
        return self.store.db.execute("SELECT COUNT(*) FROM item WHERE kind=?",(kind,)).fetchone()[0]

    def assert_preserved(self,world_count=None):
        if world_count is not None:
            self.assertEqual(self.count("WORLD"),world_count)
        rows=self.store.db.execute("SELECT * FROM item ORDER BY id").fetchall()
        self.assertEqual([row["id"] for row in rows],self.ids)
        for row in rows:
            state=json.loads(row["state"])
            self.assertEqual((row["quantity"],state["condition"],state["attachments"],state["ammo"]),(3,.51,["scope"],17))
            if row["kind"]=="WORLD":
                self.assertEqual((row["holder"],state["drop_position"],state["dropped_from_corpse"]),("cordon",[1,2,3],self.corpse))

    def test_large_inventory_finishes_in_durable_batches_and_retries_do_not_repeat(self):
        self.populate()
        key=uid();result=self.ownership.cleanup_corpse("a",key,self.corpse,self.fence,2)
        self.assertEqual((len(result["items"]),result["complete"]),(64,False))
        self.assertFalse(self.state()["corpse_removed"])
        self.assertEqual(self.ownership.cleanup_corpse("a",key,self.corpse,self.fence,2),result)
        self.assertEqual(self.scheduler.run_due(limit=1,budget_ms=1000),1)
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(128,2))
        self.assertFalse(self.state()["corpse_removed"])
        self.store.close();self.open()
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.assertTrue(self.state()["corpse_removed"])
        self.assertNotIn("corpse_cleanup_pending",self.state())
        self.assert_preserved(130)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='CorpseRemoved'").fetchone()[0],1)
        before=self.store.events();self.assertTrue(self.cleanup()["complete"])
        self.assertEqual(self.store.events(),before)

    def test_batch_journal_failure_preserves_prior_commit_and_retries_remaining_items(self):
        self.populate();self.cleanup()
        before=self.store.events();original=self.store.event
        def fail(tx,aggregate,kind,*args,**kwargs):
            if kind=="CorpseCleanupProgress":
                raise RuntimeError("injected cleanup journal failure")
            return original(tx,aggregate,kind,*args,**kwargs)
        self.store.event=fail
        try:
            with self.assertRaises(RuntimeError):
                self.scheduler.run_due(limit=1,budget_ms=1000)
        finally:
            self.store.event=original
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(64,66))
        self.assertEqual(self.store.events(),before)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),2)
        self.assert_preserved(130)

    def test_player_pickup_during_cleanup_is_not_duplicated_or_discarded(self):
        self.populate(131);self.cleanup()
        item=self.ids[-1]
        self.ownership.move_item("a",uid(),item,"cordon",self.fence,2,"CORPSE",self.corpse,"PLAYER",self.player,self.player)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),2)
        self.assertEqual((self.count("WORLD"),self.count("PLAYER"),self.count("CORPSE")),(130,1,0))
        self.assert_preserved(130)

    def test_quest_pin_added_between_batches_holds_body_without_blocking_scheduler(self):
        quests=Quests(self.world,{"body":{"steps":[{"type":"EntityDied","target":self.corpse}],
                                      "requirements":[{"entity_id":self.corpse,"alive_required":False}]}})
        self.populate();self.cleanup()
        quests.grant("a",uid(),self.player,self.fence,"body")
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.assertFalse(self.state()["corpse_removed"])
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(64,66))
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        quests.progress("a",uid(),self.player,self.fence,"body",1,self.death["event"])
        self.cleanup();self.scheduler.run_due(budget_ms=1000)
        self.assertTrue(self.state()["corpse_removed"]);self.assert_preserved(130)

    def test_old_cleanup_job_cannot_write_after_new_location_owner_recovers(self):
        self.populate();self.cleanup();self.utc+=16_000_000_000
        fresh=self.world.claim_location("new-a",uid(),"cordon")["fence"]
        self.ownership.recover_location("new-a",uid(),"cordon",fresh)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(64,66))
        self.cleanup("new-a",fresh);self.scheduler.run_due(budget_ms=1000)
        self.assert_preserved(130)

    def test_large_item_states_use_byte_bounded_batches_without_truncation(self):
        self.populate(14,"я"*150000)
        result=self.cleanup()
        self.assertGreater(len(result["items"]),0);self.assertLess(len(result["items"]),14)
        self.assertFalse(result["complete"])
        self.scheduler.run_due(budget_ms=1000)
        self.assert_preserved(14)
        for row in self.store.db.execute("SELECT state FROM item"):
            self.assertEqual(json.loads(row[0])["payload"],"я"*150000)

    def test_removed_corpse_cannot_receive_new_items_in_an_invisible_inventory(self):
        self.populate(1);self.cleanup()
        with self.assertRaises(Conflict):
            self.ownership.create_item("a",uid(),uid(),"food","cordon",self.fence,"CORPSE",self.corpse)
        self.assert_preserved(1)

    def test_continuation_queue_failure_rolls_back_first_batch_but_not_death(self):
        self.populate();before=self.store.events()
        original=Scheduler.schedule_in
        def fail(scheduler,tx,event_id,due,aggregate,version,event_type,payload,priority=0):
            if event_type=="CorpseCleanupBatch":
                raise RuntimeError("injected continuation queue failure")
            return original(scheduler,tx,event_id,due,aggregate,version,event_type,payload,priority)
        with patch.object(Scheduler,"schedule_in",fail):
            with self.assertRaises(RuntimeError):
                self.cleanup()
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(0,130))
        self.assertFalse(self.state()["corpse_removed"])
        self.assertNotIn("corpse_cleanup_pending",self.state())
        self.assertEqual(self.store.events(),before)
        self.cleanup();self.scheduler.run_due(budget_ms=1000)
        self.assert_preserved(130)

    def test_oversized_first_state_refuses_before_reading_second_item(self):
        self.populate(2)
        with self.store.transaction() as tx:
            tx.execute("UPDATE item SET state=? WHERE id=?",(json.dumps({"payload":"x"*(5*1024*1024)}),self.ids[0]))
        before=self.store.events()
        from contextlib import contextmanager
        original_transaction=self.store.transaction
        class Guarded:
            def __init__(self,tx):
                self.tx=tx
            def execute(self,sql,*args):
                cursor=self.tx.execute(sql,*args)
                if sql=="SELECT * FROM item WHERE kind='CORPSE' AND holder=? ORDER BY id LIMIT 64":
                    def first_only():
                        yield next(iter(cursor))
                        raise AssertionError("cleanup read beyond oversized first state")
                    return first_only()
                return cursor
        @contextmanager
        def guarded_transaction():
            with original_transaction() as tx:
                yield Guarded(tx)
        self.store.transaction=guarded_transaction
        try:
            with self.assertRaises(Conflict):
                self.cleanup()
        finally:
            self.store.transaction=original_transaction
        self.assertEqual((self.count("WORLD"),self.count("CORPSE")),(0,2))
        self.assertFalse(self.state()["corpse_removed"])
        self.assertEqual(self.store.events(),before)

    def test_crash_before_v3_migration_commit_preserves_old_schema_and_inventory(self):
        self.populate(2)
        with self.store.transaction() as tx:
            tx.execute("DROP INDEX item_holder")
            tx.execute("CREATE INDEX item_holder ON item(kind,holder)")
            tx.execute("UPDATE metadata SET value='3' WHERE key='schema'")
        self.store.close()
        child=subprocess.run([sys.executable,"-c",
                              "import os,sqlite3,sys; from lostzone.store import MIGRATE_V3; "
                              "db=sqlite3.connect(sys.argv[1],isolation_level=None); "
                              "db.executescript('BEGIN IMMEDIATE;'+MIGRATE_V3); os._exit(29)",str(self.path)],
                             env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1])},
                             capture_output=True,timeout=10)
        self.assertEqual(child.returncode,29,child.stderr)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as probe:
            self.assertEqual(probe.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0],"3")
            self.assertEqual([row[2] for row in probe.execute("PRAGMA index_info(item_holder)")],["kind","holder"])
            self.assertEqual(probe.execute("SELECT COUNT(*) FROM item WHERE kind='CORPSE'").fetchone()[0],2)
        self.open();self.cleanup();self.assert_preserved(2)

    def test_v3_index_migration_preserves_data_and_avoids_inventory_sort(self):
        self.populate()
        before=[tuple(row) for row in self.store.db.execute("SELECT * FROM item ORDER BY id")]
        with self.store.transaction() as tx:
            tx.execute("DROP INDEX item_holder")
            tx.execute("CREATE INDEX item_holder ON item(kind,holder)")
            tx.execute("UPDATE metadata SET value='3' WHERE key='schema'")
        self.store.close();self.open()
        self.assertEqual(self.store.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0],"4")
        self.assertEqual([tuple(row) for row in self.store.db.execute("SELECT * FROM item ORDER BY id")],before)
        plan=[row[3] for row in self.store.db.execute("EXPLAIN QUERY PLAN SELECT * FROM item WHERE kind='CORPSE' AND holder=? ORDER BY id LIMIT 64",(self.corpse,))]
        self.assertTrue(any("item_holder" in row for row in plan))
        self.assertFalse(any("TEMP B-TREE" in row for row in plan),plan)


if __name__=="__main__":
    unittest.main()
