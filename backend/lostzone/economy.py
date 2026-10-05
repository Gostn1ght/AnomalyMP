"""Trusted price catalog and atomic whole-stack trades over the item ledger.

The engine adapter still owns interaction distance/UI and binds the requested
character to the authenticated player. Prices/categories never come from a
player packet. No merchant or stash stock is rerolled by this module.
"""
import json

from .ownership import Ownership
from .store import Conflict, Invalid, canonical, finite, identifier, persistent_id, positive


CATEGORIES = frozenset(("FOOD", "MEDICINE", "AMMO", "JUNK", "TOOL", "ARTIFACT", "WEAPON", "ARMOR"))
DEPOSIT_CATEGORIES = CATEGORIES - {"WEAPON", "ARMOR", "ARTIFACT"}


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise Invalid("invalid " + name)
    return value


class Catalog:
    def __init__(self, entries=None):
        entries = {} if entries is None else entries
        if not isinstance(entries, dict) or len(entries) > 10000:
            raise Invalid("invalid trusted item catalog")
        self.entries = {}
        for section, record in entries.items():
            identifier(section)
            if not isinstance(record, dict) or record.get("category") not in CATEGORIES:
                raise Invalid("invalid catalog category")
            protection = record.get("hazard_protection_bp",{})
            if not isinstance(protection,dict) or len(protection)>16:
                raise Invalid("invalid equipment hazard protection")
            protection = {identifier(kind):integer(value,0,10000,"hazard protection") for kind,value in protection.items()}
            if protection and record["category"] not in ("ARMOR","ARTIFACT"):
                raise Invalid("hazard protection requires armor or artifact")
            self.entries[section] = {
                "category": record["category"],
                "price": integer(record.get("price"), 1, 1_000_000_000, "base price"),
                "weight_g": integer(record.get("weight_g"), 0, 1_000_000, "item weight"),
                "combat_power": integer(record.get("combat_power",100 if record["category"]=="WEAPON" else 0),0,10000,"combat power"),
                "hazard_protection_bp":protection}

    def entry(self, section):
        if section not in self.entries:
            raise Conflict("item has no trusted price/category definition")
        return self.entries[section]

    def carry_weight(self, tx, holder):
        total = 0
        for index,row in enumerate(tx.execute("SELECT section,quantity FROM item WHERE holder=? AND kind IN('PLAYER','NPC') ORDER BY id LIMIT 1025", (holder,))):
            if index == 1024:
                raise Conflict("inventory requires compaction before bounded weight calculation")
            total += self.entry(row["section"])["weight_g"] * row["quantity"]
        return total


