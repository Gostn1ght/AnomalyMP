"""Item use effects on the server (actual netcoop_item_use, Lua 5.1): what GAMMA's
use scripts give back is made by the server for the player who used the item
- chocolate -> chocolate_p, bolts pack -> 20-30 bolts, listed medicine -> empty
syringe, multiuse_r keeps its use, money items add their amount (range or fixed);
nothing for other items, another (unbound) player, a dead player or the riches
wish. The engine calls it in CInventory::Eat after the use and before an emptied item is removed."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
inventory = (root / "src/xrGame/Inventory.cpp").read_text(encoding="latin-1")
eat = inventory[inventory.index("bool CInventory::Eat(PIItem pIItem)"):]
eat = eat[:eat.index("\nbool ", 10)]
# Where single-player runs the use scripts: after UseBy, before an emptied item is removed.
used = eat.index("netcoop::server_item_used(player, pIItem->object().ID()")
assert eat.index("if (!pItemToEat->UseBy(entity_alive))") < used < eat.index("if (pItemToEat->Empty())")
assert "netcoop::server_player_copy(player)" in eat[eat.index("else if (CActor* player"):used]
items = (root / "src/xrGame/netcoop_items.inc").read_text(encoding="utf-8")
hook = items[items.index("void server_item_used(CActor* actor, u16 item, LPCSTR section)"):]
hook = hook[:hook.index("\n}\n")]
assert "pure_client()" in hook and "ServerVictimScope scope(actor);" in hook and '"netcoop_item_use.used"' in hook

lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function printf() end
made, money = {}, 0
function alife_create_item(sec, actor) made[#made + 1] = sec end
syringe_lines = {"stimpack", "glucose", "not_an_item"}
itms_manager = {ini_manager = {
    section_exist = function() return true end,
    line_count = function() return #syringe_lines end,
    r_line_ex = function(_, s, i) return true, syringe_lines[i + 1], "" end}}
ini_sys = {section_exist = function(_, s) return s ~= "not_an_item" end}
ITM = {multiuse_r = {water_r = {"max_uses", 2}}, money = {money_100 = {"100"}, money_10_50 = {"10", "49"}}}
function IsItem(typ, sec) return ITM[typ] and ITM[typ][sec] or nil end
objects = {}
level = {object_by_id = function(id) return objects[id] end}
function player(id)
    local a = {alive_ = true, wish = false}
    function a:id() return id end
    function a:alive() return self.alive_ end
    function a:has_info(name) return name == "actor_made_wish_for_riches" and self.wish end
    function a:give_money(n) money = money + n end
    return a
end
p = player(5); db = {actor = p}
''')
g.netcoop_item_use = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_item_use, (root / "scripts/netcoop-overlay/server/netcoop_item_use.script").read_text(encoding="utf-8"))
use = g.netcoop_item_use.used
made = lambda: list(g.made.values())

use(5, 100, "chocolate"); assert made() == ["chocolate_p"]
use(5, 101, "stimpack"); assert made()[-1] == "e_syringe"
use(5, 102, "bandage"); assert len(made()) == 2
use(5, 103, "bolts_pack"); bolts = made()[2:]
assert 20 <= len(bolts) <= 30 and set(bolts) == {"bolt"}
lua.execute('''w = {uses = 1}
function w:get_remaining_uses() return self.uses end
function w:get_max_uses() return 2 end
function w:set_remaining_uses(n) self.uses = n end
objects[104] = w''')
use(5, 104, "water_r"); assert g.w.uses == 2
use(5, 104, "water_r"); assert g.w.uses == 2  # never above max
use(5, 105, "money_100"); assert g.money == 100
use(5, 106, "money_10_50"); assert 110 <= g.money <= 149
# Not this player's context, dead, or the wish for riches: nothing.
n, m = len(made()), g.money
use(6, 100, "chocolate")
lua.execute("p.alive_ = false"); use(5, 100, "money_100")
lua.execute("p.alive_ = true; p.wish = true"); use(5, 100, "chocolate")
assert len(made()) == n and g.money == m
print("netcoop item use: OK")
