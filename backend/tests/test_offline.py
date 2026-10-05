import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
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
