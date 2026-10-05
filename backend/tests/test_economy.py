from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone import Store, World, Conflict, Invalid
from lostzone.economy import Catalog, Trade
from lostzone.ownership import Ownership
from lostzone.offline import Offline
from lostzone.scheduler import Scheduler
from lostzone.scavenging import Scavenging


def uid():
    return uuid.uuid4().hex


class EconomyTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/"world.db"
        self.ns = 0
        self.utc = 1_800_000_000_000_000_000
        self.open()
        self.fence = self.world.claim_location("a",uid(),"cordon")["fence"]
        self.player,self.trader = uid(),uid()
        self.ownership.create_entity("a",uid(),self.player,"CHARACTER","cordon",self.fence,
                                     {"money":1000,"position":[0,0,0],"carry_capacity_g":5000},account="p")
        self.ownership.create_entity("a",uid(),self.trader,"TRADER","cordon",self.fence,
                                     {"money":5000,"position":[1,0,0],"trade_profile":"general"})

    def open(self):
        self.store = Store(self.path)
        self.world = World(self.store,seed=42,monotonic=lambda:self.ns,wall=lambda:self.utc)
        self.ownership = Ownership(self.world)
        self.catalog = Catalog({"food":{"category":"FOOD","price":100,"weight_g":100},
                                "wpn_ak":{"category":"WEAPON","price":3000,"weight_g":4000},
                                "armor":{"category":"ARMOR","price":10000,"weight_g":10000}})
        self.trade = Trade(self.world,self.catalog,{"general":{"buy_categories":["FOOD","WEAPON"],"min_condition_bp":2000}})
        self.scheduler = Scheduler(self.world)
        self.offline = Offline(self.world,self.scheduler)
        self.scavenging = Scavenging(self.world,self.offline,self.catalog,{"chance_bp":10000})

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def item(self,section="food",kind="TRADE",holder=None,quantity=1,state=None):
        item = uid()
        self.ownership.create_item("a",uid(),item,section,"cordon",self.fence,kind,holder or self.trader,quantity,state or {})
        return item

    def trade_args(self,item,direction="BUY",**updates):
        result = dict(character_id=self.player,trader_id=self.trader,item_id=item,location="cordon",fence=self.fence,
                      direction=direction,character_version=1,trader_version=1,item_version=1,price_limit=10000)
        result.update(updates)
        return result

    def money(self,entity_id):
        return json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(entity_id,)).fetchone()[0])["money"]

    def test_buy_sell_money_and_stack_are_atomic_and_retry_survives_restart(self):
        item = self.item(quantity=4,state={"condition":.75,"attachments":["scope"]})
        command = uid()
        args = self.trade_args(item)
        bought = self.trade.transact("a",command,**args)
        self.assertEqual((bought["price"],self.money(self.player),self.money(self.trader)),(300,700,5300))
        self.store.close();self.open()
        self.assertEqual(self.trade.transact("a",command,**args),bought)
        sold = self.trade.transact("a",uid(),**self.trade_args(item,"SELL",character_version=2,trader_version=2,item_version=2,price_limit=100))
        self.assertEqual((sold["price"],self.money(self.player),self.money(self.trader)),(150,850,5150))
        row = self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()
        self.assertEqual((row["id"],row["kind"],row["holder"],row["quantity"]),(item,"TRADE",self.trader,4))
        self.assertEqual(json.loads(row["state"])["attachments"],["scope"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0],1)
        self.assertEqual(json.loads(self.store.db.execute("SELECT state FROM character WHERE id=?",(self.player,)).fetchone()[0])["money"],850)

    def test_preferences_condition_funds_weight_and_price_limits_reject_without_changes(self):
        for section,state in (("armor",{}),("wpn_ak",{"condition":.1})):
            item = self.item(section,"PLAYER",self.player,state=state)
            with self.assertRaises(Conflict):
                self.trade.transact("a",uid(),**self.trade_args(item,"SELL",price_limit=0))
        item = self.item(quantity=60)
        with self.assertRaises(Conflict):
            self.trade.transact("a",uid(),**self.trade_args(item))
        cheap = self.item()
        with self.assertRaises(Conflict):
            self.trade.transact("a",uid(),**self.trade_args(cheap,price_limit=99))
        self.assertEqual((self.money(self.player),self.money(self.trader)),(1000,5000))
        self.assertEqual(self.store.db.execute("SELECT kind FROM item WHERE id=?",(cheap,)).fetchone()[0],"TRADE")
        # Sufficient funds, insufficient weight: fixed capacity is still enforced.
        with self.store.transaction() as tx:
            state = {"money":100000,"carry_capacity_g":0}
            tx.execute("UPDATE entity SET state=? WHERE id=?",(json.dumps(state),self.player))
        with self.assertRaises(Conflict):
            self.trade.transact("a",uid(),**self.trade_args(cheap))

    def test_concurrent_purchase_has_one_owner_and_failed_commit_rolls_back_wallets(self):
        item = self.item()
        original = self.store.event
        def fail(*args,**kwargs):
            raise RuntimeError("injected journal failure")
        self.store.event = fail
        with self.assertRaises(RuntimeError):
            self.trade.transact("a",uid(),**self.trade_args(item))
        self.store.event = original
        self.assertEqual((self.money(self.player),self.money(self.trader)),(1000,5000))
        def buy(_):
            try:
                self.trade.transact("a",uid(),**self.trade_args(item));return True
            except Conflict:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(buy,range(2))),1)
        self.assertEqual((self.money(self.player),self.money(self.trader)),(900,5100))

    def test_catalog_and_arbitrage_profiles_fail_closed(self):
        with self.assertRaises(Invalid):
            Trade(self.world,self.catalog,{"x":{"buy_categories":["FOOD"],"buy_bp":11000,"sell_bp":10000}})
        with self.assertRaises(Invalid):
            Catalog({"x":{"category":"FOOD","price":True,"weight_g":1}})
        item = self.item(section="unknown")
        with self.assertRaises(Conflict):
            self.trade.transact("a",uid(),**self.trade_args(item))

    def setup_visit(self,policy="NPC_ACCESSIBLE"):
        self.npc,self.stash = uid(),uid()
        self.ownership.create_entity("a",uid(),self.npc,"NPC","cordon",self.fence,{"position":[0,0,0],"faction":"loner"})
        self.ownership.create_entity("a",uid(),self.stash,"STASH","cordon",self.fence,{"position":[1,0,0]},policy=policy,owner=self.player)
        for entity_id in (self.npc,self.stash):
            row = self.store.db.execute("SELECT * FROM entity WHERE id=?",(entity_id,)).fetchone()
            self.offline.dehydrate("a",uid(),entity_id,"cordon",self.fence,1,
                                   {entity_id:{"version":1,"state":json.loads(row["state"])}})

    def visit(self,due=1000):
        rows = {value:self.store.db.execute("SELECT version FROM entity WHERE id=?",(value,)).fetchone()[0]
                for value in (self.npc,self.stash)}
        return self.scavenging.schedule("admin",uid(),uid(),self.npc,self.stash,rows[self.npc],rows[self.stash],due,17)

    def test_stash_deposit_preserves_items_after_restart_and_has_visit_cooldown(self):
        self.setup_visit()
        # Trusted bootstrap item before abstract ownership is captured.
        item = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,?,'NPC',?,2,1,?)",(item,"food",self.npc,json.dumps({"condition":.8})))
        self.visit()
        self.store.close();self.open()
        self.ns = 100_000_000
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        row = self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()
        self.assertEqual((row["kind"],row["holder"],row["quantity"]),("STASH",self.stash,2))
        self.assertEqual(json.loads(row["state"])["condition"],.8)
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)
        with self.assertRaises(Conflict):
            self.visit(due=2000)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0],1)

    def test_armor_weapons_and_protected_stashes_never_get_automatic_deposits(self):
        self.setup_visit()
        with self.store.transaction() as tx:
            for section in ("wpn_ak","armor"):
                tx.execute("INSERT INTO item VALUES(?,?,'NPC',?,1,1,'{}')",(uid(),section,self.npc))
        self.visit();self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM item WHERE kind='STASH'").fetchone()[0],0)
        with self.store.transaction() as tx:
            tx.execute("UPDATE container SET policy='PLAYER_ONLY' WHERE id=?",(self.stash,))
        with self.assertRaises(Conflict):
            self.visit(due=30_000_000)

    def test_hydrated_stash_cancels_visit_and_static_objects_cannot_move(self):
        self.setup_visit()
        self.visit()
        self.offline.hydrate("a",uid(),self.stash,"cordon",self.fence,2)
        self.ns=100_000_000
        self.scheduler.run_due(budget_ms=1000)
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event").fetchone()[0],"CANCELLED")
        self.setup_visit()
        with self.assertRaises(Conflict):
            self.offline.start_route("admin",uid(),self.stash,2,[[1,0,0],[100,0,0]],2,42)

    def test_group_member_visit_uses_current_route_position(self):
        self.setup_visit()
        group = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'GROUP','cordon','offline:cordon',?,1,1,?)",
                       (group,self.store.epoch,json.dumps({"position":[0,0,0],"member_ids":[self.npc]})))
            tx.execute("INSERT INTO group_member VALUES(?,?)",(group,self.npc))
        self.offline.start_route("admin",uid(),group,1,[[0,0,0],[100,0,0]],2,42)
        row = self.store.db.execute("SELECT * FROM entity WHERE id=?",(self.npc,)).fetchone()
        self.assertEqual(self.offline.position_at(self.store.db,row,100_000),[20,0,0])
        self.visit(due=100_000);self.ns=10_000_000_000
        self.scheduler.run_due(budget_ms=1000)
        event = self.store.db.execute("SELECT * FROM scheduled_event WHERE type='StashVisited'").fetchone()
        self.assertEqual(json.loads(event["result"])["reason"],"route does not reach this stash")

    def visit_group(self):
        group = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO entity VALUES(?,'GROUP','cordon','offline:cordon',?,1,1,?)",
                       (group,self.store.epoch,json.dumps({"position":[0,0,0],"member_ids":[self.npc]})))
            tx.execute("INSERT INTO group_member VALUES(?,?)",(group,self.npc))
        self.offline.start_route("admin",uid(),group,1,[[0,0,0],[100,0,0]],2,42)
        return group

    def visit_food(self):
        item = uid()
        with self.store.transaction() as tx:
            tx.execute("INSERT INTO item VALUES(?,?,'NPC',?,1,1,'{}')",(item,"food",self.npc))
        return item

    def assert_visit_cancelled_without_mutation(self, item):
        self.ns = 100_000_000
        self.scheduler.run_due(budget_ms=1000)
        row = self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()
        self.assertEqual((row["kind"],row["holder"],row["version"]),("NPC",self.npc,1))
        self.assertEqual(self.store.db.execute("SELECT state FROM scheduled_event WHERE type='StashVisited'").fetchone()[0],"CANCELLED")
        for entity_id,key in ((self.npc,"last_scavenge_ms"),(self.stash,"last_npc_visit_ms")):
            state = json.loads(self.store.db.execute("SELECT state FROM entity WHERE id=?",(entity_id,)).fetchone()[0])
            self.assertNotIn(key,state)

    def test_group_route_replacement_cancels_nearby_visit_without_member_version_change(self):
        self.setup_visit()
        group = self.visit_group()
        item = self.visit_food()
        self.visit()
        self.offline.start_route("admin",uid(),group,2,[[0,0,0],[0,0,100]],2,43)
        self.assertEqual(self.store.db.execute("SELECT version FROM entity WHERE id=?",(self.npc,)).fetchone()[0],2)
        self.assert_visit_cancelled_without_mutation(item)

    def rebase_visit(self, grouped):
        self.setup_visit()
        if grouped:
            self.visit_group()
        else:
            self.offline.start_route("admin",uid(),self.npc,2,[[0,0,0],[100,0,0]],2,42)
        item = self.visit_food()
        self.visit()
        before = self.store.db.execute("SELECT version FROM entity WHERE id=?",(self.npc,)).fetchone()[0]
        self.world.set_scale("admin",uid(),20)
        self.assertEqual(self.store.db.execute("SELECT version FROM entity WHERE id=?",(self.npc,)).fetchone()[0],before)
        # Both old/new positions are within reach; cancellation must
        # come from the stale capture, rather than a distance miss.
        npc = self.store.db.execute("SELECT * FROM entity WHERE id=?",(self.npc,)).fetchone()
        self.assertLess(sum(p*p for p in self.offline.position_at(self.store.db,npc,1000)),100)
        self.assert_visit_cancelled_without_mutation(item)

    def test_scale_rebase_cancels_nearby_solo_visit(self):
        self.rebase_visit(False)

    def test_scale_rebase_cancels_nearby_group_visit(self):
        self.rebase_visit(True)

    def test_group_visit_survives_authority_restart_and_moves_same_item_once(self):
        self.setup_visit()
        self.visit_group()
        item = self.visit_food()
        self.visit()
        self.store.close();self.open()
        self.ns = 100_000_000
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),1)
        row = self.store.db.execute("SELECT * FROM item WHERE id=?",(item,)).fetchone()
        self.assertEqual((row["id"],row["kind"],row["holder"],row["version"]),(item,"STASH",self.stash,2))
        self.assertEqual(self.scheduler.run_due(budget_ms=1000),0)

    def test_legacy_visit_without_motion_capture_is_cancelled(self):
        self.setup_visit()
        item = self.visit_food()
        self.visit()
        with self.store.transaction() as tx:
            row = tx.execute("SELECT * FROM scheduled_event WHERE type='StashVisited'").fetchone()
            plan = json.loads(row["payload"])
            del plan["positions"]
            tx.execute("UPDATE scheduled_event SET payload=? WHERE id=?",(json.dumps(plan),row["id"]))
        self.assert_visit_cancelled_without_mutation(item)


if __name__=="__main__":
    unittest.main()
