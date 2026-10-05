"""NPC transit between location servers: the actual netcoop_transit.script in
two Lua VMs (Great Swamp and Cordon) with a shared record store."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/netcoop-overlay/server/netcoop_transit.script").read_text()
records = {}

WORLD = r'''
LEVEL = ...
local levels = {[1] = "k00_marsh", [2] = "l01_escape"}
objects, released, created, logs = {}, {}, {}, {}
local next_id = 100
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
function time_global() return 0 end
function command_line() return "" end
clsid = {level_changer_s = 50, level_changer = 51, script_stalker = 1, stalker = 2, actor = 3, script_actor = 4}
function IsStalker(o, c) return c == 1 end
function game_graph() return {vertex = function(_, gv) return {level_id = function() return gv end} end} end
local sim = {object = function(_, id) return objects[id] end, level_name = function(_, id) return levels[id] end}
function alife() return sim end
level = {name = function() return LEVEL end, object_by_id = function(id) return players[id] end}
players = {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
ini_sys = {section_exist = function(_, s) return s ~= "missing_item" end}
local function new(section, cls, gv, parent, fields)
	next_id = next_id + 1
	local o = {id = next_id, m_game_vertex_id = gv, parent_id = parent or 65535, position = {x = 0},
		m_level_vertex_id = 7, cls = cls, sec = section, alive_ = true, data = fields or {}}
	function o:clsid() return self.cls end
	function o:section_name() return self.sec end
	function o:alive() return self.alive_ end
	objects[o.id] = o
	return o
end
function spawn(section, cls, gv, parent, fields) return new(section, cls, gv, parent, fields) end
utils_stpk = {
	get_level_changer_data = function(se) return {dest_level_name = se.dest} end,
	get_stalker_data = function(se) local t = {} for k, v in pairs(se.data) do t[k] = v end return t end,
	set_stalker_data = function(t, se) se.data = t end,
	get_object_data = function(se) local t = {} for k, v in pairs(se.data) do t[k] = v end return t end,
	set_object_data = function(t, se) se.data = t end,
}
function alife_release(se) released[#released + 1] = se.id; objects[se.id] = nil end
function alife_release_id(id) released[#released + 1] = id; objects[id] = nil end
function get_object_story_id(id) return objects[id] and objects[id].story end
function make_squad(section, gv, members)
	local squad = new(section, 9, gv)
	squad.members = members or {}
	function squad:squad_members()
		local i = 0
		return function() i = i + 1; local id = self.members[i]; return id and {id = id} end
	end
	function squad:get_script_target() return self.script_target end
	function squad:add_squad_member(section, pos, lvid, gvid)
		local npc = new(section, 1, gvid, nil, {game_vertex_id = gvid, character_name = "random", money = 5, smart_terrain_id = 77})
		new("starter_bread", 30, gvid, npc.id, {condition = 1}) -- profile supplies
		self.members[#self.members + 1] = npc.id
		return npc.id
	end
	function squad:set_squad_relation() self.relation = true end
	SIMBOARD.squads[squad.id] = squad
	return squad
end
SIMBOARD = {squads = {}, assign_squad_to_smart = function() end}
function alife_create(section, pos, lvid, gvid) local s = make_squad(section, gvid, {}); created[#created + 1] = s; return s end
function alife_create_item(section, owner) return new(section, 30, owner.m_game_vertex_id, owner.id, {game_vertex_id = owner.m_game_vertex_id}) end
'''

def vm(level, gv):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(WORLD, level)
    g = lua.globals()
    g.netcoop_cluster_maps = lambda: "l01_escape" if level == "k00_marsh" else "k00_marsh"
    def put(target, text):
        records.setdefault(target, []).append(text)
        return True
    def take(target):
        queue = records.get(target) or []
        return queue.pop(0) if queue else ""
    g.netcoop_transit_put = put
    g.netcoop_transit_take = take
    lua.execute(source)
    return lua

marsh = vm("k00_marsh", 1)
marsh.execute(r'''
changer = spawn("lc", 50, 1); changer.dest = "l01_escape"
local a = spawn("stalker_a", 1, 1, nil, {character_name = "Vasya Folk", money = 1200, rank = 300, health = 0.7, game_vertex_id = 1, story_id = -1})
local b = spawn("stalker_b", 1, 1, nil, {character_name = "Petro", money = 50, rank = 10, health = 1})
spawn("wpn_ak74", 30, 1, a.id, {condition = 0.62, ammo_elapsed = 17, game_vertex_id = 1, story_id = 5})
spawn("missing_item", 30, 1, b.id, {})
squad = make_squad("stalker_sim_squad", 1, {a.id, b.id})
story = make_squad("story_squad", 1, {spawn("s", 1, 1).id}); story.story = 12
assert(depart(function() return 0 end) == "left")
assert(objects[squad.id] == nil and objects[a.id] == nil and objects[b.id] == nil, "the squad left this map")
assert(objects[story.id] ~= nil, "story squads stay")
''')
assert len(records.get("l01_escape", [])) == 1, "one record for Cordon"

escape = vm("l01_escape", 2)
escape.execute(r'''
back = spawn("lc", 50, 2); back.dest = "k00_marsh"
assert(arrive() == "arrived")
local squad = created[1]
assert(squad and squad.sec == "stalker_sim_squad" and squad.m_game_vertex_id == 2 and squad.relation)
assert(#squad.members == 2)
local a = objects[squad.members[1]]
assert(a.data.character_name == "Vasya Folk" and a.data.money == 1200 and a.data.rank == 300 and a.data.health == 0.7)
assert(a.data.smart_terrain_id == 77 and a.data.game_vertex_id == 2, "place and links from the new map")
local carried = {}
for id, o in pairs(objects) do if o.parent_id == a.id then carried[#carried + 1] = o end end
assert(#carried == 1 and carried[1].sec == "wpn_ak74", "profile supplies replaced by what was carried")
assert(carried[1].data.condition == 0.62 and carried[1].data.ammo_elapsed == 17)
assert(carried[1].data.story_id == nil and carried[1].data.game_vertex_id == 2, "item place fields from the new map")
assert(arrive() == "nothing", "a record is used once")
''')
marsh.execute(r'''
local c = spawn("stalker_c", 1, 1, nil, {})
watched = make_squad("stalker_sim_squad", 1, {c.id})
players[5] = {position = function() return {distance_to = function() return 10 end} end}
assert(depart(function() return 0 end) == "nobody", "a squad in sight of a player stays")
''')
print("NPC transit: identity, inventory and squad move once between location servers; story/watched squads stay PASS")
