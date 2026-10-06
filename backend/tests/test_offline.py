import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid
from lostzone.store import canonical
from lostzone.offline import Offline
from lostzone.ownership import Ownership
from lostzone.scheduler import Scheduler


def uid():
    return uuid.uuid4().hex


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "world.db"
        self.ns = 0
        self.utc = 1_800_000_000_000_000_000
        self.open()
        self.fence = self.world.claim_location("a", uid(), "cordon")["fence"]
        self.npc = uid()
        self.ownership.create_entity("a", uid(), self.npc, "NPC", "cordon", self.fence,
                                     {"position": [0, 0, 0], "health": .4, "ammo": 17, "task": "patrol"})

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store, scale=10, monotonic=lambda: self.ns, wall=lambda: self.utc)
        self.ownership = Ownership(self.world)
        self.scheduler = Scheduler(self.world)
        self.offline = Offline(self.world, self.scheduler)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def row(self, entity_id=None):
        return self.store.db.execute("SELECT * FROM entity WHERE id=?", (entity_id or self.npc,)).fetchone()

    def dehydrate(self):
        row = self.row()
        return self.offline.dehydrate("a", uid(), self.npc, "cordon", self.fence, row["version"],
                                      {self.npc: {"version": row["version"], "state": json.loads(row["state"])}})

    def captured_group(self,payload="",dead_member=False):
        second,group=uid(),uid()
        self.ownership.create_entity("a",uid(),second,"NPC","cordon",self.fence,
                                     {"position":[2,0,0],"health":.8,"payload":payload,"task":"guard"})
        self.ownership.create_entity("a",uid(),group,"GROUP","cordon",self.fence,
                                     {"position":[0,0,0],"member_ids":[self.npc,second]})
        if dead_member:
            self.ownership.kill("a",uid(),second,self.fence,1,"combat")
        captures={value:{"version":self.row(value)["version"],"state":json.loads(self.row(value)["state"])}
                  for value in (group,self.npc,second) if self.row(value)["alive"]}
        self.offline.dehydrate("a",uid(),group,"cordon",self.fence,1,captures)
        return group,second

    def test_hydration_admission_refuses_large_member_without_partial_position_or_ownership(self):
        group,second=self.captured_group("я"*2000)
        self.offline.start_route("admin",uid(),group,2,[[0,0,0],[100,0,0]],1,42)
        self.ns=2_000_000_000
        before=[dict(self.row(value)) for value in (group,self.npc,second)]
        route=dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(group,)).fetchone())
        events=self.store.events();self.offline.hydration_limit=1024
        with self.assertRaises(Invalid):
            self.offline.hydrate("a",uid(),group,"cordon",self.fence,3)
        self.assertEqual([dict(self.row(value)) for value in (group,self.npc,second)],before)
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM route WHERE entity_id=?",(group,)).fetchone()),route)
        self.assertEqual(self.store.events(),events)
        self.offline.hydration_limit=1024*1024
        result=self.offline.hydrate("a",uid(),group,"cordon",self.fence,3)
        positions={row["id"]:json.loads(row["state"])["position"] for row in result["entities"]}
        self.assertEqual(positions,{group:[2,0,0],self.npc:[2,0,0],second:[4,0,0]})
        self.assertEqual(json.loads(self.row(second)["state"])["payload"],"я"*2000)

    def test_hydration_stops_before_loading_later_members_after_oversized_first_record(self):
        group,second=self.captured_group()
        with self.store.transaction() as tx:
            state=json.loads(self.row()["state"]);state["payload"]="x"*3000
            tx.execute("UPDATE entity SET state=? WHERE id=?",(json.dumps(state),self.npc))
        self.offline.hydration_limit=1024
        from contextlib import contextmanager
        original=self.store.transaction
        class Guarded:
            def __init__(self,tx):
                self.tx=tx
            def execute(self,sql,*args):
                if sql.startswith("SELECT id,kind,location,writer,fence,version,alive,") and args[0][0]==second:
                    raise AssertionError("hydration read later member after admission overflow")
                return self.tx.execute(sql,*args)
        @contextmanager
        def transaction():
            with original() as tx:
                yield Guarded(tx)
        self.store.transaction=transaction
        try:
            with self.assertRaises(Invalid):
                self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)
        finally:
            self.store.transaction=original
        self.assertEqual(self.row()["writer"],"offline:cordon")
        self.assertEqual(self.row(second)["writer"],"offline:cordon")

    def test_hydration_projects_only_living_members_and_keeps_permanent_casualty_roster(self):
        group,dead=self.captured_group(dead_member=True)
        before=dict(self.row(dead))
        result=self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)
        self.assertEqual([row["id"] for row in result["entities"]],[group,self.npc])
        self.assertEqual(dict(self.row(dead)),before)
        self.assertEqual(json.loads(self.row(group)["state"])["member_ids"],[self.npc,dead])

    def test_hydration_utf8_escaped_projection_boundary_and_one_byte_refusal(self):
        group,_=self.captured_group('я"\\'*1000)
        self.store.close();frozen=self.path.read_bytes();self.open()
        result=self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)
        budget=len(canonical({"entities":result["entities"],"event":2**63-1}).encode("utf-8"))
        self.assertGreater(budget,1024)
        for delta in (0,-1):
            self.store.close();self.path=Path(self.folder.name)/f"boundary-{delta}.db"
            self.path.write_bytes(frozen);self.open();self.offline.hydration_limit=budget+delta
            if delta==0:
                self.assertEqual(self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)["entities"],result["entities"])
            else:
                before=self.store.events()
                with self.assertRaises(Invalid):
                    self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)
                self.assertEqual(self.row(group)["writer"],"offline:cordon")
                self.assertEqual(self.store.events(),before)

    def test_hydration_journal_failure_rolls_back_projection_route_and_inventory(self):
        group,second=self.captured_group()
        item=uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,'wpn','NPC',?,2,1,?)",
                       (item,self.npc,json.dumps({"condition":.75,"ammo":15,"attachments":["scope"]})))
        inventory=dict(self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone())
        self.offline.start_route("admin",uid(),group,2,[[0,0,0],[100,0,0]],1,42)
        self.ns=2_000_000_000
        before=[dict(self.row(value)) for value in (group,self.npc,second)]
        events=self.store.events();original=self.store.event
        def fail(tx,aggregate,kind,*args,**kwargs):
            if kind=="HydrationClaimed":
                raise RuntimeError("injected hydration journal failure")
            return original(tx,aggregate,kind,*args,**kwargs)
        self.store.event=fail
        try:
            with self.assertRaises(RuntimeError):
                self.offline.hydrate("a",uid(),group,"cordon",self.fence,3)
        finally:
            self.store.event=original
        self.assertEqual([dict(self.row(value)) for value in (group,self.npc,second)],before)
        self.assertEqual(self.store.db.execute("SELECT active FROM route WHERE entity_id=?",(group,)).fetchone()[0],1)
        self.assertEqual(self.store.events(),events)
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()),inventory)
        self.assertIsNone(self.world._mutation_cut)
        self.offline.hydrate("a",uid(),group,"cordon",self.fence,3)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],3)
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()),inventory)

    def test_foreign_member_refuses_hydration_before_parsing_its_invalid_state(self):
        group,second=self.captured_group()
        with self.store.transaction() as tx:
            tx.execute("UPDATE entity SET writer='foreign',state='invalid-json' WHERE id=?",(second,))
        before=[dict(self.row(value)) for value in (group,self.npc,second)]
        with self.assertRaises(Conflict):
            self.offline.hydrate("a",uid(),group,"cordon",self.fence,2)
        self.assertEqual([dict(self.row(value)) for value in (group,self.npc,second)],before)

    def test_shared_members_capture_stops_before_loading_later_oversized_members(self):
        group,second=self.captured_group()
        third=uid()
        with self.store.transaction() as tx:
            state=json.loads(self.row(group)["state"]);state["member_ids"].append(third)
            tx.execute("UPDATE entity SET state=? WHERE id=?",(json.dumps(state),group))
            tx.execute("INSERT INTO entity VALUES(?,'NPC','cordon','offline:cordon',?,1,1,?)",
                       (third,self.store.epoch,json.dumps({"position":[3,0,0]})))
            tx.execute("INSERT INTO group_member VALUES(?,?)",(group,third))
            for member in (self.npc,second):
                state=json.loads(self.row(member)["state"]);state["payload"]="x"*(2*1024*1024)
                tx.execute("UPDATE entity SET state=? WHERE id=?",(json.dumps(state),member))
        class Guarded:
            def __init__(self,tx):
                self.tx=tx
            def execute(self,sql,*args):
                if sql.startswith("SELECT id,kind,location,writer,fence,version,alive,") and args[0][0]==third:
                    raise AssertionError("member capture continued after byte admission exhaustion")
                return self.tx.execute(sql,*args)
        with self.store.transaction() as tx:
            with self.assertRaises(Conflict):
                self.offline.members(Guarded(tx),self.row(group))

    def test_foreign_world_scheduler_is_refused_without_overwriting_handlers(self):
        other = Store(Path(self.folder.name)/"foreign.db")
        try:
            foreign = World(other,world_id=99)
            scheduler = Scheduler(foreign)
            handlers = dict(scheduler.handlers)
            with self.assertRaises(Conflict):
                Offline(self.world,scheduler)
            self.assertEqual(scheduler.handlers,handlers)
            self.assertEqual(len(self.world.scale_handlers),1)
            self.assertEqual(other.db.execute("SELECT COUNT(*) FROM scheduled_event").fetchone()[0],0)
        finally:
            other.close()

    def test_foreign_offline_representation_cannot_register_combat_hazards_or_loot(self):
        from lostzone.economy import Catalog
        from lostzone.encounters import Encounters
        from lostzone.hazards import Hazards
        from lostzone.scavenging import Scavenging
        other = Store(Path(self.folder.name)/"foreign.db")
        try:
            foreign = World(other,world_id=99)
            scheduler = Scheduler(foreign)
            offline = Offline(foreign,scheduler)
            handlers = dict(scheduler.handlers)
            for service in (Encounters,Hazards,Scavenging):
                with self.subTest(service=service.__name__):
                    with self.assertRaises(Conflict):
                        service(self.world,offline,Catalog({}))
            self.assertEqual(scheduler.handlers,handlers)
            self.assertEqual(self.world.plan_validators,{})
            self.assertEqual(foreign.plan_validators,{})
            self.assertEqual(other.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0],0)
            self.assertEqual(self.row()["alive"],1)
        finally:
            other.close()

    def test_analytic_movement_hydrates_midroute_without_losing_state(self):
        self.dehydrate()
        route = self.offline.start_route("admin", uid(), self.npc, 2, [[0,0,0], [100,0,0], [100,0,100]], 2, 42)
        self.assertEqual(route["arrival_ms"], 1_000_000)
        self.ns = 50_000_000_000 # 50 real seconds = 500 game seconds, 100 metres
        self.assertEqual(self.offline.position_at(self.store.db, self.row(), self.world.now()), [100,0,0])
        result = self.offline.hydrate("a", uid(), self.npc, "cordon", self.fence, 3)
        state = json.loads(result["entities"][0]["state"])
        self.assertEqual(state["position"], [100,0,0])
        self.assertEqual((state["health"],state["ammo"],state["task"]), (.4,17,"patrol"))
        self.ns = 200_000_000_000
        self.assertEqual(self.scheduler.run_due(budget_ms=1000), 1)
        self.assertEqual(json.loads(self.row()["state"])["position"], [100,0,0])
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event").fetchone()[0], "CANCELLED")

    def test_real_speed_is_continuous_across_world_scale_change(self):
        self.dehydrate()
        self.offline.start_route("admin", uid(), self.npc, 2, [[0,0,0],[100,0,0]], 2, 42)
        self.ns = 10_000_000_000
        before = self.offline.position_at(self.store.db, self.row(), self.world.now())
        self.assertEqual(before, [20,0,0])
        self.world.set_scale("admin", uid(), 1)
        self.assertEqual(self.offline.position_at(self.store.db, self.row(), self.world.now()), before)
        self.ns += 10_000_000_000
        self.assertEqual(self.offline.position_at(self.store.db, self.row(), self.world.now()), [40,0,0])
        self.ns += 30_000_000_000
        self.assertEqual(self.scheduler.run_due(budget_ms=1000), 1)
        self.assertEqual(json.loads(self.row()["state"])["position"], [100,0,0])

    def test_restart_fences_offline_records_and_keeps_route_progress(self):
        self.dehydrate()
        self.offline.start_route("admin", uid(), self.npc, 2, [[0,0,0],[100,0,0]], 2, 42)
        self.ns = 10_000_000_000
        self.world.sample()
        self.store.close()
        self.ns = 50_000_000_000
        self.open()
        self.assertEqual(self.row()["fence"], self.store.epoch)
        self.assertEqual(self.offline.position_at(self.store.db, self.row(), self.world.now()), [20,0,0])
        self.ns += 40_000_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(json.loads(self.row()["state"])["position"], [100,0,0])

    def test_incomplete_capture_and_second_writer_are_refused(self):
        with self.assertRaises(Conflict):
            self.offline.dehydrate("a", uid(), self.npc, "cordon", self.fence, 1, {})
        self.dehydrate()
        with self.assertRaises(Conflict):
            self.ownership.update_entity("a", uid(), self.npc, self.fence, 2, {})
        self.offline.hydrate("a", uid(), self.npc, "cordon", self.fence, 2)
        with self.assertRaises(Conflict):
            self.offline.start_route("admin", uid(), self.npc, 4, [[0,0,0],[100,0,0]], 2, 42)

    def test_dead_members_do_not_move_or_respawn_with_living_group(self):
        dead = uid()
        self.ownership.create_entity("a", uid(), dead, "MUTANT", "cordon", self.fence,
                                     {"position": [10,0,0], "health": 1})
        self.ownership.kill("a", uid(), dead, self.fence, 1, "combat")
        group = uid()
        self.ownership.create_entity("a", uid(), group, "GROUP", "cordon", self.fence,
                                     {"position": [0,0,0], "member_ids": [self.npc,dead]})
        captures = {value: {"version": self.row(value)["version"], "state": json.loads(self.row(value)["state"])}
                    for value in (group,self.npc)}
        self.offline.dehydrate("a", uid(), group, "cordon", self.fence, 1, captures)
        self.offline.start_route("admin", uid(), group, 2, [[0,0,0],[100,0,0]], 2, 42)
        with self.assertRaises(Conflict):
            self.offline.hydrate("a", uid(), self.npc, "cordon", self.fence, 2)
        self.ns = 50_000_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(json.loads(self.row()["state"])["position"], [100,0,0])
        self.assertEqual(json.loads(self.row(dead)["state"])["position"], [10,0,0])
        self.assertEqual(self.row(dead)["alive"], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 3)

    def test_location_recovery_does_not_steal_abstract_ownership(self):
        self.dehydrate()
        self.offline.start_route("admin", uid(), self.npc, 2, [[0,0,0],[100,0,0]], 2, 42)
        self.utc += 20_000_000_000
        fence = self.world.claim_location("b", uid(), "cordon")["fence"]
        result = self.ownership.recover_location("b", uid(), "cordon", fence)
        self.assertEqual(result["entities"], [])
        self.assertEqual(self.row()["writer"], "offline:cordon")
        self.ns += 10_000_000_000
        result = self.offline.hydrate("b", uid(), self.npc, "cordon", fence, 3)
        self.assertEqual(json.loads(result["entities"][0]["state"])["position"], [20,0,0])

    def test_rebasing_routes_leaves_one_pending_arrival_and_rejects_bad_capture(self):
        from lostzone import Invalid
        with self.assertRaises(Invalid):
            self.offline.dehydrate("a", uid(), self.npc, "cordon", self.fence, 1, {self.npc: {}})
        self.dehydrate()
        self.offline.start_route("admin", uid(), self.npc, 2, [[0,0,0],[100,0,0]], 2, 42)
        for scale in (1,2,3,4,5):
            self.world.set_scale("admin", uid(), scale)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM scheduled_event WHERE state='PENDING'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
