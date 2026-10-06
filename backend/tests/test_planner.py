import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid
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

    def enable_auto(self,**changes):
        policy = {"horizon_ms":300000,"radius":1,"max_locations":25,"budget_ms":1000}
        policy.update(changes)
        self.planner.enable_automatic(policy)

    def pending_contacts(self):
        return self.store.db.execute("SELECT * FROM scheduled_event WHERE type IN ('OfflineCombat','OfflineHazard') AND state='PENDING'").fetchall()

    def reroute(self,key=None,points=None,version=2):
        return self.offline.start_route("admin",key or uid(),self.first,version,points or [[-10,0,0],[10,0,0]],1,42)

    def test_automatic_route_change_plans_actual_trap_without_explicit_plan_command(self):
        self.enable_auto();self.reroute()
        contacts = self.pending_contacts()
        self.assertEqual([(row["type"],row["due_world_ms"]) for row in contacts],[("OfflineHazard",40000)])
        self.assertEqual(json.loads(contacts[0]["payload"])["hazard_id"],self.trap)
        self.ns=4_001_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)
        self.assertEqual(self.state(contacts[0]["id"])["state"],"APPLIED")
        self.assertEqual(self.pending_contacts(),[])

    def test_automatic_scale_rebase_cancels_stale_capture_and_replans_surface_time(self):
        old = self.plan()["contacts"][0]
        self.enable_auto();self.world.set_scale("admin",uid(),20)
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")
        self.assertEqual([row["due_world_ms"] for row in self.pending_contacts()],[80000])

    def test_route_diversion_cancels_old_trap_plan_before_contact(self):
        old = self.plan()["contacts"][0];self.enable_auto()
        self.ns=1_000_000_000
        self.reroute(points=[[-9,0,0],[-9,0,20]])
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")
        self.assertEqual(self.pending_contacts(),[])
        self.ns=5_000_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],1)

    def test_automatic_contact_failure_rolls_back_route_and_existing_reservation(self):
        old = self.plan()["contacts"][0];self.enable_auto()
        before = dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone())
        original=self.store.event
        def fail(tx,aggregate,kind,*args,**kwargs):
            if kind=="OfflineHazardPlanned":
                raise RuntimeError("injected automatic discovery failure")
            return original(tx,aggregate,kind,*args,**kwargs)
        self.store.event=fail
        with self.assertRaises(RuntimeError):
            self.reroute()
        self.store.event=original
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone()),before)
        self.assertEqual(self.state(old["event_id"])["state"],"PENDING")
        self.assertEqual(len(self.pending_contacts()),1)

    def test_automatic_replay_and_restart_preserve_event_id_seed_and_capture(self):
        self.enable_auto();key=uid();result=self.reroute(key)
        contact=dict(self.pending_contacts()[0])
        self.store.close();self.open();self.enable_auto()
        self.assertEqual(self.reroute(key),result)
        self.assertEqual(dict(self.pending_contacts()[0]),contact)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='ContactsReplanned'").fetchone()[0],1)

    def test_automatic_location_budget_refuses_scale_without_partial_rebase(self):
        old = self.plan()["contacts"][0];self.enable_auto(max_locations=1)
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'NPC','garbage','offline:garbage',?,1,1,?)",
                       (uid(),self.store.epoch,json.dumps({"position":[0,0,0],"health":1})))
        before=dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone())
        with self.assertRaises(Unavailable):
            self.world.set_scale("admin",uid(),20)
        self.assertEqual(self.world._scale,10)
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone()),before)
        self.assertEqual(self.state(old["event_id"])["state"],"PENDING")

    def test_invalid_or_duplicate_automatic_policy_cannot_replace_authority(self):
        with self.assertRaises(Invalid):
            self.planner.enable_automatic({"radius":1})
        self.assertEqual(self.world.mutation_observers,{})
        self.enable_auto()
        replacement=Planner(self.world,self.encounters,self.hazards)
        with self.assertRaises(Conflict):
            replacement.enable_automatic(self.planner.policy)
        self.assertEqual(self.world.mutation_observers["offline_contacts"],self.planner.changed_in)
        self.assertEqual(self.scheduler.handlers["OfflineContactsWindow"],self.planner.window_in)

    def windows(self,state="PENDING"):
        return self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineContactsWindow' AND state=? ORDER BY due_world_ms",(state,)).fetchall()

    def test_durable_windows_discover_crossed_trap_when_processing_is_late(self):
        self.enable_auto(horizon_ms=10000);self.reroute()
        self.assertEqual(self.pending_contacts(),[])
        self.assertEqual([row["due_world_ms"] for row in self.windows()],[10000])
        self.ns=5_000_000_000 # now=50000, contact=40000 in a prior window
        self.scheduler.run_due(budget_ms=1000)
        hazards=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineHazard'").fetchall()
        self.assertEqual(len(hazards),1)
        self.assertEqual((hazards[0]["due_world_ms"],hazards[0]["state"]),(40000,"APPLIED"))
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)
        self.assertEqual(self.windows(),[])

    def test_windows_resume_from_captured_due_time_after_restart(self):
        self.enable_auto(horizon_ms=10000);self.reroute()
        original=dict(self.windows()[0])
        self.store.close();self.open();self.enable_auto(horizon_ms=10000)
        self.assertEqual(dict(self.windows()[0]),original)
        self.ns=5_000_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)

    def test_new_route_atomically_replaces_its_location_window(self):
        self.enable_auto(horizon_ms=10000);self.reroute()
        original=self.windows()[0]
        self.reroute(points=[[-10,0,0],[-10,0,20]],version=3)
        self.assertEqual(self.state(original["id"])["state"],"CANCELLED")
        self.assertEqual(len(self.windows()),1)
        self.assertNotEqual(self.windows()[0]["id"],original["id"])

    def test_missing_captured_policy_holds_window_without_skipping_history(self):
        self.enable_auto(horizon_ms=10000);self.reroute()
        original=self.windows()[0]
        self.store.close();self.open();self.ns=5_000_000_000
        with self.assertRaises(Unavailable):
            self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.state(original["id"])["state"],"PENDING")
        self.assertEqual(self.pending_contacts(),[])
        self.enable_auto(horizon_ms=10000);self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)

    def test_window_never_repeats_stationary_fights_after_route_resolution(self):
        self.change(self.trap,armed=False)
        self.enable_auto(horizon_ms=10000);self.reroute()
        self.ns=30_000_000_000;self.scheduler.run_due(budget_ms=1000)
        fights=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineCombat'").fetchall()
        self.assertEqual(len(fights),1)
        self.assertEqual(fights[0]["state"],"APPLIED")
        self.assertEqual(self.windows(),[])

    def test_final_arrival_stops_windows_without_an_actor_tick_loop(self):
        self.change(self.trap,armed=False)
        self.world.set_state("admin",uid(),"relations",1,{"hostile":[]})
        self.enable_auto(horizon_ms=10000);self.reroute()
        self.ns=30_000_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.windows(),[])
        self.assertEqual(self.store.db.execute("SELECT active FROM route WHERE entity_id=?",(self.first,)).fetchone()[0],0)
        self.assertEqual(len(self.windows("APPLIED")),19)

    def test_late_route_replacement_cannot_skip_previously_undiscovered_hazard(self):
        self.enable_auto(horizon_ms=10000);self.reroute()
        original=dict(self.windows()[0]);self.ns=5_000_000_000
        with patch("lostzone.scheduler.time.monotonic",return_value=0):
            with self.assertRaises(Conflict):
                self.reroute(points=[[-5,0,0],[-5,0,20]],version=3)
        self.assertEqual(dict(self.windows()[0]),original)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],1)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)
        self.assertEqual(self.pending_contacts(),[])

    def test_continuation_capture_failure_keeps_pending_job_and_retries_once(self):
        self.enable_auto(horizon_ms=10000);self.reroute();self.ns=5_000_000_000
        original=self.store.event
        def fail(tx,aggregate,kind,*args,**kwargs):
            if kind=="OfflineHazardPlanned":
                raise RuntimeError("injected continuation capture failure")
            return original(tx,aggregate,kind,*args,**kwargs)
        self.store.event=fail
        with self.assertRaises(RuntimeError):
            self.scheduler.run_due(budget_ms=1000)
        self.store.event=original
        self.assertEqual([row["due_world_ms"] for row in self.windows()],[30000])
        self.assertEqual(self.pending_contacts(),[])
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],1)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],1)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.first,)).fetchone()[0],0)

    def test_automatic_hydration_cancels_future_abstract_capture(self):
        old=self.plan()["contacts"][0];self.enable_auto()
        fence=self.world.claim_location("a",uid(),"cordon")["fence"]
        self.offline.hydrate("a",uid(),self.first,"cordon",fence,2)
        self.assertEqual(self.state(old["event_id"])["state"],"CANCELLED")
        self.assertEqual(self.pending_contacts(),[])
        self.assertEqual(self.store.db.execute("SELECT writer FROM entity WHERE id=?",(self.first,)).fetchone()[0],"a")

    def test_dehydration_discovers_stationary_actual_hazard_contact(self):
        fence=self.world.claim_location("a",uid(),"cordon")["fence"]
        npc=uid();state={"position":[-5,0,0],"health":.2,"faction":"duty"}
        Ownership(self.world).create_entity("a",uid(),npc,"NPC","cordon",fence,state)
        self.enable_auto()
        self.offline.dehydrate("a",uid(),npc,"cordon",fence,1,{npc:{"version":1,"state":state}})
        contact=self.pending_contacts()[0]
        self.assertEqual((json.loads(contact["payload"])["entity_id"],contact["due_world_ms"]),(npc,0))
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(npc,)).fetchone()[0],0)
        # The independent moving first/second pair can keep its future fight;
        # no stationary hazard loop is created for the just-killed NPC.
        self.assertEqual([row["type"] for row in self.pending_contacts()],["OfflineCombat"])

    def test_diplomacy_subscriber_replans_without_timer_or_explicit_command(self):
        self.change(self.trap,armed=False);self.enable_auto()
        self.world.set_state("admin",uid(),"relations",1,{"hostile":[["duty","bandit"]]})
        contact=self.pending_contacts()[0]
        self.assertEqual((contact["type"],contact["due_world_ms"]),("OfflineCombat",190000))
        self.world.set_state("admin",uid(),"relations",2,{"hostile":[]})
        self.assertEqual(self.state(contact["id"])["state"],"CANCELLED")
        self.assertEqual(self.pending_contacts(),[])

    def test_automatic_time_budget_refusal_rolls_back_route_and_new_plans(self):
        self.enable_auto(budget_ms=1)
        before=dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone())
        with patch("lostzone.planner.time.monotonic",side_effect=[0,0,.002]):
            with self.assertRaises(Unavailable):
                self.reroute()
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(self.first,)).fetchone()),before)
        self.assertEqual(self.pending_contacts(),[])
        self.assertIsNone(self.world._mutation_cut)

    def arrival_then_contact(self):
        self.change(self.trap,armed=False)
        self.offline.start_route("admin",uid(),self.first,2,[[-10,0,0],[0,0,0]],10,42)
        self.offline.start_route("admin",uid(),self.second,1,[[10,0,0],[0,0,0]],1,42)
        self.enable_auto()
        self.world.set_state("admin",uid(),"relations",1,{"hostile":[["duty","bandit"]]})
        contact=self.pending_contacts()[0]
        self.assertEqual(contact["due_world_ms"],90000)
        arrival=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='RouteArrived' AND state='PENDING' ORDER BY due_world_ms LIMIT 1").fetchone()
        self.assertEqual(arrival["due_world_ms"],10000)
        return contact,arrival

    def test_arrival_replans_later_physical_fight_without_cancelling_its_source(self):
        old,arrival=self.arrival_then_contact();self.ns=20_000_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.state(arrival["id"])["state"],"APPLIED")
        self.assertEqual(self.state(old["id"])["state"],"CANCELLED")
        fights=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineCombat' AND state='APPLIED'").fetchall()
        self.assertEqual(len(fights),1)
        self.assertEqual(fights[0]["due_world_ms"],90000)
        self.assertEqual(self.pending_contacts(),[])
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)

    def test_outcome_continuation_failure_rolls_back_source_arrival(self):
        old,arrival=self.arrival_then_contact();self.ns=20_000_000_000
        original=self.scheduler.schedule_in
        def fail(tx,event_id,due,aggregate,version,kind,*args,**kwargs):
            if kind=="OfflineContactsRefresh":
                raise RuntimeError("injected causal continuation failure")
            return original(tx,event_id,due,aggregate,version,kind,*args,**kwargs)
        self.scheduler.schedule_in=fail
        with self.assertRaises(RuntimeError):
            self.scheduler.run_due(budget_ms=1000)
        self.scheduler.schedule_in=original
        self.assertEqual(self.state(arrival["id"])["state"],"PENDING")
        self.assertEqual(self.state(old["id"])["state"],"PENDING")
        self.assertEqual(self.store.db.execute("SELECT active FROM route WHERE entity_id=?",(self.first,)).fetchone()[0],1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineContactsRefresh'").fetchone()[0],0)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.state(arrival["id"])["state"],"APPLIED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineCombat' AND state='APPLIED'").fetchone()[0],1)

    def test_outcome_refresh_keeps_physical_time_across_delayed_restart(self):
        old,arrival=self.arrival_then_contact();self.ns=20_000_000_000
        self.assertEqual(self.scheduler.run_due(limit=1,budget_ms=1000),1)
        self.assertEqual(self.state(arrival["id"])["state"],"APPLIED")
        refresh=dict(self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineContactsRefresh'").fetchone())
        self.assertEqual(refresh["due_world_ms"],10000)
        self.store.close();self.open();self.enable_auto()
        self.assertEqual(dict(self.state(refresh["id"])),refresh)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.state(old["id"])["state"],"CANCELLED")
        fights=self.store.db.execute("SELECT due_world_ms FROM scheduled_event WHERE type='OfflineCombat' AND state='APPLIED'").fetchall()
        self.assertEqual([row[0] for row in fights],[90000])

    def test_outcome_refresh_stops_without_scanning_large_stationary_population(self):
        self.arrival_then_contact();self.ns=20_000_000_000
        self.assertEqual(self.scheduler.run_due(limit=3,budget_ms=1000),3)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM route WHERE active=1").fetchone()[0],0)
        with self.store.transaction() as tx:
            for index in range(300):
                tx.execute("INSERT INTO entity VALUES(?,'NPC','cordon','offline:cordon',?,1,1,?)",
                           (uid(),self.store.epoch,json.dumps({"health":1,"position":[10000+index,0,0]})))
        # A full discovery pass would refuse its 256-root budget. No motion
        # remains, so completing the causal job must not scan that population.
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        self.assertEqual(self.windows(),[])

    def simultaneous_arrivals(self,legacy_priority=False):
        self.change(self.trap,armed=False)
        self.world.set_state("admin",uid(),"relations",1,{"hostile":[]})
        self.offline.start_route("admin",uid(),self.first,2,[[-10,0,0],[0,0,0]],1,42)
        self.offline.start_route("admin",uid(),self.second,1,[[10,0,0],[20,0,0]],1,42)
        third=uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'NPC','cordon','offline:cordon',?,1,1,?)",
                       (third,self.store.epoch,json.dumps({"health":1,"position":[-20,0,0]})))
        self.offline.start_route("admin",uid(),third,1,[[-20,0,0],[20,0,0]],1,42)
        self.enable_auto(horizon_ms=1000000)
        self.world.set_state("admin",uid(),"relations",2,{"hostile":[]})
        if legacy_priority:
            with self.store.transaction() as tx:
                tx.execute("UPDATE scheduled_event SET priority=0 WHERE type='RouteArrived' AND due_world_ms=100000")
        self.ns=15_000_000_000

    def test_simultaneous_source_outcomes_coalesce_pending_location_refresh(self):
        self.simultaneous_arrivals(legacy_priority=True)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),3)
        refreshes=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineContactsRefresh'").fetchall()
        self.assertEqual(len(refreshes),1)
        self.assertEqual(refreshes[0]["state"],"APPLIED")
        links=[json.loads(row[0]) for row in self.store.db.execute("SELECT payload FROM world_event WHERE type='ContactsRefreshQueued' ORDER BY sequence")]
        self.assertEqual([link["coalesced"] for link in links],[False,True])
        self.assertEqual({link["refresh_event"] for link in links},{refreshes[0]["id"]})
        self.assertEqual(len({link["source_event"] for link in links}),2)

    def test_later_same_time_outcome_creates_new_refresh_after_previous_applied(self):
        self.simultaneous_arrivals()
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),4)
        refreshes=self.store.db.execute("SELECT * FROM scheduled_event WHERE type='OfflineContactsRefresh'").fetchall()
        self.assertEqual(len(refreshes),2)
        self.assertTrue(all(row["state"]=="APPLIED" for row in refreshes))
        self.assertEqual(len({row["id"] for row in refreshes}),2)


if __name__=="__main__":
    unittest.main()
