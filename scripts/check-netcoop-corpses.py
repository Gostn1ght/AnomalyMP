"""Corpses disappear (owner 2026-10-06): the actual netcoop_corpses script."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
clock = 1000000
os = {time = function() return clock end}
tick = 0
function time_global() return tick end
function printf() end
state = {}
alife_storage_manager = {get_state = function() return state end}
objects, players, released, story = {}, {}, {}, {}
local function pos(x) return {x = x, distance_to_sqr = function(self, o) return (self.x - o.x)^2 end} end
function corpse(id, x) objects[id] = {position = pos(x), alive = function() return false end, clsid = function() return 1 end,
    m_game_vertex_id = 1} end
function alife() return {object = function(_, id) return objects[id] end, level_name = function() return "k00_marsh" end} end
function game_graph() return {vertex = function() return {level_id = function() return 1 end} end} end
level = {name = function() return "k00_marsh" end, object_by_id = function(id)
    if players[id] then return {position = function() return players[id] end} end end}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
function IsStalker() return true end
function IsMonster() return false end
function get_object_story_id(id) return story[id] end
safe_release_manager = {release = function(se) for id, o in pairs(objects) do if o == se then objects[id] = nil; released[#released + 1] = id end end end}
''')
g = lua.globals()
g.netcoop_corpses = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_corpses, (root / "scripts/netcoop-overlay/server/netcoop_corpses.script").read_text(encoding="ascii"))
lua.execute(r'''
local c = netcoop_corpses
corpse(10, 0); corpse(11, 500); corpse(12, 900); story[12] = "story_guy"
players[1] = {x = 5, distance_to_sqr = function(self, o) return (self.x - o.x)^2 end}
tick = 100000; c.update()                        -- first look: clocks start now
assert(#released == 0, "nothing removed at once")
clock = clock + 11 * 60; tick = tick + 31000; c.update()
assert(objects[10], "a corpse next to a player stays")
assert(not objects[11], "an old corpse far from players goes")
assert(objects[12], "a story corpse stays")
players[1] = nil; tick = tick + 31000; c.update()
assert(not objects[10], "it goes once the player left")
-- Over the cap the oldest go first, even if young.
for i = 100, 145 do corpse(i, 1000 + i); state.netcoop_corpses[i] = clock + i end -- death callbacks
tick = tick + 31000; c.update()
local left = 0 for id in pairs(objects) do left = left + 1 end
assert(left == 40 and objects[12] and not objects[100] and objects[145], "capped at 40, oldest first, story kept: " .. left)
''')
print("Corpses: kept next to players and for 10 min, then removed with their loot; cap 40 oldest first; story corpses stay PASS")
