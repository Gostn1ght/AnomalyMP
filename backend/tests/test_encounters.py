import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.economy import Catalog
from lostzone.ownership import Ownership
from lostzone.offline import Offline
from lostzone.scheduler import Scheduler
from lostzone.encounters import Encounters


def uid():
    return uuid.uuid4().hex


class EncounterTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/"world.db"
        self.ns = 0
        self.utc = 1_800_000_000_000_000_000
        self.open()
        self.fence = self.world.claim_location("a",uid(),"cordon")["fence"]
        self.world.set_state("admin",uid(),"relations",0,{"hostile":[["duty","bandit"]]})
        self.first,self.second,self.weapon = uid(),uid(),uid()
        self.ownership.create_entity("a",uid(),self.first,"NPC","cordon",self.fence,
                                     {"position":[0,0,0],"health":1,"faction":"duty","experience":5,"task":"patrol"})
        self.ownership.create_entity("a",uid(),self.second,"NPC","cordon",self.fence,
                                     {"position":[1,0,0],"health":.2,"faction":"bandit","melee_power":1})
        self.ownership.create_item("a",uid(),self.weapon,"wpn","cordon",self.fence,"NPC",self.first,
                                   state={"rounds":30,"condition":.8,"attachments":["scope"]})
        self.loot = uid()
        self.ownership.create_item("a",uid(),self.loot,"food","cordon",self.fence,"NPC",self.second,
                                   state={"condition":.6})
        for entity_id in (self.first,self.second):
            row = self.row(entity_id)
            self.offline.dehydrate("a",uid(),entity_id,"cordon",self.fence,1,
                                   {entity_id:{"version":1,"state":json.loads(row["state"])}})
        self.event = uid()

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store,world_id=123,seed=42,monotonic=lambda:self.ns,wall=lambda:self.utc)
        self.ownership = Ownership(self.world)
        self.catalog = Catalog({"wpn":{"category":"WEAPON","price":1000,"weight_g":3000,"combat_power":1000},
                                "food":{"category":"FOOD","price":100,"weight_g":100}})
        self.scheduler = Scheduler(self.world)
        self.offline = Offline(self.world,self.scheduler)
        self.encounters = Encounters(self.world,self.offline,self.catalog)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def row(self,entity_id):
        return self.store.db.execute("SELECT * FROM entity WHERE id=?",(entity_id,)).fetchone()

    def schedule(self,event=None,due=1000):
        return self.encounters.schedule("admin",uid(),event or self.event,self.first,self.second,
                                        self.row(self.first)["version"],self.row(self.second)["version"],due,17)

    def result(self):
        return json.loads(self.store.db.execute("SELECT result FROM scheduled_event WHERE id=?",(self.event,)).fetchone()[0])

    def test_individual_death_preserves_loot_and_consumes_actual_weapon_rounds(self):
        self.schedule();self.ns=100_000_000
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        result = self.result()
        self.assertEqual(result["casualties"],[self.second])
        self.assertEqual((self.row(self.second)["alive"],self.row(self.first)["alive"]),(0,1))
        row = self.store.db.execute("SELECT * FROM item WHERE id=?",(self.loot,)).fetchone()
        self.assertEqual((row["id"],row["kind"],row["holder"]),(self.loot,"CORPSE",self.second))
        weapon = json.loads(self.store.db.execute("SELECT state FROM item WHERE id=?",(self.weapon,)).fetchone()[0])
        self.assertLess(weapon["rounds"],30)
        self.assertEqual(weapon["rounds"],result["ammo"][0]["remaining"])
        self.assertEqual(weapon["attachments"],["scope"])
        self.assertEqual(json.loads(self.row(self.first)["state"])["task"],"patrol")
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        self.store.close();self.open()
        self.assertEqual(self.result(),result)
        self.assertEqual(self.row(self.second)["alive"],0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0],2)

    def test_restart_before_resolution_keeps_frozen_result(self):
        self.schedule()
        self.store.close()
        clone = Path(self.folder.name)/"copy.db"
        clone.write_bytes(self.path.read_bytes())
        self.open();self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        expected = self.result()
        self.store.close();self.path=clone;self.ns=0;self.open();self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result(),expected)

    def test_hydration_cancels_abstract_fight_before_any_damage_or_ammo_spend(self):
        self.schedule()
        self.offline.hydrate("a",uid(),self.first,"cordon",self.fence,2)
        self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE id=?",(self.event,)).fetchone()[0],"CANCELLED")
        self.assertEqual(self.row(self.second)["alive"],1)
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM item WHERE id=?",(self.weapon,)).fetchone()[0])["rounds"],30)

    def test_resolution_failure_rolls_back_ammo_health_death_and_evidence(self):
        self.schedule()
        self.ns=100_000_000
        original = self.store.event
        def fail(tx,aggregate,kind,*args,**kwargs):
            if kind=="OfflineEncounterResolved":
                raise RuntimeError("injected crash before evidence commit")
            return original(tx,aggregate,kind,*args,**kwargs)
        self.store.event=fail
        with self.assertRaises(RuntimeError):
            self.scheduler.run_due(budget_ms=1000)
        self.store.event=original
        self.assertEqual(self.row(self.second)["alive"],1)
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM item WHERE id=?",(self.weapon,)).fetchone()[0])["rounds"],30)
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE id=?",(self.event,)).fetchone()[0],"PENDING")
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        self.assertEqual(self.result()["casualties"],[self.second])

    def test_diplomacy_change_cancels_fight_and_far_routes_do_not_invent_combat(self):
        self.schedule()
        self.world.set_state("admin",uid(),"relations",1,{"hostile":[]})
        self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result()["reason"],"location/diplomacy changed")
        self.world.set_state("admin",uid(),"relations",2,{"hostile":[["duty","bandit"]]})
        with self.store.transaction() as tx:
            state = json.loads(self.row(self.second)["state"])
            state["position"]=[1000,0,0]
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?",(json.dumps(state),self.second))
        self.event=uid();self.schedule(due=2000);self.ns=200_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result()["reason"],"routes do not meet")

    def test_item_capture_change_cancels_fight_instead_of_rerolling_outcome(self):
        self.schedule()
        with self.store.transaction() as tx:
            tx.execute("UPDATE item SET version=version+1 WHERE id=?",(self.weapon,))
        self.ns=100_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result()["reason"],"individual capture/inventory changed")
        self.assertEqual(self.row(self.second)["alive"],1)

    def group(self,member,faction):
        self.offline.hydrate("a",uid(),member,"cordon",self.fence,self.row(member)["version"])
        group = uid()
        self.ownership.create_entity("a",uid(),group,"GROUP","cordon",self.fence,
                                     {"position":json.loads(self.row(member)["state"])["position"],"faction":faction,"member_ids":[member]})
        return group

    def test_lost_group_keeps_casualty_ids_and_does_not_leave_a_moving_empty_patrol(self):
        first,second = self.group(self.first,"duty"),self.group(self.second,"bandit")
        for group,member in ((first,self.first),(second,self.second)):
            captures = {value:{"version":self.row(value)["version"],"state":json.loads(self.row(value)["state"])}
                        for value in (group,member)}
            self.offline.dehydrate("a",uid(),group,"cordon",self.fence,1,captures)
        self.encounters.schedule("admin",uid(),self.event,first,second,2,2,1000,17)
        self.ns=100_000_000;self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.row(second)["alive"],0)
        self.assertEqual(json.loads(self.row(second)["state"])["member_ids"],[self.second])
        self.assertTrue(json.loads(self.row(second)["state"])["corpse_removed"])
        with self.assertRaises(Conflict):
            self.offline.start_route("admin",uid(),second,self.row(second)["version"],[[1,0,0],[100,0,0]],2,42)

    def test_individual_group_member_cannot_leave_roster_via_transfer(self):
        from lostzone.transfers import Transfers
        self.group(self.first,"duty")
        self.world.claim_location("b",uid(),"garbage")
        with self.assertRaises(Conflict):
            Transfers(self.world,b"x"*32).prepare("a",uid(),self.first,"cordon",self.fence,"garbage",self.row(self.first)["version"])

    def contact(self, horizon=100000, command=None):
        return self.encounters.plan_contact("admin", command or uid(), self.event, self.first, self.second,
                                           self.row(self.first)["version"], self.row(self.second)["version"], horizon, 17, 10)

    def place(self, entity_id, position):
        with self.store.transaction() as tx:
            state = json.loads(self.row(entity_id)["state"])
            state["position"] = position
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (json.dumps(state), entity_id))

    def crossing(self):
        self.place(self.first, [-100,0,0]); self.place(self.second, [0,0,-100])
        for entity_id, points in ((self.first,[[-100,0,0],[100,0,0]]), (self.second,[[0,0,-100],[0,0,100]])):
            self.offline.start_route("admin",uid(),entity_id,self.row(entity_id)["version"],points,2,42)

    def test_contact_planner_commits_one_real_crossing_and_retry_does_not_duplicate(self):
        self.crossing()
        command = uid()
        result = self.contact(horizon=1_200_000,command=command)
        self.assertGreater(result["due_ms"],0)
        self.assertEqual(self.contact(horizon=1_200_000,command=command),result)
        self.ns = int((result["due_ms"] / self.world._scale + .01)*1_000_000)
        self.scheduler.run_due(budget_ms=1000)
        combat = self.result()
        self.assertEqual(combat["casualties"],[self.second])
        self.assertLessEqual(sum((a-b)**2 for a,b in zip(*combat["positions"])),100.000001)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineCombat'").fetchone()[0],1)

    def test_contact_planner_miss_does_not_create_fight_or_spend_ammo(self):
        self.place(self.second,[1000,0,0])
        self.assertEqual(self.contact()["reason"],"routes do not meet")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE type='OfflineCombat'").fetchone()[0],0)
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM item WHERE id=?",(self.weapon,)).fetchone()[0])["rounds"],30)

    def test_planned_route_contact_survives_authority_restart(self):
        self.crossing()
        result = self.contact(horizon=1_200_000)
        self.store.close(); self.open()
        self.ns = int((result["due_ms"] / self.world._scale + .01)*1_000_000)
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result()["capture_hash"],result["capture_hash"])
        self.assertEqual(self.result()["casualties"],[self.second])

    def test_scale_rebase_cancels_stale_contact_even_when_still_inside_radius(self):
        self.offline.start_route("admin",uid(),self.first,self.row(self.first)["version"],[[0,0,0],[10,0,0]],1,42)
        self.schedule(due=1000)
        self.world.set_scale("admin",uid(),2)
        self.ns = 600_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.result()["reason"],"route capture changed")
        self.assertEqual(self.row(self.second)["alive"],1)
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM item WHERE id=?",(self.weapon,)).fetchone()[0])["rounds"],30)

    def test_immediate_contact_uses_one_planning_instant(self):
        original = self.world.now
        ticks = iter(range(10000))
        self.world.now = lambda: original() + next(ticks)*.001
        result = self.contact()
        self.assertIsNotNone(result["event_id"])


if __name__=="__main__":
    unittest.main()
