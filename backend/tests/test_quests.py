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

    def test_missing_and_dead_requirement_do_not_spawn_copies(self):
        self.ownership.kill("b", uid(), self.unique, self.b, 1, "combat")
        result = self.quests.grant("a", uid(), self.player, self.a, "jupiter_task")
        self.assertEqual(result["status"], "FAILED")
        bad = Quests(self.world, {"missing": {"steps": [{"type": "EntityDied", "target": self.target}],
                                            "requirements": [{"entity_id": uid()}]}})
        with self.assertRaises(Conflict):
            bad.grant("a", uid(), self.player, self.a, "missing")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entity").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
