import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid
from lostzone.contacts import trajectory, earliest_contact
from lostzone.economy import Catalog
from lostzone.hazards import Hazards
from lostzone.offline import Offline
from lostzone.ownership import Ownership
from lostzone.scheduler import Scheduler
from lostzone.encounters import Encounters
from lostzone.store import Unavailable


def uid():
    return uuid.uuid4().hex


class HazardTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/"world.db"
        self.ns = 0
        self.open()
        self.fence = self.world.claim_location("a",uid(),"cordon")["fence"]
        self.npc,self.hazard,self.item,self.event = (uid() for _ in range(4))
        self.ownership.create_entity("a",uid(),self.npc,"NPC","cordon",self.fence,
                                     {"position":[-10,0,0],"health":.2,"faction":"duty","task":"patrol","known_hazards":[]})
        self.ownership.create_entity("a",uid(),self.hazard,"TRAP","cordon",self.fence,
                                     {"position":[0,0,0],"hazard_type":"fire","armed":True,"charges":1,
                                      "radius":1,"damage_bp":10000,"owner_id":uid(),"cooldown_ms":60000})
        self.ownership.create_item("a",uid(),self.item,"food","cordon",self.fence,"NPC",self.npc,
                                   quantity=2,state={"condition":.7,"attachments":["tag"]})
        for value in (self.npc,self.hazard):
            row = self.row(value)
            self.offline.dehydrate("a",uid(),value,"cordon",self.fence,1,{value:{"version":1,"state":json.loads(row["state"])}})
        self.offline.start_route("admin",uid(),self.npc,2,[[-10,0,0],[10,0,0]],1,42)

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store,world_id=123,seed=42,monotonic=lambda:self.ns,wall=lambda:1_800_000_000_000_000_000)
        self.ownership = Ownership(self.world)
        self.scheduler = Scheduler(self.world)
        self.offline = Offline(self.world,self.scheduler)
        self.catalog = Catalog({"armor":{"category":"ARMOR","price":1000,"weight_g":1000,
                                         "hazard_protection_bp":{"fire":10000}}})
        self.hazards = Hazards(self.world,self.offline,self.catalog)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def row(self,value):
        return self.store.db.execute("SELECT * FROM entity WHERE id=?",(value,)).fetchone()

    def change(self,value,**changes):
        with self.store.transaction() as tx:
            state = dict(json.loads(self.row(value)["state"]),**changes)
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(json.dumps(state),value))

    def plan(self,root=None,command=None):
        root = root or self.npc
        return self.hazards.plan_contact("admin",command or uid(),self.event,root,self.hazard,
                                         self.row(root)["version"],self.row(self.hazard)["version"],300000,17)

    def resolve_plan(self,result):
        self.ns = int((result["due_ms"]/self.world._scale+.01)*1_000_000)
        self.scheduler.run_due(budget_ms=1000)
        return json.loads(self.store.db.execute("SELECT result FROM scheduled_event WHERE id=?",(self.event,)).fetchone()[0])

    def test_trap_death_preserves_inventory_id_state_and_consumes_charge_once_after_restart(self):
        command = uid()
        plan = self.plan(command=command)
        self.assertAlmostEqual(plan["due_ms"],90000)
        self.store.close();self.open()
        self.assertEqual(self.plan(command=command),plan)
        result = self.resolve_plan(plan)
        self.assertTrue(result["outcomes"][0]["died"])
        self.assertEqual(self.row(self.npc)["alive"],0)
        state = json.loads(self.row(self.npc)["state"])
        self.assertEqual((state["task"],state["position"],state["death_time"]),("patrol",[-1,0,0],90000))
        item = self.store.db.execute("SELECT * FROM item WHERE id=?",(self.item,)).fetchone()
        self.assertEqual((item["id"],item["kind"],item["holder"],item["quantity"]),(self.item,"CORPSE",self.npc,2))
        self.assertEqual(json.loads(item["state"]),{"condition":.7,"attachments":["tag"]})
        trap = json.loads(self.row(self.hazard)["state"])
        self.assertEqual((trap["charges"],trap["armed"]),(0,False))
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        self.store.close();self.open()
        self.assertEqual(self.row(self.npc)["alive"],0)
        with self.assertRaises(Conflict):
            self.offline.start_route("admin",uid(),self.npc,self.row(self.npc)["version"],[[-1,0,0],[1,0,0]],1,42)

    def test_equipped_catalog_protection_uses_condition_not_inventory_presence(self):
        armor = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,'armor','NPC',?,1,1,?)",(armor,self.npc,json.dumps({"equipped":True,"condition":1})))
        result = self.resolve_plan(self.plan())
        self.assertEqual((result["outcomes"][0]["damage_bp"],self.row(self.npc)["alive"]),(0,1))
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],0)

    def test_unequipped_armor_does_not_grant_remote_protection(self):
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,'armor','NPC',?,1,1,?)",(uid(),self.npc,json.dumps({"equipped":False,"condition":1})))
        self.assertTrue(self.resolve_plan(self.plan())["outcomes"][0]["died"])

    def test_damaged_equipped_armor_reduces_protection(self):
        self.change(self.npc,health=1)
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,'armor','NPC',?,1,1,?)",(uid(),self.npc,json.dumps({"equipped":True,"condition":.5})))
        result = self.resolve_plan(self.plan())
        self.assertEqual((result["outcomes"][0]["damage_bp"],result["outcomes"][0]["health"]),(5000,.5))

    def test_item_capture_change_cancels_without_spending_trap_charge(self):
        plan = self.plan()
        with self.store.transaction() as tx:
            tx.execute("UPDATE item SET version=version+1 WHERE id=?",(self.item,))
        result = self.resolve_plan(plan)
        self.assertIn("changed",result["reason"])
        self.assertEqual((self.row(self.npc)["alive"],json.loads(self.row(self.hazard)["state"])["charges"]),(1,1))

    def test_hydration_cancels_before_damage_inventory_or_charge_changes(self):
        plan = self.plan()
        self.offline.hydrate("a",uid(),self.npc,"cordon",self.fence,3)
        result = self.resolve_plan(plan)
        self.assertIn("changed",result["reason"])
        self.assertEqual(self.row(self.npc)["alive"],1)
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],1)
        self.assertEqual(self.store.db.execute("SELECT kind FROM item WHERE id=?",(self.item,)).fetchone()[0],"NPC")

    def test_scale_change_cancels_even_if_new_route_still_reaches_hazard(self):
        plan = self.plan()
        self.world.set_scale("admin",uid(),20)
        self.resolve_plan(plan)
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE id=?",(self.event,)).fetchone()[0],"CANCELLED")
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],1)

    def test_owner_faction_height_and_cooldown_misses_do_not_create_event(self):
        for changes in ({"owner_id":self.npc},{"safe_factions":["duty"]},
                        {"position":[0,10,0]},{"cooldown_until_ms":400000}):
            self.change(self.hazard,owner_id=uid(),safe_factions=[],position=[0,0,0],cooldown_until_ms=0)
            self.change(self.hazard,**changes)
            self.assertIsNone(self.plan()["event_id"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],0)

    def test_journal_failure_rolls_back_death_loot_charge_and_position(self):
        plan = self.plan()
        original = self.store.event
        def fail(tx,aggregate,event_type,*args,**kwargs):
            if event_type=="OfflineHazardResolved":
                raise RuntimeError("injected hazard evidence failure")
            return original(tx,aggregate,event_type,*args,**kwargs)
        self.store.event = fail
        with self.assertRaises(RuntimeError):
            self.resolve_plan(plan)
        self.store.event = original
        self.assertEqual((self.row(self.npc)["alive"],json.loads(self.row(self.npc)["state"])["position"]),(1,[-10,0,0]))
        self.assertEqual(self.store.db.execute("SELECT kind FROM item WHERE id=?",(self.item,)).fetchone()[0],"NPC")
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],1)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.row(self.npc)["alive"],0)

    def test_anomaly_outcome_capture_is_identical_across_restart(self):
        with self.store.transaction() as tx:
            tx.execute("UPDATE entity SET kind='ANOMALY' WHERE id=?",(self.hazard,))
        self.change(self.hazard,active=True)
        self.change(self.npc,experience=10,known_hazards=["fire"])
        plan = self.plan()
        self.store.close()
        clone = Path(self.folder.name)/"clone.db"
        clone.write_bytes(self.path.read_bytes())
        self.open()
        expected = self.resolve_plan(plan)
        self.store.close();self.path=clone;self.ns=0;self.open()
        self.assertEqual(self.resolve_plan(plan),expected)

    def test_member_trajectory_keeps_group_turns_and_hazard_hits_offset_member(self):
        with self.store.transaction() as tx:
            tx.execute("UPDATE route SET active=0 WHERE entity_id=?",(self.npc,))
            group = uid()
            tx.execute("INSERT INTO entity VALUES(?,'GROUP','cordon','offline:cordon',?,1,1,?)",
                       (group,self.store.epoch,json.dumps({"position":[-10,0,-2],"member_ids":[self.npc]})))
            tx.execute("INSERT INTO group_member VALUES(?,?)",(group,self.npc))
        self.offline.start_route("admin",uid(),group,1,[[-10,0,-2],[-10,0,8],[10,0,8]],1,42)
        self.change(self.hazard,position=[-10,0,10])
        npc = self.row(self.npc)
        path = trajectory(self.offline,self.store.db,npc,0,300000)
        self.assertIn((100000,[-10,0,10]),path)
        self.assertAlmostEqual(earliest_contact(path,[(0,[-10,0,10]),(300000,[-10,0,10])],1),90000)
        result = self.resolve_plan(self.plan(root=group))
        self.assertEqual(result["outcomes"][0]["id"],self.npc)
        self.assertEqual((self.row(self.npc)["alive"],self.row(group)["alive"]),(0,0))
        self.assertEqual(json.loads(self.row(group)["state"])["member_ids"],[self.npc])

    def test_invalid_trap_and_equipment_policy_fail_before_scheduling(self):
        self.change(self.hazard,charges=0)
        with self.assertRaises(Conflict):
            self.plan()
        with self.assertRaises(Invalid):
            Catalog({"x":{"category":"FOOD","price":1,"weight_g":1,"hazard_protection_bp":{"fire":5000}}})

    def test_contact_at_arrival_endpoint_is_resolved_before_arrival_changes_capture(self):
        self.event = "f"*32 # Would sort after any RouteArrived ID at equal priority.
        self.change(self.hazard,position=[10,0,1])
        plan = self.plan()
        self.assertEqual(plan["due_ms"],200000)
        self.assertTrue(self.resolve_plan(plan)["outcomes"][0]["died"])
        self.assertEqual(json.loads(self.row(self.npc)["state"])["position"],[10,0,0])

    def test_two_contacts_cannot_consume_the_same_trap_charge(self):
        plan = self.plan()
        other = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'MUTANT','cordon','offline:cordon',?,1,1,?)",
                       (other,self.store.epoch,json.dumps({"position":[0,0,0],"health":.2})))
        self.hazards.plan_contact("admin",uid(),uid(),other,self.hazard,1,2,300000,17)
        result = self.resolve_plan(plan)
        self.assertIn("changed",result["reason"])
        self.assertEqual((self.row(other)["alive"],self.row(self.npc)["alive"]),(0,1))
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],0)
        self.assertEqual(self.store.db.execute("SELECT kind FROM item WHERE id=?",(self.item,)).fetchone()[0],"NPC")

    def test_large_individual_states_cannot_overflow_aggregate_capture_admission(self):
        state = json.dumps({"payload":"x"*550000})
        with self.store.transaction() as tx:
            for _ in range(2):
                tx.execute("INSERT INTO item VALUES(?,'food','NPC',?,1,1,?)",(uid(),self.npc,state))
        with self.assertRaises(Conflict):
            self.plan()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],0)
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],1)

    def discovery(self, command=None):
        return self.hazards.plan_location("admin",command or uid(),"cordon",300000,17)

    def test_location_discovery_preserves_one_captured_contact_across_retry_restart(self):
        key = uid()
        result = self.discovery(key)
        self.assertEqual((result["actors"],result["hazards"],result["members"],len(result["contacts"])),(1,1,1,1))
        plan = result["contacts"][0]
        self.assertAlmostEqual(plan["due_ms"],90000)
        self.event = plan["event_id"]
        self.store.close();self.open()
        self.assertEqual(self.discovery(key),result)
        self.assertEqual(self.discovery()["contacts"],[])
        self.assertTrue(self.resolve_plan(plan)["outcomes"][0]["died"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],1)

    def test_discovery_cancels_stale_motion_and_replans_before_old_due_time(self):
        old = self.plan()
        self.world.set_scale("admin",uid(),20)
        result = self.discovery()
        self.assertEqual((result["cancelled_plans"],len(result["contacts"])),(1,1))
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE id=?",(old["event_id"],)).fetchone()[0],"CANCELLED")
        plan = result["contacts"][0]
        self.assertAlmostEqual(plan["due_ms"],180000)
        self.assertEqual(json.loads(self.row(self.hazard)["state"])["charges"],1)
        self.event = plan["event_id"]
        self.assertTrue(self.resolve_plan(plan)["outcomes"][0]["died"])

    def test_discovery_journal_failure_rolls_back_cancellation_and_replacement_together(self):
        old = self.plan()
        self.world.set_scale("admin",uid(),20)
        original = self.store.event
        def fail(tx,aggregate,event_type,*args,**kwargs):
            if event_type=="OfflineHazardPlanned":
                raise RuntimeError("injected replacement plan journal failure")
            return original(tx,aggregate,event_type,*args,**kwargs)
        self.store.event = fail
        with self.assertRaises(RuntimeError):
            self.discovery()
        self.store.event = original
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE id=?",(old["event_id"],)).fetchone()[0],"PENDING")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='ScheduledEventCancelled'").fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],1)

    def test_discovery_filters_inactive_immunity_height_and_cooldown(self):
        for changes in ({"armed":False},{"owner_id":self.npc},{"safe_factions":["duty"]},
                        {"position":[0,20,0]},{"cooldown_until_ms":300001}):
            self.change(self.hazard,armed=True,owner_id=uid(),safe_factions=[],position=[0,0,0],cooldown_until_ms=0)
            self.change(self.hazard,**changes)
            self.assertEqual(self.discovery()["contacts"],[])
        self.change(self.hazard,owner_id=uid(),safe_factions=[],position=[0,0,0],cooldown_until_ms=100000)
        self.assertAlmostEqual(self.discovery()["contacts"][0]["due_ms"],100000)

    def test_discovery_uses_offset_member_path_and_reserves_group_once(self):
        group = uid()
        with self.store.transaction() as tx:
            tx.execute("UPDATE route SET active=0 WHERE entity_id=?",(self.npc,))
            tx.execute("INSERT INTO entity VALUES(?,'GROUP','cordon','offline:cordon',?,1,1,?)",
                       (group,self.store.epoch,json.dumps({"position":[-10,0,-2],"member_ids":[self.npc]})))
            tx.execute("INSERT INTO group_member VALUES(?,?)",(group,self.npc))
        self.offline.start_route("admin",uid(),group,1,[[-10,0,-2],[-10,0,8],[10,0,8]],1,42)
        self.change(self.hazard,position=[-10,0,10])
        result = self.discovery()
        self.assertEqual((result["actors"],result["members"],len(result["contacts"])),(1,1,1))
        plan = result["contacts"][0]
        self.assertEqual(plan["entity_id"],group)
        self.assertAlmostEqual(plan["due_ms"],90000)
        self.event = plan["event_id"]
        self.assertEqual(self.resolve_plan(plan)["outcomes"][0]["id"],self.npc)

    def test_hazard_and_combat_planners_share_actor_reservations(self):
        other = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'MUTANT','cordon','offline:cordon',?,1,1,?)",
                       (other,self.store.epoch,json.dumps({"position":[10,0,0],"health":1,"faction":"bandit"})))
        self.world.set_state("admin",uid(),"relations",0,{"hostile":[["duty","bandit"]]})
        encounters = Encounters(self.world,self.offline,Catalog({"food":{"category":"FOOD","price":1,"weight_g":1}}))
        self.plan()
        self.assertEqual(encounters.plan_location("admin",uid(),"cordon",300000,17,1)["contacts"],[])
        self.change(self.hazard,armed=False)
        combat = encounters.plan_location("admin",uid(),"cordon",300000,17,1)
        self.assertEqual((combat["cancelled_plans"],len(combat["contacts"])),(1,1))
        self.change(self.hazard,armed=True)
        self.assertEqual(self.discovery()["contacts"],[])

    def test_discovery_admission_overflow_rolls_back_all_early_plans(self):
        with self.store.transaction() as tx:
            for i in range(1,65):
                position = [i*1000,0,0]
                tx.execute("INSERT INTO entity VALUES(?,'NPC','cordon','offline:cordon',?,1,1,?)",
                           (uid(),self.store.epoch,json.dumps({"position":position,"health":.2})))
                tx.execute("INSERT INTO entity VALUES(?,'TRAP','cordon','offline:cordon',?,1,1,?)",
                           (uid(),self.store.epoch,json.dumps({"position":position,"hazard_type":"fire","armed":True,
                                                             "charges":1,"radius":1,"damage_bp":10000})))
        with self.assertRaises(Unavailable):
            self.discovery()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineHazard'").fetchone()[0],0)
        self.assertEqual(self.row(self.npc)["alive"],1)


if __name__=="__main__":
    unittest.main()
