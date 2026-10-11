"""Workshop on the server (actual netcoop_workshop and GAMMA's actual crafting
code: ui_workshop + zz_ui_workshop_keep_crafting_window_open +
zzzzzz_ui_workshop_nearby_stashes + craft_use_low_cond +
zzzzzz_craft_use_low_cond_nearby_stashes, from scripts/fixtures/workshop;
Lua 5.1, the world stubbed). The server rebuilds the recipe and the toolkit
state itself and runs GAMMA's UpdateItem/Craft headless for the player:
components from the inventory and from a stash in range are used up, belt
artefacts are not, the result is created; missing components, a missing
toolkit or an unknown recipe change nothing; a recipe book teaches the
recipe once (kept with the character, sent to the client) and is used up;
only a toolkit, a mechanic's vise or a furniture workshop is a workshop.
Disassembly runs GAMMA's leaf for the item and the tool. The client sends
"craft <type> <index>" from the workshop that opened the window,
"disassemble" for GAMMA's disassembly leaves, "recipe_read" for books, and
unlocks the recipes the server sends."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

here = Path(__file__).resolve().parent
root = here / "netcoop-overlay"
gamma = here / "fixtures/workshop"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function printf() end
function printe() end
strformat = string.format
function class(name)
    local env = getfenv(2)
    return function(base)
        local c = {}
        c.__index = c
        setmetatable(c, {__index = base})
        env[name] = c
    end
end
CUIScriptWnd, CUIListBoxItem = {}, {}
function str_explode(s, sep)
    local out = {}
    for part in string.gmatch(s, "([^" .. sep .. "]+)") do out[#out + 1] = (part:gsub("^%s+", ""):gsub("%s+$", "")) end
    return out
end
function GetARGB() return 0 end
utils_xml = {get_color = function() return "" end, set_icon = function() error("UI icon used on the server") end}
utils_obj = {play_sound = function() error("UI sound on the server") end}
ui_item = {get_sec_name = function(s) return s end}
game = {translate_string = function(id) return "<" .. id .. ">" end}
game_achievements = {has_achievement = function() return false end}
stats = {}
game_statistics = {increment_statistic = function(n) stats[n] = (stats[n] or 0) + 1 end}
function CreateTimeEvent() error("time event from the headless window") end
function random_number(a) return a end
function spairs(t, f)
    local keys = {}
    for k in pairs(t) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return f(t, a, b) end)
    local i = 0
    return function() i = i + 1; if keys[i] then return keys[i], t[keys[i]] end end
end
clsid = {inventory_box_s = 7}
-- world
objects, next_id = {}, 100
ACTOR = 0
function make(sec, parent, extra)
    next_id = next_id + 1
    local o = {_id = next_id, _sec = sec, _parent = parent, _cond = 1}
    for k, v in pairs(extra or {}) do o[k] = v end
    function o:id() return self._id end
    function o:section() return self._sec end
    function o:condition() return self._cond end
    function o:name() return self._name or (self._sec .. self._id) end
    function o:clsid() return self._clsid or 1 end
    function o:get_remaining_uses() return 1 end
    function o:position() return self._pos or {x = 0, y = 0, z = 0} end
    function o:iterate_inventory_box(fn, arg)
        for _, it in pairs(objects) do if it._parent == self._id then fn(arg, it) end end
    end
    objects[o._id] = o
    return o
end
belt = {}
actor = {_id = ACTOR}
function actor:id() return 0 end
function actor:iterate_inventory(fn, arg)
    local list = {}
    for _, it in pairs(objects) do if it._parent == ACTOR then list[#list + 1] = it end end
    table.sort(list, function(a, b) return a._id < b._id end)
    for _, it in ipairs(list) do fn(arg, it) end
end
function actor:iterate_belt(fn) for _, it in ipairs(belt) do fn(actor, it) end end
infos = {}
function actor:has_info(i) return infos[i] or false end
function actor:position() return {x = 0, y = 0, z = 0} end
db = {actor = actor, storage = {}}
level = {object_by_id = function(id) if id == 0 then return actor end return objects[id] end}
get_object_by_id = level.object_by_id
function distance_between_safe(a, b) local p = b:position(); return math.sqrt(p.x * p.x + p.z * p.z) end
function alife_release_id(id) objects[id] = nil end
function alife_release(obj) objects[obj:id()] = nil end
created = {}
function alife_create_item(sec, owner, t)
    local o = make(sec, owner:id(), {})
    if t and t.cond then o._cond = t.cond end
    created[#created + 1] = sec
    return o
end
storage = {}
alife_storage_manager = {get_state = function() return storage end}
SECTIONS = {itm_basickit = "tool", itm_advancedkit = "tool", itm_expertkit = "tool", itm_drugkit = "tool", itm_ammokit = "tool",
    itm_artefactskit = "tool", prt_i_fabrics = "part", prt_i_scrap = "part", bandage = "item", medkit = "item",
    af_medusa = "arty", recipe_basic_1 = "recipe", kolbasa = "item", wpn_pm = "weapon"}
function IsItem(kind, sec, obj)
    sec = sec or (obj and obj:section())
    if kind == "recipe" then return SECTIONS[sec] == "recipe" end
    return false
end
function IsWeapon(o) return SECTIONS[o:section()] == "weapon" end
function IsOutfit() return false end
function IsHeadgear() return false end
function SYS_GetParam(_, sec, key)
    if key == "kind" then return SECTIONS[sec] == "arty" and "i_arty" or "i_part" end
end
utils_item = {is_degradable = function() return false end, discharge = function(o) objects[o:id()] = nil end}
functors = {itm_basickit = "workshop_tool.start_workshop_basic", itm_advancedkit = "workshop_tool.start_workshop_advanced"}
ini_sys = {
    section_exist = function(_, s) return SECTIONS[s] ~= nil end,
    r_string_ex = function(_, s, k) if k == "use1_action_functor" then return functors[s] end end,
    r_float_ex = function() return nil end,
}
-- craft.ltx: [1] title, x_<result> = tool, recipe, comp, n, comp, n
craft_lines = {
    {"title", "st_craft_medical"},
    {"x_bandage", "1,recipe_basic_0,prt_i_fabrics,2,prt_i_scrap,1"},
    {"x_medkit", "1,recipe_basic_1,prt_i_fabrics,1,prt_i_scrap,1"},
    {"x_kolbasa", "2,recipe_basic_0,prt_i_scrap,1,prt_i_fabrics,1"},
}
ini_craft = {
    section_exist = function(_, s) return s == "1" end,
    line_count = function() return #craft_lines end,
    r_line = function(_, s, i) local l = craft_lines[i + 1]; return true, l[1], l[2] end,
}
itms_manager = {ini_craft = ini_craft, ini_manager = {r_string_ex = function() return nil end}}
function parse_list(ini, sec, key) return {"mech_" .. key} end
sent = {}
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = ch .. "|" .. data end
ui_mcm = nil
''')

def load(table_name, path):
    t = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...), select(3, ...))), setmetatable(env,{__index=_G}))()",
                t, path.read_text(encoding="utf-8"), "@" + path.name)
    g[table_name] = t
    return t

ws = load("ui_workshop", gamma / "ui_workshop.lua")
load("zz_ui_workshop_keep_crafting_window_open", gamma / "zz_ui_workshop_keep_crafting_window_open.lua")
nearby = load("zzzzzz_ui_workshop_nearby_stashes", gamma / "zzzzzz_ui_workshop_nearby_stashes.lua")
low = load("craft_use_low_cond", gamma / "craft_use_low_cond.lua")
low2 = load("zzzzzz_craft_use_low_cond_nearby_stashes", gamma / "zzzzzz_craft_use_low_cond_nearby_stashes.lua")
lua.execute("function RegisterScriptCallback() end")
for m in (nearby, low, low2):
    m.on_game_start()
server = load("netcoop_workshop", root / "server/netcoop_workshop.script")

def inv():
    return sorted(o._sec for o in g.objects.values() if o._parent == 0)

def item(sec, parent=0, **kw):
    return lua.eval("make")(sec, parent, lua.table_from(kw))

kit = item("itm_basickit")
item("prt_i_fabrics"); item("prt_i_fabrics"); item("prt_i_fabrics")
item("prt_i_scrap")
arty = item("af_medusa"); g.belt[1] = arty

# 1. a default recipe from a toolkit: components used up, result made
assert server.craft(0, 1, kit, "craft 1 1") == ""
assert inv() == ["af_medusa", "bandage", "itm_basickit", "prt_i_fabrics"], inv()
assert g.stats["items_crafted"] == 1
# 2. not enough components: nothing changes
before = inv()
assert server.craft(0, 1, kit, "craft 1 1") == "<craft_warning_4>"
assert inv() == before
# 3. components in a stash within range are used (the player's own stash)
stash = item("stash_box", 9999, _clsid=7, _pos=lua.table_from({"x": 3, "y": 0, "z": 4}))
lua.execute(f"storage.player_created_stashes = {{[{stash._id}] = true}}")
item("prt_i_fabrics", stash._id); item("prt_i_scrap", stash._id)
assert server.craft(0, 1, kit, "craft 1 1") == ""
assert inv().count("bandage") == 2 and "prt_i_fabrics" not in inv(), inv()
assert not any(o._parent == stash._id for o in g.objects.values())
assert g.objects[arty._id]            # the belt artefact is never an ingredient
# 4. an unknown recipe, then the book teaches it once
item("prt_i_fabrics"); item("prt_i_scrap")
r = server.craft(0, 1, kit, "craft 1 2"); assert r == "<craft_warning_2>", r
book = item("recipe_basic_1")
assert server.read_recipe(0, book) == ""
assert book._id not in g.objects and g.sent[len(g.sent)] == "recipes|recipe_basic_1"
assert g.db.storage[0].pstor.netcoop_recipes == "recipe_basic_1"
book2 = item("recipe_basic_1")
assert server.read_recipe(0, book2) == "<st_recipe_is_known>" and book2._id in g.objects
assert server.craft(0, 1, kit, "craft 1 2") == ""
assert "medkit" in inv()
server.command(0, "get")
assert g.sent[len(g.sent)] == "recipes|recipe_basic_1"
# 5. a recipe for the advanced toolkit with only the basic one: no
item("prt_i_scrap"); item("prt_i_fabrics")
assert server.craft(0, 1, kit, "craft 1 3") == "<craft_warning_3>"
assert "kolbasa" not in inv() and "prt_i_scrap" in inv()
adv = item("itm_advancedkit")
assert server.craft(0, 1, adv, "craft 1 3") == ""
assert "kolbasa" in inv()
# 6. only workshops; bad requests
assert server.craft(0, 1, item("prt_i_scrap"), "craft 1 1") == "this item is not a workshop"
assert server.craft(0, 2, stash, "craft 1 1") == "this is not a workshop"
lua.execute(f"storage.workshop_stashes = {{[1] = {stash._id}}}")
assert server.craft(0, 2, stash, "craft 9 9") == "no such recipe"
assert server.craft(0, 1, kit, "craft x") == "bad recipe"
# a mechanic's vise: access from bind_awr, tiers from the player's infos
vise = item("physic_object", 9999, _name="awr_tiski_bar")
lua.execute("bind_awr = {access = function(o) return o:name() == 'awr_tiski_bar' end}")
assert server.craft(0, 2, vise, "craft 1 9") == "no such recipe"
lua.execute("bind_awr.access = function() return false end")
assert server.craft(0, 2, vise, "craft 1 1") == "the mechanic has not given you access"

# 7. disassembly: GAMMA's leaf for the item kind, after the tool check
lua.execute("""
dis = {}
item_parts = {is_suitable_dtool = function(o, t) return t:section() == 'itm_basickit' end,
  disassembly_item = function(o, t) dis[#dis + 1] = 'item ' .. o:section() end,
  disassembly_weapon = function(o, t) dis[#dis + 1] = 'weapon ' .. o:section() end,
  disassembly_outfit = function(o, t) dis[#dis + 1] = 'outfit ' .. o:section() end}
""")
pm = item("wpn_pm")
assert server.disassemble(pm, kit) == "" and g.dis[1] == "weapon wpn_pm"
assert server.disassemble(pm, adv) == "<st_news_dis_items>" and len(g.dis) == 1

# 8. server routing (netcoop_server_compat.item_action) and the command
compat = (root / "server/netcoop_server_compat.script").read_text(encoding="utf-8")
assert 'string.match(action, "^craft %d+ %d+$") and not target' in compat
assert "netcoop_workshop.disassemble(item, target)" in compat and "netcoop_workshop.read_recipe(actor_id, item)" in compat
assert 'cmd == "recipes"' in (root / "server/netanomaly_server.script").read_text(encoding="utf-8")

# ---------------------------------------------------------------- client
lua.execute(r'''
actions = {}
function netcoop_item_action(kind, id, target, action) actions[#actions + 1] = string.format("%d %d %d %s", kind, id, target, action); return true end
commands = {}
function netcoop_command(c) commands[#commands + 1] = c end
function netcoop_pure_client() return true end
callbacks = {}
function RegisterScriptCallback(n, f) callbacks[n] = f end
unlocked, interactions = {}, {}
ui_pda_encyclopedia_tab = {is_unlocked_note = function(n) return unlocked[n] or false end}
function SendScriptCallback(n, kind, _, sec) interactions[#interactions + 1] = kind .. " " .. sec; unlocked["encyclopedia__notes_" .. sec] = true end
workshop_tool = {start_workshop_basic = function(obj) opened = "basic" end}
ui_furniture_workshop = {OpenWorkshop = function(id) opened = "furniture" end}
viewed = {}
item_recipe = {start = function(sec) viewed[#viewed + 1] = sec end}
actor_menu = {set_msg = function() end}
actor_effects = {play_item_fx = function() end}
function get_hud() return nil end
item_parts = {disassembly_item = function() error("client must not disassemble") end,
  disassembly_weapon = function() error("client must not disassemble") end,
  disassembly_outfit = function() error("client must not disassemble") end}
''')
view = load("netcoop_workshop_view", root / "client/netcoop_workshop_view.script")
view.on_game_start()
g.callbacks.actor_on_first_update()
assert g.commands[1] == "recipes get"
g.workshop_tool.start_workshop_basic(kit)
assert g.opened == "basic" and view.opened_from.kind == 1 and view.opened_from.id == kit._id
win = lua.eval("{craft_allow_r = true, last_type = 1, selected_index = 2, btn_craft = {Enable = function() end}}")
g.ui_workshop.UIWorkshopCraft.Craft(win)
assert g.actions[1] == f"1 {kit._id} 65535 craft 1 2", g.actions[1]
g.ui_furniture_workshop.OpenWorkshop(stash._id)
g.ui_workshop.UIWorkshopCraft.Craft(win)
assert g.actions[2] == f"2 {stash._id} 65535 craft 1 2"
g.callbacks.physic_object_on_use_callback(vise, g.actor)
g.ui_workshop.UIWorkshopCraft.Craft(win)
assert g.actions[3] == f"2 {vise._id} 65535 craft 1 2"
g.item_parts.disassembly_weapon(pm, kit)
assert g.actions[4] == f"1 {pm._id} {kit._id} disassemble"
book3 = item("recipe_basic_1")
g.item_recipe.func_recipe(book3)
assert g.actions[5] == f"1 {book3._id} 65535 recipe_read" and g.viewed[1] == "recipe_basic_1"
view.receive_recipes("recipe_basic_1,recipe_basic_1")
assert list(g.interactions.values()) == ["notes recipe_basic_1"]
g.item_recipe.func_recipe(book3)                   # known now: no request
assert len(g.actions) == 5
cc = (root / "client/netcoop_client_compat.script").read_text(encoding="utf-8")
assert 'channel == "recipes"' in cc and "netcoop_workshop_view.receive_recipes(data)" in cc
for lang in ("rus", "eng"):
    table = (root / f"client/configs/text/{lang}/st_netcoop.xml").read_bytes().decode("cp1251")
    assert 'id="st_netcoop_workshop_unknown"' in table, lang
print("Workshop on the server: GAMMA craft headless, stashes, toolkits, recipes from books, disassembly: PASS")
