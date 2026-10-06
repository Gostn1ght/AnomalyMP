import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.scheduler import Scheduler, UnavailableHandler
from lostzone.store import Unavailable


def uid():
    return uuid.uuid4().hex


class MutationBarrierTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name)/"world.db")
        self.ns = 0
        self.world = World(self.store,scale=1,monotonic=lambda:self.ns)
        self.scheduler = Scheduler(self.world)
        self.scheduler.handlers["Dependency"] = self.resolve

    def tearDown(self):
        self.store.close();self.folder.cleanup()

    def resolve(self,tx,event):
        tx.execute("INSERT INTO world_state VALUES('dependency',1,'{}') ON CONFLICT(name) DO UPDATE SET version=version+1")
        return {"at":self.world.now()},True

    def queue(self,count=1,kind="Dependency"):
        with self.store.transaction() as tx:
            for index in range(count):
                self.scheduler.schedule_in(tx,uid(),100+index,"world:dependency",1,kind,{})
        self.ns=1_000_000_000

    def pending(self):
        return self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='PENDING'").fetchone()[0]

    def test_command_and_due_events_share_one_frozen_instant(self):
        self.queue(2)
        original = self.resolve
        def delayed(tx,event):
            result = original(tx,event)
            self.ns+=100_000_000
            return result
        self.scheduler.handlers["Dependency"] = delayed
        result = self.world.set_state("admin",uid(),"territory",0,{})
        rows = self.store.db.execute("SELECT result FROM scheduled_event").fetchall()
        self.assertEqual([json.loads(row[0])["at"] for row in rows],[1000,1000])
        self.assertEqual(self.store.events()[-1]["sequence"],result["event"])
        self.assertEqual(self.store.events()[-1]["world_ms"],1000)
        self.assertEqual(self.world.now(),1200)
        self.assertIsNone(self.world._mutation_cut)

    def test_stale_command_rolls_back_dependency_and_evidence(self):
        self.queue()
        with self.assertRaises(Conflict):
            self.world.set_state("admin",uid(),"territory",42,{})
        self.assertEqual(self.pending(),1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_state").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM command_result").fetchone()[0],0)
        self.assertIsNone(self.world._mutation_cut)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),0)

    def test_work_count_exhaustion_rolls_back_then_background_runner_unblocks(self):
        self.queue(65)
        with patch("lostzone.scheduler.time.monotonic",return_value=0):
            with self.assertRaises(Unavailable):
                self.world.set_state("admin",uid(),"territory",0,{})
            self.assertEqual(self.pending(),65)
            self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_state").fetchone()[0],0)
            self.assertEqual(self.scheduler.run_due(limit=64,budget_ms=1000),64)
            self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),0)
        self.assertEqual(self.store.db.execute("SELECT version FROM world_state WHERE name='dependency'").fetchone()[0],65)

    def test_time_budget_exhaustion_rolls_back_partial_catchup(self):
        self.queue(2)
        with patch("lostzone.scheduler.time.monotonic",side_effect=[0,0,.006]):
            with self.assertRaises(Unavailable):
                self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_state").fetchone()[0],0)
        self.assertIsNone(self.world._mutation_cut)

    def test_unavailable_handler_holds_command_and_recovers_after_registration(self):
        self.queue(kind="MissingResolver")
        with self.assertRaises(UnavailableHandler):
            self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),1)
        self.assertIsNone(self.world._mutation_cut)
        self.scheduler.handlers["MissingResolver"] = self.resolve
        self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),0)

    def test_replay_does_not_catch_up_or_change_existing_result(self):
        key=uid();result=self.world.set_state("admin",key,"territory",0,{})
        self.queue()
        self.assertEqual(self.world.set_state("admin",key,"territory",0,{}),result)
        self.assertEqual(self.pending(),1)
        self.world.set_state("admin",uid(),"territory",1,{})
        self.assertEqual(self.pending(),0)

    def test_failed_authorization_precedes_due_event_application(self):
        self.queue()
        def refuse(tx):
            raise Conflict("not the location owner")
        with self.assertRaises(Conflict):
            self.store.command("other",uid(),{},self.world.mutation(lambda tx:{}),authorize=refuse)
        self.assertEqual(self.pending(),1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_state").fetchone()[0],0)

    def test_scale_anchor_uses_frozen_cut_not_handler_elapsed_time(self):
        self.queue()
        def delayed(tx,event):
            self.ns+=100_000_000
            return self.resolve(tx,event)
        self.scheduler.handlers["Dependency"]=delayed
        result=self.world.set_scale("admin",uid(),2)
        self.assertEqual(result["world_ms"],1000)
        self.assertEqual(self.world.now(),1200)
        self.assertEqual(self.pending(),0)

    def test_recursive_mutation_refused_without_leaving_frozen_clock(self):
        self.queue()
        self.scheduler.handlers["Dependency"] = lambda tx,event:self.world.mutation(lambda nested:{ })(tx)
        with self.assertRaises(Unavailable):
            self.world.set_state("admin",uid(),"territory",0,{})
        self.assertEqual(self.pending(),1)
        self.assertIsNone(self.world._mutation_cut)
