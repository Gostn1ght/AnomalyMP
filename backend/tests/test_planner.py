import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World
from lostzone.economy import Catalog
from lostzone.encounters import Encounters
from lostzone.hazards import Hazards
from lostzone.offline import Offline
from lostzone.ownership import Ownership
from lostzone.planner import Planner
from lostzone.scheduler import Scheduler
from lostzone.store import Unavailable


def uid():
    return uuid.uuid4().hex


class PlannerTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/"world.db"
        self.ns = 0
        self.open()
        self.first,self.second,self.trap = uid(),uid(),uid()
        with self.store.transaction() as tx:
            for entity_id,kind,state in (
                (self.first,"NPC",{"position":[-10,0,0],"health":.2,"faction":"duty"}),
                (self.second,"MUTANT",{"position":[10,0,0],"health":.2,"faction":"bandit"}),
                (self.trap,"TRAP",{"position":[-5,0,0],"radius":1,"hazard_type":"fire","armed":True,"charges":1,"damage_bp":10000})):
                tx.execute("INSERT INTO entity VALUES(?,?,'cordon','offline:cordon',?,1,1,?)",(entity_id,kind,self.store.epoch,json.dumps(state)))
        self.world.set_state("admin",uid(),"relations",0,{"hostile":[["duty","bandit"]]})
        self.offline.start_route("admin",uid(),self.first,1,[[-10,0,0],[10,0,0]],1,42)

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store,world_id=123,seed=42,monotonic=lambda:self.ns,wall=lambda:1_800_000_000_000_000_000)
        self.scheduler = Scheduler(self.world)
        self.offline = Offline(self.world,self.scheduler)
        self.catalog = Catalog({})
        self.encounters = Encounters(self.world,self.offline,self.catalog)
        self.hazards = Hazards(self.world,self.offline,self.catalog)
        self.planner = Planner(self.world,self.encounters,self.hazards)

    def tearDown(self):
        self.store.close();self.folder.cleanup()

    def plan(self,key=None,seed=17,radius=1):
        return self.planner.plan("admin",key or uid(),"cordon",300000,seed,radius)

    def change(self,entity_id,**changes):
        with self.store.transaction() as tx:
            state = json.loads(tx.execute("SELECT state FROM entity WHERE id=?",(entity_id,)).fetchone()[0])
            state.update(changes)
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(json.dumps(state),entity_id))

    def state(self,event_id):
        return self.store.db.execute("SELECT * FROM scheduled_event WHERE id=?",(event_id,)).fetchone()

    def test_first_physical_hazard_wins_over_later_hostile_contact(self):
        result = self.plan()
        self.assertEqual(len(result["contacts"]),1)
        contact = result["contacts"][0]
        self.assertEqual((contact["type"],contact["due_ms"]),("offline_hazard",40000))
        self.ns = 4_001_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.second,)).fetchone()[0],1)
        self.assertEqual(self.state(contact["event_id"])["state"],"APPLIED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineCombat'").fetchone()[0],0)

    def test_earlier_fight_wins_over_later_trap(self):
        self.change(self.trap,position=[9.5,0,0],radius=.1)
        result = self.plan(radius=2)
        self.assertEqual([(row["type"],row["due_ms"]) for row in result["contacts"]],[("offline_combat",180000)])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],0)

    def test_combined_pass_preempts_existing_later_fight_and_keeps_its_actor_unharmed(self):
        old = self.encounters.plan_location("admin",uid(),"cordon",300000,17,1)["contacts"][0]
        result = self.plan()
        self.assertEqual((result["preempted_plans"],result["contacts"][0]["type"]),(1,"offline_hazard"))
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],1)

    def test_newly_placed_earlier_trap_preempts_valid_old_hazard_capture(self):
        old = self.plan()["contacts"][0]
        new_trap = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'TRAP','cordon','offline:cordon',?,1,1,?)",
                       (new_trap,self.store.epoch,json.dumps({"position":[-7,0,0],"radius":1,"hazard_type":"fire",
                                                             "armed":True,"charges":1,"damage_bp":10000})))
        result = self.plan()
        contact = result["contacts"][0]
        self.assertEqual((result["preempted_plans"],contact["due_ms"]),(1,20000))
        self.assertEqual(json.loads(self.state(contact["event_id"])["payload"])["hazard_id"],new_trap)
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")

    def test_retry_restart_and_new_seed_do_not_reroll_retained_capture(self):
        key = uid();result = self.plan(key)
        event_id = result["contacts"][0]["event_id"]
        payload = self.state(event_id)["payload"]
        self.store.close();self.open()
        self.assertEqual(self.plan(key),result)
        retained = self.plan(seed=999)["contacts"][0]
        self.assertEqual((retained["event_id"],retained["retained"]),(event_id,True))
        self.assertEqual(self.state(event_id)["payload"],payload)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],1)

    def test_preemption_and_new_plan_roll_back_together_when_capture_journal_fails(self):
        old = self.encounters.plan_location("admin",uid(),"cordon",300000,17,1)["contacts"][0]
        original = self.store.event
        def fail(tx,aggregate,event_type,*args,**kwargs):
            if event_type=="OfflineHazardPlanned":
                raise RuntimeError("injected combined plan failure")
            return original(tx,aggregate,event_type,*args,**kwargs)
        self.store.event = fail
        with self.assertRaises(RuntimeError):
            self.plan()
        self.store.event = original
        self.assertEqual(self.state(old["event_id"])["state"],"PENDING")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='ScheduledEventCancelled'").fetchone()[0],0)

    def test_combined_disjoint_admission_overflow_has_no_partial_plans(self):
        with self.store.transaction() as tx:
            for i in range(1,65):
                position = [i*1000,0,0]
                tx.execute("INSERT INTO entity VALUES(?,'NPC','cordon','offline:cordon',?,1,1,?)",
                           (uid(),self.store.epoch,json.dumps({"position":position,"health":.2})))
                tx.execute("INSERT INTO entity VALUES(?,'TRAP','cordon','offline:cordon',?,1,1,?)",
                           (uid(),self.store.epoch,json.dumps({"position":position,"radius":1,"hazard_type":"fire",
                                                             "armed":True,"charges":1,"damage_bp":10000})))
        with self.assertRaises(Unavailable):
            self.plan()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type IN ('OfflineCombat','OfflineHazard')").fetchone()[0],0)

    def test_scale_change_cancels_old_capture_and_selects_rebased_contact(self):
        old = self.plan()["contacts"][0]
        self.world.set_scale("admin",uid(),20)
        result = self.plan()
        self.assertEqual((result["cancelled_plans"],result["contacts"][0]["due_ms"]),(1,80000))
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")

    def test_surface_contact_rounding_does_not_cancel_a_captured_fight(self):
        self.change(self.trap,armed=False)
        contact = self.plan(radius=.1)["contacts"][0]
        self.assertEqual(contact["type"],"offline_combat")
        self.ns = int((contact["due_ms"]+1)/10*1000000)
        self.scheduler.run_due(budget_ms=1000)
        event = self.state(contact["event_id"])
        self.assertEqual(event["state"],"APPLIED")
        self.assertTrue(json.loads(event["result"])["casualties"])


if __name__=="__main__":
    unittest.main()
