"""Weapon/outfit parts with one authority (actual netcoop_weapon_parts on the
server and netcoop_weapon_parts_view on the client, Lua 5.1, the world and
GAMMA's functions stubbed). The server keeps parts in se storage and in the
cluster store by the item's uid: a new copy of the item (relog, another
server, a new id) gets the same parts; the client receives them, replaces
what it invented and reloads the jamming cache; the shooter's wear is
reported (only after the server's table arrived) and the server takes only
lower values, never a missing part or a higher one; maintenance, field strip
and installing a part run on the server and send the new table; only the
owner's items; GAMMA's menus send these actions."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

here = Path(__file__).resolve().parent
root = here / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function printf() end
game = {translate_string = function(id) return "<" .. id .. ">" end}
store = {}
function netcoop_store_read(b, k) return (store[b] or {})[k] or "" end
function netcoop_store_swap(b, k, old, new)
  store[b] = store[b] or {}
  if (store[b][k] or "") ~= old then return false end
  store[b][k] = new ~= "" and new or nil
  return true end
se = {}
function se_load_var(id, _, key) return se[id] and se[id][key] end
function se_save_var(id, _, key, v) se[id] = se[id] or {}; se[id][key] = v end
uids = {}
function netcoop_item_uid(id) return uids[id] or "" end
sent = {}
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = {id = id, ch = ch, data = data} end
objects = {}
function make(id, sec, parent)
  local o = {_id = id, _sec = sec, _parent = parent, _cond = 0.5}
  function o:id() return self._id end
  function o:section() return self._sec end
  function o:parent() return objects[self._parent] end
  function o:condition() return self._cond end
  function o:set_condition(c) self._cond = c end
  objects[id] = o
  return o
end
level = {object_by_id = function(id) return objects[id] end}
evaluated = 0
item_parts = {
  get_parts_con = function(obj, id, evaluate)
    local t = se_load_var(obj and obj:id() or id, nil, "parts")
    if not t and evaluate then evaluated = evaluated + 1; t = {prt_w_trigger = 80, prt_w_barrel = 90, prt_w_spring = 70}
      se_save_var(obj:id(), nil, "parts", t) end
    return t end,
  set_parts_con = function(id, data) se_save_var(id, nil, "parts", data) end,
  get_suitable_dtool = function() return nil end,
}
discharged = {}
utils_item = {discharge = function(o) discharged[#discharged + 1] = o:section() end}
kits = {clean = "cleaning_kit", repair = "repair_kit"}
zzzz_arti_jamming_repairs = {
  get_suitable_kit = function(obj, clean) return make(900 + (clean and 1 or 0), clean and kits.clean or kits.repair, 1) end,
  act_fieldstrip = function(id, part) local t = se_load_var(id, nil, "parts"); for k in pairs(t) do if (not part or k == part) and k ~= "prt_w_barrel" then t[k] = -1 end end
    item_parts.set_parts_con(id, t) end,
}
arti_jamming = {
  is_part = function(sec) return string.match(sec, "^prt_w_") ~= nil end,
  try_replace_part = function(wpn, t, part) local old = t[part:section()]; t[part:section()] = 95; part:set_condition(old / 100); item_parts.set_parts_con(wpn:id(), t) end,
}
''')

def load(name, path):
    t = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...), select(3, ...))), setmetatable(env,{__index=_G}))()",
                t, path.read_text(encoding="utf-8"), "@" + path.name)
    g[name] = t
    return t

srv = load("netcoop_weapon_parts", root / "server/netcoop_weapon_parts.script")
make = lua.eval("make")
actor = make(1, "actor", None)
other = make(2, "actor", None)
ak = make(10, "wpn_ak74", 1)
g.uids[10] = "777000111"

def last_sent():
    return g.sent[len(g.sent)]

# the server's table, kept by uid; sent to the owner
srv.command(1, "get 10")
assert g.evaluated == 1 and last_sent().ch == "wparts" and last_sent().data == "10|prt_w_barrel:90,prt_w_spring:70,prt_w_trigger:80"
assert g.store.wparts["777000111"] == "prt_w_barrel:90,prt_w_spring:70,prt_w_trigger:80"
# not the owner: nothing
n = len(g.sent); srv.command(2, "get 10"); assert len(g.sent) == n
# wear: only lower values, never a missing part, never higher
srv.command(1, "wear 10 prt_w_trigger:60,prt_w_spring:99,prt_w_barrel:-1,prt_w_fake:1")
t = g.se[10].parts
assert t.prt_w_trigger == 60 and t.prt_w_spring == 70 and t.prt_w_barrel == 90 and t.prt_w_fake is None
assert g.store.wparts["777000111"] == "prt_w_barrel:90,prt_w_spring:70,prt_w_trigger:60"
# a new copy of the same item (relog: new id, same uid) gets the same parts, not new ones
ak2 = make(11, "wpn_ak74", 1); g.uids[11] = "777000111"
srv.command(1, "get 11")
assert g.evaluated == 1 and g.se[11].parts.prt_w_trigger == 60
# maintenance: repair kit for a part under 60, cleaning kit 60..97; kit used up, +10% condition
lua.execute("se[11].parts.prt_w_spring = 50")
srv.command(1, "get 11")  # (store keeps 70 for spring: wear only lowers; set it through wear)
srv.command(1, "wear 11 prt_w_spring:50")
repair = make(901, "x", 1)
assert srv.action(1, ak2, make(500, "repair_kit", 1), "wpart_maint prt_w_spring 0") == ""
assert g.se[11].parts.prt_w_spring == 99 and list(g.discharged.values()) == ["repair_kit"] and abs(ak2._cond - 0.6) < 1e-6
assert srv.action(1, ak2, make(501, "repair_kit", 1), "wpart_maint prt_w_spring 0") == "<st_upgr_cant_do>"  # not worn
assert srv.action(1, ak2, make(502, "cleaning_kit", 1), "wpart_maint prt_w_trigger 1") == ""                # 60: clean
assert g.se[11].parts.prt_w_trigger == 99
assert srv.action(1, ak2, make(503, "bandage", 1), "wpart_maint prt_w_barrel 1") == "no kit"
assert last_sent().data.startswith("11|")
# field strip and part install run GAMMA's functions on the server's table
assert srv.action(1, ak2, None, "wpart_strip prt_w_trigger") == ""
assert g.se[11].parts.prt_w_trigger == -1 and "prt_w_trigger:-1" in g.store.wparts["777000111"]
part = make(600, "prt_w_trigger", 1); part._cond = 0.7
assert srv.action(1, ak2, part, "wpart_install") == "" and g.se[11].parts.prt_w_trigger == 95
assert srv.action(1, ak2, make(601, "bandage", 1), "wpart_install") == "this is not a part"
# routing on the server
compat = (root / "server/netcoop_server_compat.script").read_text(encoding="utf-8")
assert 'string.match(action, "^wpart_")' in compat and "netcoop_weapon_parts.action(actor_id, item, target, action)" in compat
assert 'cmd == "wparts"' in (root / "server/netanomaly_server.script").read_text(encoding="utf-8")
assert "netcoop_weapon_parts.ensure(obj)" in (root / "server/netcoop_workshop.script").read_text(encoding="utf-8")

# ---------------------------------------------------------------- client
lua.execute(r'''
tg = 0
function time_global() return tg end
commands, actions = {}, {}
function netcoop_command(c) commands[#commands + 1] = c end
function netcoop_item_action(k, i, t, a) actions[#actions + 1] = string.format("%d %d %d %s", k, i, t, a); return true end
function netcoop_pure_client() return true end
callbacks = {}
function RegisterScriptCallback(n, f) callbacks[n] = f end
cur = 10; resets = 0
arti_jamming.has_parts = function(o) return o:section() == "wpn_ak74" end
arti_jamming.current_id = function() return cur end
arti_jamming.reset_cgd = function() resets = resets + 1 end
utils_obj = {play_sound = function() end}
held = nil
db = {actor = {
  iterate_inventory = function(_, fn) fn(nil, objects[10]) end,
  object = function(_, sec) return make(700, sec, 1) end,
  active_item = function() return held end,
}}
se = {}
''')
view = load("netcoop_weapon_parts_view", root / "client/netcoop_weapon_parts_view.script")
view.on_game_start()
g.callbacks.actor_on_first_update()
assert g.commands[1] == "wparts get 10"
# invented table before the server's: GAMMA's own write is not reported
lua.execute("item_parts.set_parts_con(10, {prt_w_trigger = 1})")
g.tg += 5000; g.callbacks.actor_on_update()
assert len(g.commands) == 1
# the server's table replaces it and the jamming cache reloads
view.receive("10|prt_w_barrel:90,prt_w_spring:70,prt_w_trigger:60")
assert g.se[10].parts.prt_w_trigger == 60 and g.resets == 1 and view.synced[10]
# wear while firing (GAMMA's persist): reported, at most every 3 s
lua.execute("local t = se[10].parts; t.prt_w_trigger = 58; item_parts.set_parts_con(10, t)")
g.tg += 600; g.callbacks.actor_on_update()
assert g.commands[len(g.commands)] == "wparts wear 10 prt_w_barrel:90,prt_w_spring:70,prt_w_trigger:58"
lua.execute("local t = se[10].parts; t.prt_w_trigger = 57; item_parts.set_parts_con(10, t)")
g.tg += 600; g.callbacks.actor_on_update()
assert g.commands[len(g.commands)].endswith("trigger:58")
g.tg += 3000; g.callbacks.actor_on_update()
assert g.commands[len(g.commands)].endswith("trigger:57")
# GAMMA's menus go to the server
lua.execute("zzzz_arti_jamming_repairs.replace_part(10, 'prt_w_spring', 'repair_kit', false)")
assert g.actions[len(g.actions)] == "1 10 700 wpart_maint prt_w_spring 0"
lua.execute("zzzz_arti_jamming_repairs.act_fieldstrip(10, nil)")
assert g.actions[len(g.actions)] == "1 10 65535 wpart_strip all"
lua.execute("arti_jamming.try_replace_part(objects[10], {}, objects[600])")
assert g.actions[len(g.actions)] == "1 10 600 wpart_install"
# a weapon in hands without the server's table is asked for
lua.execute("make(12, 'wpn_ak74', 1); held = objects[12]")
g.tg += 20000; g.callbacks.actor_on_update()
assert "wparts get 12" in list(g.commands.values())
cc = (root / "client/netcoop_client_compat.script").read_text(encoding="utf-8")
assert 'channel == "wparts"' in cc and "netcoop_weapon_parts_view.receive(data)" in cc
src = (here.parent / "src/xrGame/netcoop_items.inc").read_text(encoding="utf-8", errors="replace")
assert "LPCSTR script_item_uid(u16 id)" in src
assert 'def("netcoop_item_uid", &netcoop::script_item_uid)' in (here.parent / "src/xrGame/level_script.cpp").read_text(encoding="utf-8", errors="replace")
print("Weapon parts: server authority by uid, wear only down, maintenance/strip/install on the server: PASS")
