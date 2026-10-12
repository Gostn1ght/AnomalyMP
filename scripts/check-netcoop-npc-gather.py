"""NPCs picking items up from the ground keep the same item (doc 43 L17).
Actual GAMMA xr_gather_items.gather_item with the actual netcoop_npc_loot
hook (Lua 5.1): a weapon the NPC changes to, an artefact it finds and an ammo
box are taken with their own IDs (npc:take_item), nothing is cloned, created
or released; GAMMA's artefact bookkeeping still runs. An item someone else
picked up meanwhile stays with them; an exe without take_item keeps GAMMA's
clone/create path."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

here = Path(__file__).resolve().parent
root = here / "netcoop-overlay"
gamma = here / "fixtures" / "npc-gather" / "xr_gather_items.script"  # GAMMA copy
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function printf() end
function netcoop_enabled() return true end
function netcoop_pure_client() return false end
function RegisterScriptCallback() end
function class(name) local env = getfenv(2); return function() env[name] = {} end end
property_evaluator, action_base = {}, {}

log = {}
objects = {}
function make(id, section, cls, parent)
  local o = {_id = id, _section = section, _cls = cls, _parent = parent, _alive = true}
  function o:id() return self._id end
  function o:name() return section .. id end
  function o:section() return self._section end
  function o:alive() return self._alive end
  function o:parent() return self._parent and objects[self._parent] end
  function o:get_artefact() return {FollowByPath = function() log[#log + 1] = "follow" .. id end} end
  function o:take_item(it)
    log[#log + 1] = "take " .. it._id
    it._parent = self._id
  end
  objects[id] = o
  return o
end
function se(o)
  if not o then return nil end
  return {id = o._id, parent_id = o._parent or 65535, cls = o._cls, section_name = function() return o._section end,
          clsid = function() return o._cls end}
end
function alife_object(id) return se(objects[id]) end
level = {object_by_id = function(id) return objects[id] end}
function vector() return {set = function(self) return self end} end
function IsArtefact(_, cls) return cls == "af" end
function IsWeapon(o) return o._cls == "wpn" end
next_id = 900
function alife_clone_weapon(s, section, parent) log[#log + 1] = "clone " .. s.id; return {id = 999} end
function alife_create_item(section, where, props) next_id = next_id + 1; log[#log + 1] = "create " .. section; return {id = next_id} end
function alife_release(s) log[#log + 1] = "release " .. s.id; objects[s.id] = nil; return true end
function ini_file()
  return {r_bool_ex = function(_, _, k) return k == "enable" or k == "use_xr_corpse_detection_loot_table" end,
          r_string_ex = function() return nil end, r_float_ex = function() return nil end}
end
utils_data = {collect_section = function() return {} end}
xr_corpse_detection = {lootable_table = {wpn_ak74 = true, af_medusa = true, ammo_5_45x39_fmj = true, bread = true}}
zone_took = {}
bind_anomaly_zone = {parent_zones_by_artefact_id = {}, artefact_ways_by_id = {}}
ui_options = {get = function() return false end}
stats = 0
game_statistics = {increment_npc_statistic = function() stats = stats + 1 end}
db = {actor = {}, storage = {}}
''')
mod = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            mod, (root / "server/netcoop_npc_loot.script").read_text(encoding="utf-8"))
gather = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            gather, gamma.read_text(encoding="cp1251"))
g.xr_gather_items = gather
gather.on_game_start()
mod.on_game_start()
make = lua.eval("make")


def pick(npc, item_id):
    lua.execute("log = {}")
    g.db.storage[npc._id] = lua.eval("{gather_items = {}}")
    g.db.storage[npc._id].gather_items.selected_id = item_id
    gather.gather_item(npc)
    return [g.log[i + 1] for i in range(len(g.log))]


npc = make(10, "stalker", "npc")
# a better weapon on the ground: the NPC takes that very weapon
make(50, "wpn_ak74", "wpn")
assert pick(npc, 50) == ["take 50"], g.log
assert g.objects[50]._parent == 10
# an artefact: same artefact, GAMMA's anomaly-field bookkeeping and stats still run
lua.execute("bind_anomaly_zone.parent_zones_by_artefact_id[51] = {on_artefact_take = function(_, a) zone_took[#zone_took + 1] = a._id end}")
make(51, "af_medusa", "af")
assert pick(npc, 51) == ["follow51", "take 51"], g.log
assert g.objects[51]._parent == 10 and g.zone_took[1] == 51 and g.stats == 1
# an ammo box: the same box (its real count), not a new default one
make(52, "ammo_5_45x39_fmj", "ammo")
assert pick(npc, 52) == ["take 52"], g.log
# picked up by someone else (a player) in the meantime: it stays with them
other = make(11, "stalker", "npc")
make(53, "bread", "food")
item = g.objects[53]
item._parent = 11
# GAMMA would release it from the other's inventory and give the NPC a copy
assert pick(npc, 53) == [], g.log
assert g.objects[53]._parent == 11
# an exe without take_item: GAMMA's clone / create+release, unchanged
lua.execute("objects[10].take_item = nil")
make(54, "wpn_ak74", "wpn")
assert pick(npc, 54) == ["clone 54"], g.log
make(55, "bread", "food")
assert pick(npc, 55) == ["create bread", "release 55"], g.log
# a dead NPC never takes
lua.execute("objects[10].take_item = objects[11].take_item; objects[10]._alive = false")
make(56, "bread", "food")
assert pick(npc, 56) == ["create bread", "release 56"], g.log
# only xr_gather_items is affected: the global helpers are GAMMA's
assert g.alife_create_item is not gather.alife_create_item and lua.eval("alife_clone_weapon ~= xr_gather_items.alife_clone_weapon")
print("PASS NPC ground pickup: weapon/artefact/ammo keep their IDs (take_item), GAMMA bookkeeping kept, fallback without take_item")
