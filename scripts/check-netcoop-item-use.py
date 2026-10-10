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

# Artefact containers and combinations (server actions; the client only asks).
lua.execute(r"""
released = {}
function alife_release(obj) released[#released + 1] = obj:section() end
conds = {}
function alife_create_item(sec, actor, data) made[#made + 1] = sec; conds[sec] = data and data.cond end
sections = {af_medusa = "ARTEFACT", lead_box = "x", af_medusa_lead_box = "x", af_iam = "x", bandage = "x", kit = "x", medkit = "x"}
ini_sys = {section_exist = function(_, s) return sections[s] ~= nil end,
           r_string_ex = function(_, s, k) return k == "class" and sections[s] or nil end}
itms_manager.itms_arty_container = {lead_box = true, af_iam = true}
itms_manager.item_combine = {bandage = {kit = "medkit"}}
function item(sec, cond) return {section = function() return sec end, condition = function() return cond or 1 end} end
""")
act = g.netcoop_item_use.container_action
made0 = len(made())
assert act("arty_pack", lua.eval('item("af_medusa", 0.7)'), lua.eval('item("lead_box")')) == ""
assert made()[-1] == "af_medusa_lead_box" and abs(g.conds["af_medusa_lead_box"] - 0.7) < 1e-9
assert list(g.released.values()) == ["af_medusa", "lead_box"]
assert act("arty_pack", lua.eval('item("af_medusa")'), lua.eval('item("af_iam")')) != ""   # no such packed section
assert act("arty_pack", lua.eval('item("bandage")'), lua.eval('item("lead_box")')) != ""   # not an artefact
assert act("arty_unpack", lua.eval('item("af_medusa_lead_box", 0.4)'), None) == ""
assert made()[-2:] == ["lead_box", "af_medusa"] and abs(g.conds["af_medusa"] - 0.4) < 1e-9 and g.ARTY_FROM_CONT
assert act("arty_unpack", lua.eval('item("lead_box")'), None) != ""                       # empty container
assert act("combine", lua.eval('item("bandage")'), lua.eval('item("kit")')) == "" and made()[-1] == "medkit"
assert act("combine", lua.eval('item("kit")'), lua.eval('item("bandage")')) != ""
assert act("arty_pack", lua.eval('item("af_medusa")'), None) is None                       # needs a target
assert len(made()) == made0 + 4

# Packages: all content (use_package) or GAMMA's random pick (use_package_random).
lua.execute(r"""
functors = {medkit_ai1 = "itms_manager.use_package", quest_package_1 = "itms_manager.use_package_random"}
content = {medkit_ai1 = "bandage, bandage, kit", quest_package_1 = "a1,a2,a3,a4,a5,a6,a7,a8"}
for _, s in ipairs({"medkit_ai1", "quest_package_1", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"}) do sections[s] = sections[s] or "x" end
local exist = ini_sys.section_exist
ini_sys.r_string_ex = function(_, s, k)
    if k == "use1_action_functor" then return functors[s] end
    return k == "class" and sections[s] == "ARTEFACT" and "ARTEFACT" or nil end
itms_manager.ini_manager.r_string_ex = function(_, sec, key) return content[key] end
""")
n0, r0 = len(made()), len(g.released)
assert act("package", lua.eval('item("medkit_ai1")'), None) == ""
assert made()[n0:] == ["bandage", "bandage", "kit"] and g.released[r0 + 1] == "medkit_ai1"
for seed in range(20):
    lua.execute(f"math.randomseed({seed})")
    n0 = len(made())
    assert act("package", lua.eval('item("quest_package_1")'), None) == ""
    got = made()[n0:]
    assert 2 <= len(got) <= 6 and set(got) <= {"a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"}, got
assert act("package", lua.eval('item("bandage")'), None) != ""
assert act("package", lua.eval('item("medkit_ai1")'), lua.eval('item("kit")')) is None

# Wiring: the server action and the client requests.
srv = (root / "scripts/netcoop-overlay/server/netcoop_server_compat.script").read_text(encoding="utf-8")
assert 'netcoop_item_use.container_action(action, item, target)' in srv
cli = (root / "scripts/netcoop-overlay/client/netcoop_client_compat.script").read_text(encoding="utf-8")
for request in ('"arty_pack")', '"combine")', '65535, "arty_unpack")', '65535, "package")', "install_server_containers()"):
    assert request in cli, request
print("netcoop item use: OK")