class Trade:
    def __init__(self, world, catalog, profiles=None):
        self.world, self.store, self.catalog = world, world.store, catalog
        self.ownership = Ownership(world)
        self.profiles = {}
        profiles = {} if profiles is None else profiles
        if not isinstance(profiles, dict) or len(profiles) > 256:
            raise Invalid("invalid merchant profiles")
        for name, record in profiles.items():
            identifier(name)
            if not isinstance(record, dict) or not isinstance(record.get("buy_categories"), list):
                raise Invalid("invalid merchant preferences")
            categories = record["buy_categories"]
            if any(value not in CATEGORIES for value in categories):
                raise Invalid("invalid merchant category")
            buy = integer(record.get("buy_bp", 5000), 1, 100000, "merchant buy multiplier")
            sell = integer(record.get("sell_bp", 10000), 1, 100000, "merchant sell multiplier")
            if buy > sell:
                raise Invalid("merchant price spread would create a buy/sell loop")
            self.profiles[name] = {"buy_categories": frozenset(categories), "buy_bp": buy, "sell_bp": sell,
                                   "min_condition_bp": integer(record.get("min_condition_bp", 0), 0, 10000, "minimum condition")}

    def inspect(self, tx, actor, character_id, trader_id, item_id, location, fence, direction,
                character_version, trader_version, item_version):
        self.world.require_location(tx, actor, location, fence)
        character = self.ownership.require_entity(tx, actor, character_id, fence, character_version, alive=True)
        trader = self.ownership.require_entity(tx, actor, trader_id, fence, trader_version, alive=True)
        if character["kind"] != "CHARACTER" or trader["kind"] != "TRADER" or character["location"] != location or trader["location"] != location:
            raise Conflict("trade participants are outside this location")
        profile = self.profiles.get(json.loads(trader["state"]).get("trade_profile"))
        if not profile:
            raise Conflict("merchant has no configured trade profile")
        item = tx.execute("SELECT * FROM item WHERE id=?", (item_id,)).fetchone()
        source = ("TRADE", trader_id) if direction == "BUY" else ("PLAYER", character_id)
        if not item or (item["kind"], item["holder"], item["version"]) != (*source, item_version):
            raise Conflict("trade stock/ownership changed")
        entry = self.catalog.entry(item["section"])
        condition = int(finite(json.loads(item["state"]).get("condition", 1), 0, 1) * 10000)
        if direction == "SELL" and (entry["category"] not in profile["buy_categories"] or condition < profile["min_condition_bp"]):
            raise Conflict("merchant does not accept this item/condition")
        numerator = entry["price"] * item["quantity"] * condition * profile["sell_bp" if direction == "BUY" else "buy_bp"]
        # Integer money with conservative rounding; no float wallet arithmetic.
        price = max(1, (numerator + 99_999_999) // 100_000_000 if direction == "BUY" else numerator // 100_000_000)
        if price >= 2**63:
            raise Conflict("trade price exceeds wallet range")
        return character, trader, item, price

    def transact(self, actor, command_id, character_id, trader_id, item_id, location, fence, direction,
                 character_version, trader_version, item_version, price_limit, quote_only=False):
        for value in (character_id, trader_id, item_id):
            persistent_id(value)
        for value in (fence, character_version, trader_version, item_version):
            positive(value)
        identifier(location)
        if direction not in ("BUY", "SELL") or type(quote_only) is not bool:
            raise Invalid("invalid trade direction/quote")
        integer(price_limit, 0, 2**63-1, "trade price limit")
        payload = {"type": "trade", "character_id": character_id, "trader_id": trader_id, "item_id": item_id,
                   "location": location, "fence": fence, "direction": direction, "character_version": character_version,
                   "trader_version": trader_version, "item_version": item_version, "price_limit": price_limit, "quote_only": quote_only}
        def apply(tx):
            character, trader, item, price = self.inspect(tx, actor, character_id, trader_id, item_id, location, fence,
                                                         direction, character_version, trader_version, item_version)
            if quote_only:
                return {"price": price, "quantity": item["quantity"], "item_version": item_version,
                        "character_version": character_version, "trader_version": trader_version}
            if (direction == "BUY" and price > price_limit) or (direction == "SELL" and price < price_limit):
                raise Conflict("price is outside the accepted limit")
            states = [json.loads(row["state"]) for row in (character, trader)]
            wallets = [integer(state.get("money", 0), 0, 2**63-1, "wallet") for state in states]
            payer, recipient = (0,1) if direction == "BUY" else (1,0)
            if wallets[payer] < price or wallets[recipient] > 2**63-1-price:
                raise Conflict("payer funds/recipient wallet limit")
            target_kind, target_holder = ("PLAYER", character_id) if direction == "BUY" else ("TRADE", trader_id)
            self.ownership.check_capacity(tx, target_kind, target_holder)
            if direction == "BUY":
                limit = integer(states[0].get("carry_capacity_g", 50000), 0, 1_000_000, "carry capacity")
                weight = self.catalog.carry_weight(tx, character_id) + self.catalog.entry(item["section"])["weight_g"] * item["quantity"]
                if weight > limit:
                    raise Conflict("character carry capacity exceeded")
            wallets[payer] -= price
            wallets[recipient] += price
            for row, state, money in zip((character,trader), states, wallets):
                state["money"] = money
                encoded = canonical(state)
                tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (encoded,row["id"]))
                if row["kind"] == "CHARACTER":
                    tx.execute("UPDATE character SET state=? WHERE id=?", (encoded,row["id"]))
            tx.execute("UPDATE item SET kind=?,holder=?,version=version+1 WHERE id=?", (target_kind,target_holder,item_id))
            tx.execute("UPDATE container SET version=version+1 WHERE id IN (?,?)", (character_id,trader_id))
            event = self.store.event(tx, "item:" + item_id, "ItemTraded", {**payload,"price":price}, self.world.now())
            return {"item_id": item_id, "item_version": item_version+1, "character_version": character_version+1,
                    "trader_version": trader_version+1, "price": price, "character_money": wallets[0], "trader_money": wallets[1], "event": event}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.world.require_location(tx, actor, location, fence))
