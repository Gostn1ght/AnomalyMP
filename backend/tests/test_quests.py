import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.ownership import Ownership
from lostzone.transfers import Transfers
from lostzone.quests import Quests
from lostzone.scheduler import Scheduler


def uid():
    return uuid.uuid4().hex


class QuestTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "world.db")
        self.world = World(self.store)
        self.ownership = Ownership(self.world)
        self.transfers = Transfers(self.world, b"key-" * 8)
        self.a = self.world.claim_location("a", uid(), "cordon")["fence"]
        self.b = self.world.claim_location("b", uid(), "jupiter")["fence"]
        self.player, self.target, self.unique = uid(), uid(), uid()
        self.ownership.create_entity("a", uid(), self.player, "CHARACTER", "cordon", self.a,
                                     {"health": .7, "money": 500}, account="test")
        self.ownership.create_entity("b", uid(), self.target, "NPC", "jupiter", self.b, {"health": 1})
        self.ownership.create_entity("b", uid(), self.unique, "NPC", "jupiter", self.b, {"health": .4})
        self.definition = {"steps": [{"type": "EntityDied", "target": self.target}],
                           "requirements": [{"entity_id": self.unique}],
                           "reward": {"money": 1500, "items": [{"section": "medkit", "quantity": 2}]}}
        self.quests = Quests(self.world, {"jupiter_task": self.definition})

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def test_cross_location_quest_keeps_links_and_reward_is_once(self):
        self.quests.grant("a", uid(), self.player, self.a, "jupiter_task")
        prepared = self.transfers.prepare("a", uid(), self.player, "cordon", self.a, "jupiter", 1)
        self.transfers.claim("b", uid(), prepared["token"], self.b)
        self.transfers.commit("b", uid(), prepared["transfer_id"], self.b)
        requirements = self.quests.requirements("b", self.player, self.b)
        self.assertEqual(requirements[0]["entity_id"], self.unique)
        self.assertEqual(requirements[0]["location"], "jupiter")
        event = self.ownership.kill("b", uid(), self.target, self.b, 1, "combat")["event"]
        key = uid()
        result = self.quests.progress("b", key, self.player, self.b, "jupiter_task", 1, event)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(self.quests.progress("b", key, self.player, self.b, "jupiter_task", 1, event), result)
        self.assertEqual(self.quests.progress("b", uid(), self.player, self.b, "jupiter_task", 2, event), result)
        state = json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?", (self.player,)).fetchone()[0])
        self.assertEqual(state["money"], 2000)
        self.assertEqual(self.store.db.execute("SELECT SUM(quantity) FROM item WHERE holder=?", (self.player,)).fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 3)

    def test_unique_death_fails_quest_and_never_resurrects_npc(self):
        self.quests.grant("a", uid(), self.player, self.a, "jupiter_task")
        event = self.ownership.kill("b", uid(), self.unique, self.b, 1, "offline_anomaly")["event"]
        result = self.quests.progress("a", uid(), self.player, self.a, "jupiter_task", 1, event)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?", (self.unique,)).fetchone()[0], 0)
        with self.assertRaises(Conflict):
            self.ownership.create_entity("b", uid(), self.unique, "NPC", "jupiter", self.b, {})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0], 0)

    def test_wrong_event_and_active_quest_corpse_protection(self):
        # Requirement does not need the target alive but pins its body.
        definition = {"steps": [{"type": "EntityDied", "target": self.unique}],
                      "requirements": [{"entity_id": self.target, "alive_required": False}]}
        quests = Quests(self.world, {"corpse_task": definition})
        quests.grant("a", uid(), self.player, self.a, "corpse_task")
        event = self.ownership.kill("b", uid(), self.target, self.b, 1, "combat")["event"]
        with self.assertRaises(Conflict):
            quests.progress("a", uid(), self.player, self.a, "corpse_task", 1, event)
        with self.assertRaises(Conflict):
            self.ownership.cleanup_corpse("b", uid(), self.target, self.b, 2)
        self.assertEqual(quests.scheduler.run_due(budget_ms=1000),0)
        with self.assertRaises(Conflict):
            self.ownership.cleanup_corpse("b", uid(), self.target, self.b, 2)

    def test_missing_and_dead_requirement_do_not_spawn_copies(self):
        self.ownership.kill("b", uid(), self.unique, self.b, 1, "combat")
        result = self.quests.grant("a", uid(), self.player, self.a, "jupiter_task")
        self.assertEqual(result["status"], "FAILED")
        bad = Quests(self.world, {"missing": {"steps": [{"type": "EntityDied", "target": self.target}],
                                            "requirements": [{"entity_id": uid()}]}})
        with self.assertRaises(Conflict):
            bad.grant("a", uid(), self.player, self.a, "missing")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 3)

    def quest_state(self, quest_id="jupiter_task"):
        row = self.store.db.execute("SELECT state FROM quest WHERE character_id=? AND id=?",(self.player,quest_id)).fetchone()
        return json.loads(row[0])

    def test_death_fails_without_player_polling_and_survives_player_handoff(self):
        self.quests.grant("a",uid(),self.player,self.a,"jupiter_task")
        prepared = self.transfers.prepare("a",uid(),self.player,"cordon",self.a,"jupiter",1)
        self.ownership.kill("b",uid(),self.unique,self.b,1,"combat")
        self.assertEqual(self.quest_state()["status"],"ACTIVE")
        self.quests.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.quest_state()["status"],"FAILED")
        self.transfers.claim("b",uid(),prepared["token"],self.b)
        self.transfers.commit("b",uid(),prepared["transfer_id"],self.b)
        self.assertEqual(self.quest_state()["status"],"FAILED")
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(self.player,)).fetchone()[0])["money"],500)
        self.ownership.cleanup_corpse("b",uid(),self.unique,self.b,2)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='QuestFailed'").fetchone()[0],1)

    def test_old_committed_death_is_reconciled_after_restart_without_respawn(self):
        self.quests.grant("a",uid(),self.player,self.a,"jupiter_task")
        self.world.quest_death_queue = None # Simulate a pre-subscriber service.
        event = self.ownership.kill("b",uid(),self.unique,self.b,1,"combat")["event"]
        path = self.store.path
        self.store.close()
        self.store = Store(path)
        self.world = World(self.store)
        self.quests = Quests(self.world,{"jupiter_task":self.definition})
        # A separately constructed scheduler still shares registered handlers.
        Scheduler(self.world).run_due(budget_ms=1000)
        state = self.quest_state()
        self.assertEqual((state["status"],state["failure_entity"]),("FAILED",self.unique))
        self.assertEqual(state["failure_event"],self.store.db.execute("SELECT id FROM world_event WHERE sequence=?",(event,)).fetchone()[0])
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.unique,)).fetchone()[0],0)
        self.assertEqual(self.quests.reconcile("admin",uid())["scheduled"],0)

    def test_large_death_fanout_commits_bounded_batches_and_releases_pin_only_after_last(self):
        self.quests = Quests(self.world,{f"batch_{i:03d}":self.definition for i in range(65)})
        for i in range(65):
            self.quests.grant("a",uid(),self.player,self.a,f"batch_{i:03d}")
        self.ownership.kill("b",uid(),self.unique,self.b,1,"combat")
        self.assertEqual(self.quests.scheduler.run_due(limit=1,budget_ms=1000),1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM quest WHERE json_extract(state,'$.status')='FAILED'").fetchone()[0],64)
        with self.assertRaises(Conflict):
            self.ownership.cleanup_corpse("b",uid(),self.unique,self.b,2)
        self.assertEqual(self.quests.scheduler.run_due(limit=1,budget_ms=1000),1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM quest WHERE json_extract(state,'$.status')='FAILED'").fetchone()[0],65)
        self.ownership.cleanup_corpse("b",uid(),self.unique,self.b,2)
        self.assertEqual(self.quests.scheduler.run_due(budget_ms=1000),0)

    def test_failure_evidence_rolls_back_quest_batch_but_preserves_committed_death(self):
        self.quests.grant("a",uid(),self.player,self.a,"jupiter_task")
        self.ownership.kill("b",uid(),self.unique,self.b,1,"combat")
        original = self.store.event
        def fail(tx,aggregate,event_type,*args,**kwargs):
            if event_type=="QuestFailed":
                raise RuntimeError("injected quest failure journal error")
            return original(tx,aggregate,event_type,*args,**kwargs)
        self.store.event = fail
        with self.assertRaises(RuntimeError):
            self.quests.scheduler.run_due(budget_ms=1000)
        self.store.event = original
        self.assertEqual(self.quest_state()["status"],"ACTIVE")
        self.assertEqual(self.store.db.execute("SELECT alive FROM entity WHERE id=?",(self.unique,)).fetchone()[0],0)
        self.quests.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.quest_state()["status"],"FAILED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='QuestFailed'").fetchone()[0],1)

    def test_last_member_death_fails_group_requirement_from_committed_group_evidence(self):
        group = uid()
        self.ownership.create_entity("b",uid(),group,"GROUP","jupiter",self.b,{"member_ids":[self.unique]})
        self.quests = Quests(self.world,{"group_task":{"steps":[{"type":"EntityDied","target":self.target}],
                                                      "requirements":[{"entity_id":group}]}})
        self.quests.grant("a",uid(),self.player,self.a,"group_task")
        self.ownership.kill("b",uid(),self.unique,self.b,1,"combat")
        self.quests.scheduler.run_due(budget_ms=1000)
        state = self.quest_state("group_task")
        self.assertEqual((state["status"],state["failure_entity"]),("FAILED",group))
        self.assertEqual(self.store.db.execute("SELECT type FROM world_event WHERE id=?",(state["failure_event"],)).fetchone()[0],"GroupLostAllMembers")

    def test_scheduler_from_other_world_cannot_resolve_this_worlds_quests(self):
        other_store = Store(Path(self.folder.name)/"other.db")
        try:
            other_world = World(other_store)
            with self.assertRaises(Conflict):
                Quests(self.world,{},scheduler=Scheduler(other_world))
        finally:
            other_store.close()

    def test_reconcile_cursor_gets_past_unproven_legacy_deaths_without_inventing_evidence(self):
        ids = [f"{i:032x}" for i in range(1,66)]
        definitions = {}
        for i,entity_id in enumerate(ids):
            self.ownership.create_entity("b",uid(),entity_id,"NPC","jupiter",self.b,{"health":1})
            definitions[f"legacy_{i}"] = {"steps":[{"type":"EntityDied","target":self.target}],
                                          "requirements":[{"entity_id":entity_id}]}
        self.quests = Quests(self.world,definitions)
        for quest_id in definitions:
            self.quests.grant("a",uid(),self.player,self.a,quest_id)
        # Older imported records lack journal evidence; keep their quest pins.
        with self.store.transaction() as tx:
            tx.executemany("UPDATE entity SET alive=0 WHERE id=?",[(i,) for i in ids[:64]])
        self.world.quest_death_queue = None
        self.ownership.kill("b",uid(),ids[64],self.b,1,"combat")
        first = self.quests.reconcile("admin",uid())
        self.assertEqual((first["examined"],first["scheduled"],first["unproven"],first["next_after"]),
                         (64,0,ids[:64],ids[63]))
        key = uid()
        second = self.quests.reconcile("admin",key,first["next_after"])
        self.assertEqual((second["examined"],second["scheduled"],second["next_after"]),(1,1,None))
        self.assertEqual(self.quests.reconcile("admin",key,first["next_after"]),second)
        self.quests.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.quest_state("legacy_64")["status"],"FAILED")
        self.assertEqual(self.quest_state("legacy_0")["status"],"ACTIVE")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='EntityDied'").fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
