"""Real command replays must not revive a retired location/entity writer."""
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict
from lostzone.ownership import Ownership
from lostzone.transfers import Transfers
from lostzone.economy import Catalog, Trade
from lostzone.quests import Quests


def uid():
    return uuid.uuid4().hex


class ReplayFencingTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.folder.name)/"world.db")
        self.ns=0;self.utc=1_800_000_000_000_000_000
        self.world=World(self.store,monotonic=lambda:self.ns,wall=lambda:self.utc)
        self.ownership=Ownership(self.world)
        self.transfers=Transfers(self.world,b"replay-key-"*4)
        self.claim_key=uid()
        self.fence=self.world.claim_location("a",self.claim_key,"cordon")["fence"]
        self.target_fence=self.world.claim_location("b",uid(),"garbage")["fence"]
        self.records=[]

    def tearDown(self):
        self.store.close();self.folder.cleanup()

    def record(self,name,call):
        result=call()
        self.assertEqual(call(),result)
        self.records.append((name,call,result))
        return result

    def version(self,entity):
        return self.store.db.execute("SELECT version FROM entity WHERE id=?",(entity,)).fetchone()[0]

    def durable(self):
        return {name:[tuple(row) for row in self.store.db.execute("SELECT * FROM "+name+" ORDER BY rowid")]
                for name in ("entity","item","transfer","player_session","character","quest","command_result","world_event","location_lease")}

    def populated_commands(self):
        self.record("claim",lambda:self.world.claim_location("a",self.claim_key,"cordon"))
        key=uid();self.record("renew",lambda key=key:self.world.renew_location("a",key,"cordon",self.fence))
        player,npc,trader=uid(),uid(),uid()
        for entity,kind,state,extra in (
                (player,"CHARACTER",{"position":[0,0,0],"health":1,"money":1000},{"account":"player"}),
                (npc,"NPC",{"position":[1,0,0],"health":1},{}),
                (trader,"TRADER",{"position":[1,0,0],"money":1000,"trade_profile":"general"},{})):
            key=uid()
            self.record("create "+kind,lambda entity=entity,kind=kind,state=state,extra=extra,key=key:
                        self.ownership.create_entity("a",key,entity,kind,"cordon",self.fence,state,**extra))
        floor,stock=uid(),uid()
        for item,kind,holder in ((floor,"WORLD","cordon"),(stock,"TRADE",trader)):
            key=uid()
            self.record("create item "+kind,lambda item=item,kind=kind,holder=holder,key=key:
                        self.ownership.create_item("a",key,item,"food","cordon",self.fence,kind,holder))
        key=uid()
        self.record("move",lambda key=key:self.ownership.move_item("a",key,floor,"cordon",self.fence,1,
                    "WORLD","cordon","PLAYER",player,player))
        key=uid()
        self.record("update",lambda key=key:self.ownership.update_entity("a",key,npc,self.fence,1,{"position":[1,0,0],"health":.9}))
        key=uid()
        self.record("disconnect",lambda key=key:self.ownership.disconnect("a",key,player,self.fence,1,{"position":[0,0,0],"money":1000,"health":1}))
        key=uid()
        self.record("resume",lambda key=key:self.ownership.resume("a",key,player,"cordon",self.fence,2))
        catalog=Catalog({"food":{"category":"FOOD","price":100,"weight_g":100}})
        trade=Trade(self.world,catalog,{"general":{"buy_categories":["FOOD"]}})
        key=uid()
        self.record("trade",lambda key=key:trade.transact("a",key,player,trader,stock,"cordon",self.fence,"BUY",3,1,1,1000))
        quests=Quests(self.world,{"task":{"steps":[{"type":"EntityDied","target":npc}],"reward":{"money":10}}})
        key=uid();self.record("quest grant",lambda key=key:quests.grant("a",key,player,self.fence,"task"))
        key=uid()
        death=self.record("death",lambda key=key:self.ownership.kill("a",key,npc,self.fence,2,"combat"))
        key=uid()
        self.record("quest progress",lambda key=key:quests.progress("a",key,player,self.fence,"task",1,death["event"]))
        key=uid()
        self.record("corpse cleanup",lambda key=key:self.ownership.cleanup_corpse("a",key,npc,self.fence,3))
        prepared=self.transfers.prepare("a",uid(),player,"cordon",self.fence,"garbage",self.version(player))
        key=uid()
        self.record("abort",lambda key=key:self.transfers.abort("a",key,prepared["transfer_id"],self.fence))
        key=uid()
        self.record("recover",lambda key=key:self.ownership.recover_location("a",key,"cordon",self.fence))

    def test_current_writer_replays_after_own_effects_without_duplicate_mutations(self):
        self.populated_commands();before=self.durable()
        for name,call,result in self.records:
            with self.subTest(operation=name):
                self.assertEqual(call(),result)
        self.assertEqual(self.durable(),before)

    def test_expired_writer_cannot_replay_successes_or_change_durable_state(self):
        self.populated_commands();self.utc+=16_000_000_000;before=self.durable()
        for name,call,_ in self.records:
            with self.subTest(operation=name):
                with self.assertRaises(Conflict):
                    call()
        self.assertEqual(self.durable(),before)

    def test_new_fence_under_same_principal_does_not_reauthorize_old_results(self):
        self.populated_commands();self.utc+=16_000_000_000
        fresh=self.world.claim_location("a",uid(),"cordon")["fence"]
        self.assertGreater(fresh,self.fence)
        self.ownership.recover_location("a",uid(),"cordon",fresh)
        before=self.durable()
        for name,call,_ in self.records:
            with self.subTest(operation=name):
                with self.assertRaises(Conflict):
                    call()
        self.assertEqual(self.durable(),before)

    def test_new_principal_does_not_reauthorize_retired_writer_results(self):
        self.populated_commands();self.utc+=16_000_000_000
        fresh=self.world.claim_location("new-a",uid(),"cordon")["fence"]
        self.ownership.recover_location("new-a",uid(),"cordon",fresh)
        before=self.durable()
        for name,call,_ in self.records:
            with self.subTest(operation=name):
                with self.assertRaises(Conflict):
                    call()
        self.assertEqual(self.durable(),before)

    def test_character_handoff_rejects_source_entity_results_with_source_lease_still_valid(self):
        self.populated_commands()
        player=self.store.db.execute("SELECT id FROM character").fetchone()[0]
        prepared=self.transfers.prepare("a",uid(),player,"cordon",self.fence,"garbage",self.version(player))
        self.transfers.claim("b",uid(),prepared["token"],self.target_fence)
        self.transfers.commit("b",uid(),prepared["transfer_id"],self.target_fence)
        self.world.require_location(self.store.db,"a","cordon",self.fence)
        before=self.durable()
        for name,call,_ in self.records:
            if name in ("move","disconnect","resume","trade","quest grant","quest progress"):
                with self.subTest(operation=name):
                    with self.assertRaises(Conflict):
                        call()
        self.assertEqual(self.durable(),before)


if __name__=="__main__":
    unittest.main()
