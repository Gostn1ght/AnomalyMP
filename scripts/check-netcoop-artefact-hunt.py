"""NPCs search for artefacts offline (doc 43 L08). Actual netcoop_artefacts
with the actual netcoop_loot_policy generator (Lua 5.1): an offline squad of
an artefact-hunting community staying at its smart terrain (GAMMA resets
current_action on load: by position) takes an
offline artefact within 80 m into its best hunter's inventory with the same
ID (alife():netcoop_take_offline). The chance follows rank, detector and the
artefact's danger; online/moving/non-hunting squads, far, online, carried,
quest and other-map artefacts are left alone; the rolls do not depend on
when they run; one look per game hour, two finds per look; a field coming
online forgets artefacts taken from it."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function printf() end
local V = {}
V.__index = V
function vec(x, z) return setmetatable({x = x, y = 0, z = z}, V) end
function V:distance_to(o) return math.sqrt((self.x - o.x) ^ 2 + (self.z - o.z) ^ 2) end

objects, takes = {}, {}
function make(id, t)
  t.id = id
  t.parent_id = t.parent_id or 65535
  t.m_game_vertex_id = t.gv or 1
  t.position = t.position or vec(0, 0)
  t.children = t.children or {}
  function t:section_name() return self.section end
  function t:name() return self.section .. self.id end
  function t:clsid() return self.cls end
  function t:alive() return self.dead ~= true end
  objects[id] = t
  return t
end
function alife_object(id) return objects[id] end
sim = {}
function sim:actor() return objects[0] end
function sim:iterate_objects(f) for id = 0, 2000 do local o = objects[id]; if o and f(o) then return end end end
function sim:get_children(se)
  local i = 0
  return function() i = i + 1; return se.children[i] end
end
function sim:netcoop_take_offline(who, what)
  local o, w = objects[what], objects[who]
  if not o or not w or o.online or w.online or o.parent_id ~= 65535 then return false end
  o.parent_id = who
  table.insert(w.children, what)
  takes[#takes + 1] = what
  return true
end
function alife() return sim end
-- level of a game vertex: vertices 1..9 are this map, 10+ another one
function game_graph() return {vertex = function(_, gv) return {level_id = function() return gv < 10 and 1 or 2 end} end} end
function IsArtefact(_, cls) return cls == "af" end
ini_sys = {r_float_ex = function(_, sec, key) return ({af_cheap = 1000, af_rare = 40000})[sec] or 0 end,
           r_bool_ex = function(_, sec, key) return sec == "af_quest" and key == "quest_item" end}
function ini_file() return {} end
utils_data = {collect_section = function() return {stalker = true, dolg = true} end}
ranks = {get_se_obj_rank_name = function(se) return se.rank end}
function get_object_story_id(id) return objects[id] and objects[id].story end
storage = {}
alife_storage_manager = {get_state = function() return storage end}
hours = 100
local T = {}
T.__index = T
function T:set() end
function T:diffSec() return hours * 3600 end
game = {CTime = function() return setmetatable({}, T) end, get_game_time = function() return setmetatable({}, T) end}
SIMBOARD = {smarts = {}}
function squad(id, smart_id, community, members, extra)
  local s = make(id, {section = "squad", cls = "squad", current_action = 0, smart_id = smart_id,
                      position = vec(objects[smart_id].position.x + 20, objects[smart_id].position.z),
                      community = community, members = members})
  for k, v in pairs(extra or {}) do s[k] = v end
  function s:get_squad_community() return self.community end
  function s:squad_members()
    local i = 0
    return function() i = i + 1; local m = self.members[i]; return m and {id = m} end
  end
  SIMBOARD.smarts[smart_id].squads[id] = true
  return s
end
function smart(id, x, z, gv)
  local s = make(id, {section = "smart", cls = "smart", position = vec(x, z), gv = gv})
  SIMBOARD.smarts[id] = {smrt = s, squads = {}}
  return s
end
''')
policy = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            policy, (root / "server/netcoop_loot_policy.script").read_text(encoding="utf-8"))
g.netcoop_loot_policy = policy
g.storage.netcoop_loot_policy = lua.eval("{seed = 777}")
mod = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            mod, (root / "server/netcoop_artefacts.script").read_text(encoding="utf-8"))
make = lua.eval("make")
T = lambda **kw: lua.table_from(kw)
make(0, T(section="actor", cls="actor"))

# hunters: rank x detector
make(500, T(section="detector_advanced", cls="dev"))
make(501, T(section="detector_scientific", cls="dev"))
novice = make(10, T(section="stalker", cls="npc", rank="novice"))
legend = make(11, T(section="stalker", cls="npc", rank="legend", children=lua.table(501)))
pro = make(12, T(section="stalker", cls="npc", rank="experienced", children=lua.table(500)))
assert abs(mod.hunter_skill(novice) - 0.6 * 0.3) < 1e-9
assert abs(mod.hunter_skill(legend) - 1.6 * 1.7) < 1e-9
assert abs(mod.hunter_skill(pro) - 1.3) < 1e-9
legend.dead = True
assert mod.hunter_skill(legend) == 0
legend.dead = False

# a squad of stalkers resting at a smart terrain 30 m from a cheap artefact
lua.execute("smart(100, 0, 0, 1)")
lua.execute("squad(200, 100, 'stalker', {12, 10})")
af = make(300, T(section="af_cheap", cls="af", position=g.vec(30, 0)))

def chance_over(hours_count, start=1000):
    found = 0
    for h in range(start, start + hours_count):
        af.parent_id = 65535
        lua.execute("takes = {}; objects[12].children = {500}")
        found += mod.hunt_look(h)
    return found / hours_count

rate = chance_over(600)
expected = 0.10 * 1.3 * (1 - 1000 / 50000)
assert abs(rate - expected) < 0.04, (rate, expected)
# the same hours give the same finds (restart / other calls to math.random in between)
first = [mod.hunt_look(h) or 0 for h in range(2000, 2040) if not af.__setitem__("parent_id", 65535)]
math_noise = [g.math.random() for _ in range(17)]
again = [mod.hunt_look(h) or 0 for h in range(2000, 2040) if not af.__setitem__("parent_id", 65535)]
assert first == again and sum(first) > 0, (first, again)
# the hunter really holds the very artefact
af.parent_id = 65535
for h in range(3000, 3400):
    if mod.hunt_look(h):
        break
assert af.parent_id == 12 and 300 in list(g.objects[12].children.values())

def never(desc, setup, undo):
    lua.execute(setup)
    af.parent_id = 65535
    hits = sum(mod.hunt_look(h) for h in range(5000, 5300))
    lua.execute(undo)
    assert hits == 0, desc

never("online squad", "objects[200].online = true", "objects[200].online = nil")
never("squad away from its smart", "objects[200].position = vec(61, 0)", "objects[200].position = vec(20, 0)")
never("squad sent elsewhere", "objects[200].assigned_target_id = 999", "objects[200].assigned_target_id = nil")
never("not a hunting community", "objects[200].community = 'zombied'", "objects[200].community = 'stalker'")
never("story squad", "objects[200].story = 'x'", "objects[200].story = nil")
never("hunter online", "objects[12].online = true; objects[10].online = true", "objects[12].online = nil; objects[10].online = nil")
never("artefact online", "objects[300].online = true", "objects[300].online = nil")
never("artefact 81 m away", "objects[300].position = vec(81, 0)", "objects[300].position = vec(30, 0)")
never("quest artefact", "objects[300].section = 'af_quest'", "objects[300].section = 'af_cheap'")
never("artefact on another map", "objects[300].m_game_vertex_id = 12", "objects[300].m_game_vertex_id = 1")
lua.execute("objects[300].parent_id = 77")
assert sum(mod.hunt_look(h) for h in range(5000, 5300)) == 0  # in someone's inventory

# a rare artefact lies in a worse anomaly: fewer finds than a cheap one
lua.execute("objects[300].section = 'af_rare'")
rare = chance_over(600, 7000)
lua.execute("objects[300].section = 'af_cheap'")
assert rare < rate * 0.6, (rare, rate)

# at most two finds per look
for i in range(8):
    make(400 + i, T(section="af_cheap", cls="af", position=g.vec(10 + i, 0)))
lua.execute("objects[200].members = {11}")  # the legend: high chance
best = max(mod.hunt_look(h) for h in range(8000, 8100) if not [setattr(g.objects[400 + i], "parent_id", 65535) for i in range(8)] is None)
assert best == 2, best

# one look per game hour, remembered with the world
g.hours = 50
lua.execute("takes = {}")
mod.hunt_update(); mod.hunt_update()
assert g.storage.netcoop_af_hunt.hour == 50
g.hours = 50.9
mod.hunt_update()
assert g.storage.netcoop_af_hunt.hour == 50

# a field coming online forgets what left it (taken by an NPC or released)
lua.execute('''
forgot = {}
zone = {artefact_ways_by_id = {[300] = "way", [401] = "way", [999] = "way"}}
function zone.on_artefact_take(self, obj) forgot[#forgot + 1] = obj.id end
objects[300].parent_id = 12; objects[401].parent_id = 65535
''')
assert mod.forget_taken(g.zone) == 2
assert sorted(g.forgot.values()) == [300, 999]
print("PASS offline artefact hunt: rank/detector/danger chance, same ID into the hunter, eligibility, deterministic, 1/hour, 2/look, field forgets taken")
