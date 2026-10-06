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
function command_line() return "-netcoop_npc_transit" end
clsid = {level_changer_s = 50, level_changer = 51, script_stalker = 1, stalker = 2, actor = 3, script_actor = 4}
function IsStalker(o, c) return c == 1 end
function game_graph() return {vertex = function(_, gv) return {level_id = function() return gv end} end} end
local sim = {object = function(_, id) return objects[id] end, level_name = function(_, id) return levels[id] end}
function alife() return sim end
level = {name = function() return LEVEL end, object_by_id = function(id) return players[id] end}
players = {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
ini_sys = {section_exist = function(_, s) return s ~= "missing_item" end}
function net_packet()
    local p = {cells = {}, cursor = 1, size = 0}
    function p:w_begin() self.cells = {}; self.size = 2; self.cursor = 1 end
    function p:r_seek(n) assert(n == 2); self.cursor = 1 end
    function p:w(value, width) self.cells[#self.cells + 1] = {value, width}; self.size = self.size + width end
    function p:r() local c = assert(self.cells[self.cursor], "truncated packet"); self.cursor = self.cursor + 1; return c[1] end
    function p:w_u32(v) self:w(v, 4) end
    function p:r_u32() return self:r() end
    function p:w_u16(v) self:w(v, 2) end
    function p:r_u16() return self:r() end
    function p:w_stringZ(v) self:w(v, #v + 1) end
    function p:r_stringZ() local v = self:r(); assert(type(v) == "string"); return v end
    function p:w_tell() return self.size end
    function p:r_tell() local n = 2; for i = 1, self.cursor - 1 do n = n + self.cells[i][2] end; return n end
    function p:r_eof() return self.cursor > #self.cells end
    return p
end
local function new(section, cls, gv, parent, fields)
	next_id = next_id + 1
	local o = {id = next_id, m_game_vertex_id = gv, parent_id = parent or 65535, position = {x = 0},
		m_level_vertex_id = 7, cls = cls, sec = section, alive_ = true, online = false, data = fields or {}}
	function o:name() return self.sec .. tostring(self.id) end
	function o:clsid() return self.cls end
	function o:section_name() return self.sec end
	function o:alive() return self.alive_ end
	objects[o.id] = o
	return o
end
function spawn(section, cls, gv, parent, fields) return new(section, cls, gv, parent, fields) end
utils_stpk = {
    parse_cse_alife_object_properties_packet = function(t, p) t.game_vertex_id = p:r_u16(); t.custom_data = p:r_stringZ() end,
    fill_cse_alife_object_properties_packet = function(t, p) p:w_u16(t.game_vertex_id); p:w_stringZ(t.custom_data) end,
	get_level_changer_data = function(se) return {dest_level_name = se.dest} end,
	get_stalker_data = function(se) local t = {} for k, v in pairs(se.data) do t[k] = v end return t end,
	set_stalker_data = function(t, se) se.data = t end,
	get_object_data = function(se) local t = {} for k, v in pairs(se.data) do t[k] = v end return t end,
	set_object_data = function(t, se) se.data = t end,
}
function alife_release(se)
    if fail_release_id == se.id then error("release injected") end
    released[#released + 1] = se.id; objects[se.id] = nil; SIMBOARD.squads[se.id] = nil
end
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
    function squad:STATE_Write(p)
        p:w_u16(self.m_game_vertex_id); p:w_stringZ(self.custom_data or "squad personal state")
        p:w_u32(#self.members)
        for _, id in ipairs(self.members) do p:w_u16(id) end
        local start = p:w_tell()
        p:w_stringZ("nil"); p:w_stringZ("nil"); p:w_stringZ(self.respawn_point_prop_section or "origin props")
        p:w_stringZ("nil"); p:w_stringZ("nil") -- GAMMA's fifth string: scripted_target
        p:w_u16(p:w_tell() - start)
    end
    function squad:STATE_Read(p)
        self.m_game_vertex_id = p:r_u16(); self.custom_data = p:r_stringZ()
        local count = p:r_u32(); assert(count == #self.members)
        for _, id in ipairs(self.members) do assert(p:r_u16() == id) end
        local start = p:r_tell()
        assert(p:r_stringZ() == "nil"); assert(p:r_stringZ() == "nil")
        self.respawn_point_prop_section = p:r_stringZ()
        assert(p:r_stringZ() == "nil"); assert(p:r_stringZ() == "nil")
        local size = p:r_tell() - start; assert(p:r_u16() == size and p:r_eof())
    end
	SIMBOARD.squads[squad.id] = true -- as in GAMMA: id -> true
	return squad
end
SIMBOARD = {squads = {}, assign_squad_to_smart = function() end}
function alife_create(section, pos, lvid, gvid) local s = make_squad(section, gvid, {}); created[#created + 1] = s; return s end
function alife_create_item(section, owner)
    if section == fail_item then return nil end
    return new(section, 30, owner.m_game_vertex_id, owner.id, {game_vertex_id = owner.m_game_vertex_id})
end
storage_state = {se_object = {}, game_object = {}}
alife_storage_manager = {get_state = function() return storage_state end}
db = {storage = {}}
function deep_copy(t, seen)
    if type(t) ~= "table" then return t end
    seen = seen or {}; if seen[t] then return seen[t] end
    local c = {}; seen[t] = c
    for k, v in pairs(t) do c[deep_copy(k, seen)] = deep_copy(v, seen) end
    return c
end
function netcoop_world_save(reason)
    if fail_save then return false end
    snapshot = deep_copy({objects = objects, squads = SIMBOARD.squads, storage = storage_state, created = created})
    return true
end
function rollback_to_checkpoint()
    local saved = deep_copy(snapshot)
    objects, SIMBOARD.squads, storage_state, created = saved.objects, saved.squads, saved.storage, saved.created
end
'''

serial = 0
fail_put = False
fail_ack = False

def vm(level, gv):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(WORLD, level)
    g = lua.globals()
    g.netcoop_cluster_maps = lambda: "l01_escape" if level == "k00_marsh" else "k00_marsh"
    def new_id():
        global serial
        serial += 1
        return f"{serial:032x}"
    def put(target, key, wire):
        if fail_put:
            return False
        queue = records.setdefault(target, {})
        if key in queue:
            assert queue[key][0] == wire, "same id never changes payload"
        else:
            queue[key] = (wire, False)
        return True
    def take(target):
        queue = records.get(target) or {}
        for key in sorted(queue):
            wire, done = queue[key]
            if not done:
                return key + "\n" + wire
        return ""
    def ack(target, key):
        if fail_ack:
            return False
        wire, _ = records[target][key]
        records[target][key] = wire, True
        return True
    def take_next(target, after):
        queue=records.get(target) or {}
        pending=[key for key in sorted(queue) if not queue[key][1]]
        if not pending:
            return ""
        key=next((key for key in pending if key>after),pending[0])
        return key+"\n"+queue[key][0]
    g.netcoop_transit_id = new_id
    g.netcoop_transit_put = put
    g.netcoop_transit_take = take
    g.netcoop_transit_next = take_next
    g.netcoop_transit_ack = ack
    lua.execute(source)
    return lua

def pair():
    global records, fail_put, fail_ack
    records, fail_put, fail_ack = {}, False, False
    marsh, escape = vm("k00_marsh", 1), vm("l01_escape", 2)
    marsh.execute(r'''
changer = spawn("lc", 50, 1); changer.dest = "l01_escape"
a = spawn("stalker_a", 1, 1, nil, {character_name = "Vasya Folk", money = 1200, rank = 300, health = 0.7,
    equipment_preferences = {2, 3}, game_vertex_id = 1, story_id = -1, death_droped = false, custom_data = "personal", visual_name = "v"})
b = spawn("stalker_b", 1, 1, nil, {character_name = "Petro", money = 50, rank = 10, health = 1})
weapon = spawn("wpn_ak74", 30, 1, a.id, {condition = 0.62, ammo_elapsed = 17, upgrades = {"scope"}, game_vertex_id = 1, story_id = -1})
storage_state.se_object[a.id] = {name = a:name(), injured = true, consumption = {last = 123, remaining = 4}}
storage_state.game_object[a.id] = {name = a:name(), pstor_all = {visited = "safehouse"}}
squad = make_squad("stalker_sim_squad", 1, {a.id, b.id})
story = make_squad("story_squad", 1, {spawn("s", 1, 1).id}); story.story = 12
assert(netcoop_world_save("initial"))
''')
    escape.execute('back = spawn("lc", 50, 2); back.dest = "k00_marsh"; assert(netcoop_world_save("initial"))')
    return marsh, escape

def restart(lua):
    lua.globals().rollback_to_checkpoint()
    lua.execute(source)

marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
escape.execute(r'''
assert(arrive() == "arrived")
local squad = created[1]
assert(#squad.members == 2 and squad.m_game_vertex_id == 2 and squad.relation)
local npc = objects[squad.members[1]]
assert(npc.data.character_name == "Vasya Folk" and npc.data.health == .7 and npc.data.money == 1200)
assert(npc.data.death_droped == false and npc.data.custom_data == "personal" and npc.data.equipment_preferences[2] == 3)
assert(npc.data.game_vertex_id == 2 and npc.data.smart_terrain_id == 77)
assert(storage_state.se_object[npc.id].injured and storage_state.se_object[npc.id].consumption.remaining == 4)
assert(storage_state.game_object[npc.id].pstor_all.visited == "safehouse")
local carried = {}
for _, o in pairs(objects) do if o.parent_id == npc.id then carried[#carried + 1] = o end end
assert(#carried == 1 and carried[1].sec == "wpn_ak74")
assert(carried[1].data.condition == .62 and carried[1].data.ammo_elapsed == 17 and carried[1].data.upgrades[1] == "scope")
assert(carried[1].data.game_vertex_id == 2)
assert(arrive() == "nothing")
''')
# The retirement checkpoint contains the wire outbox, not necessarily the
# removed se_object slots (production unregister can clear those slots).
wire = next(iter(records["l01_escape"].values()))[0]
source_pid = marsh.globals().deserialize(wire).members[1].lua.pid
npc_id = escape.globals().created[1].members[1]
assert escape.globals().storage_state.se_object[npc_id].netcoop_persistent_id == source_pid
restart(marsh)
assert marsh.globals().recover_outbox() == "ready"
assert escape.globals().arrive() == "nothing", "source restart cannot republish acknowledged record"

# Source checkpoint fails: nobody can read a transfer; crash restores source.
marsh, escape = pair()
marsh.globals().fail_save = True
assert marsh.globals().depart(lambda: 0) == "source checkpoint pending"
assert escape.globals().arrive() == "nothing"
restart(marsh)
assert marsh.globals().objects[marsh.globals().a.id] is not None
marsh.globals().fail_save = False
assert marsh.globals().depart(lambda: 0) == "left"
assert escape.globals().arrive() == "arrived"

# Retired source is durable, publication fails; crash retries its saved outbox.
marsh, escape = pair()
fail_put = True
assert marsh.globals().depart(lambda: 0) == "publish pending"
assert escape.globals().arrive() == "nothing"
restart(marsh)
assert marsh.globals().objects[marsh.globals().a.id] is None
fail_put = False
assert marsh.globals().recover_outbox() == "ready"
assert escape.globals().arrive() == "arrived"

# Target save fails: in-memory retries don't spawn again. A crash rolls back
# the new squad and leaves the mailbox readable for the next restore.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
escape.globals().fail_save = True
assert escape.globals().arrive() == "target checkpoint pending"
assert len(escape.globals().created) == 1
assert escape.globals().arrive() == "target checkpoint pending"
assert len(escape.globals().created) == 1
restart(escape)
assert len(escape.globals().created) == 0
escape.globals().fail_save = False
assert escape.globals().arrive() == "arrived"
assert len(escape.globals().created) == 1

# Commit succeeded but acknowledgment failed: restart uses durable receipt.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
fail_ack = True
assert escape.globals().arrive() == "ack pending"
restart(escape)
fail_ack = False
assert escape.globals().arrive() == "acknowledged"
assert len(escape.globals().created) == 1

# Missing entrance or ANY inventory section retains the entire record.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
escape.execute('back.dest = "wrong_map"')
assert escape.globals().arrive() == "no entrance"
assert len(escape.globals().created) == 0
escape.execute('back.dest = "k00_marsh"; ini_sys.section_exist = function(_, s) return s ~= "wpn_ak74" end')
assert escape.globals().arrive() == "record held"
assert len(escape.globals().created) == 0
escape.execute('ini_sys.section_exist = function() return true end')
assert escape.globals().arrive() == "arrived"

# Partial spawn fails: every new entity rolls back, original record survives.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
escape.globals().fail_item = "wpn_ak74"
assert escape.globals().arrive() == "restore failed"
escape.execute('for _, o in pairs(objects) do assert(o.cls == 50, "no partial squad or supplies") end')
escape.globals().fail_item = None
assert escape.globals().arrive() == "arrived"

# Source partial retirement: reconcile exact persistent identities on retry.
marsh, escape = pair()
marsh.execute('fail_release_id = b.id')
try:
    marsh.globals().depart(lambda: 0)
except Exception:
    pass
else:
    raise AssertionError("fault must hold departure")
assert escape.globals().arrive() == "nothing"
marsh.globals().fail_release_id = None
assert marsh.globals().recover_outbox() == "ready"
assert escape.globals().arrive() == "arrived"

# Unsupported/unmapped state holds source; online/story/watched NPCs stay.
marsh, escape = pair()
marsh.execute('storage_state.se_object[a.id].unsupported = function() end')
assert marsh.globals().depart(lambda: 0).startswith("capture held")
assert marsh.globals().objects[marsh.globals().a.id] is not None
assert not records
marsh.execute('storage_state.se_object[a.id].unsupported = nil; storage_state.some_mod = {[a.id] = {target_id = 999}}')
assert marsh.globals().depart(lambda: 0).startswith("capture held")
assert not records
marsh.execute('storage_state.some_mod = nil; a.online = true')
assert marsh.globals().depart(lambda: 0) == "nobody"
marsh.execute('a.online = false; players[5] = {position = function() return {distance_to = function() return 10 end} end}')
assert marsh.globals().depart(lambda: 0) == "nobody"

# A malformed first record stays recoverable but no longer strands a valid
# later squad. The bounded arrival attempt rotates and eventually retries it.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
poison="0"*32
records["l01_escape"][poison]=( "invalid wire",False)
assert escape.globals().arrive() == "record held"
assert len(escape.globals().created) == 0
assert escape.globals().arrive() == "arrived"
assert len(escape.globals().created) == 1
assert escape.globals().arrive() == "record held"
assert records["l01_escape"][poison] == ("invalid wire",False)

# Changing a transfer nonce cannot duplicate persistent people or equipment
# already materialized on this target. Same-nonce receipt retry remains valid.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
assert escape.globals().arrive() == "arrived"
original_id,original_record=next(iter(records["l01_escape"].items()))
copy_id="f"*32
escape.globals().copy_wire=original_record[0]
escape.globals().copy_id=copy_id
copy_wire=escape.execute('local r = assert(deserialize(copy_wire)); r.id = copy_id; return assert(serialize(r))')
records["l01_escape"][copy_id]=(copy_wire,False)
assert escape.globals().arrive() == "record held"
assert len(escape.globals().created) == 1
assert records["l01_escape"][copy_id][1] is False
assert any("persistent identity already present" in line for line in escape.globals().logs.values())

# Target proximity holds the intact mailbox before any entity/receipt/save.
# Every connected player's distance is checked, including the exact boundary.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
pending = dict(records["l01_escape"])
escape.execute('''
players[1] = {position = function() return {distance_to = function() return 1000 end} end}
players[2] = {position = function() return {distance_to = function() return 150 end} end}
''')
assert escape.globals().arrive() == "entrance occupied"
assert len(escape.globals().created) == 0
assert records["l01_escape"] == pending
escape.execute('assert(next(storage_state.netcoop_transit_v2.inbox) == nil)')
restart(escape)
assert escape.globals().arrive() == "entrance occupied"
assert len(escape.globals().created) == 0
assert records["l01_escape"] == pending
escape.execute('players[2] = nil')
assert escape.globals().arrive() == "arrived"
assert len(escape.globals().created) == 1

# A held entrance does not strand another entrance, nor does player arrival
# after materialization interfere with an idempotent receipt/ACK retry.
marsh, escape = pair()
assert marsh.globals().depart(lambda: 0) == "left"
original_id, original_record = next(iter(records["l01_escape"].items()))
escape.globals().other_wire = original_record[0]
escape.globals().other_id = "e"*32
other_wire = escape.execute('''
local r = assert(deserialize(other_wire)); r.id = other_id; r.from = "l02_garbage"
r.lua.pid = string.format("%032x", 700)
for i, member in ipairs(r.members) do
    member.lua.pid = string.format("%032x", 700+i)
    for j, item in ipairs(member.items) do item.lua.pid = string.format("%032x", 800+i*10+j) end
end
other = spawn("lc", 50, 2); other.dest = "l02_garbage"; other.position.x = 1000
players[1] = {position = function() return {distance_to = function(_, pos) return pos.x end} end}
return assert(serialize(r))
''')
records["l01_escape"]["e"*32] = (other_wire, False)
assert escape.globals().arrive() == "entrance occupied"
assert records["l01_escape"][original_id] == original_record
fail_ack = True
assert escape.globals().arrive() == "ack pending"
assert len(escape.globals().created) == 1
escape.execute('players[1] = {position = function() return {distance_to = function() return 0 end} end}')
assert escape.globals().arrive() == "entrance occupied"
fail_ack = False
assert escape.globals().arrive() == "acknowledged"
assert len(escape.globals().created) == 1
escape.execute('players = {}')
assert escape.globals().arrive() == "arrived"
assert len(escape.globals().created) == 2

# Strict parser rejects executable Lua, truncation, duplicates and resource
# bombs without ever invoking a compiler or executing mailbox contents.
escape.execute(r'''
assert(deserialize("(function() while true do end end)()") == nil)
assert(deserialize("T2:S1:xN1;S1:xN2;") == nil)
assert(deserialize("T1:S1:xS999999:abc") == nil)
assert(deserialize("T1:S1:xN1e999;") == nil)
assert(deserialize(string.rep("T1:S1:x", 30) .. "B1") == nil)
assert(deserialize("T0:trailing") == nil)
assert(serialize({value = 0/0}) == nil)
assert(serialize({value = "a\0b"}) == nil)
local cycle = {}; cycle.self = cycle; assert(serialize(cycle) == nil)
local text = assert(serialize({text = "Привет", flag = false, numbers = {1, -2, .1}}))
assert(deserialize(text).text == "Привет" and deserialize(text).flag == false)
''')
print("NPC transit PASS: paired checkpoints, crash/retry at source/publish/target/ack, intact inventory, stable IDs and supported Lua/native state, held exit/section, rollback, bounded non-executable wire, held-record rotation, target identity collision refusal and occupied entrance admission")
escape.execute('command_line = function() return "-netcoop_cluster_selftest" end')
assert escape.globals().arrive() == "ownership adapter required"
assert escape.globals().depart(lambda: 0) == "ownership adapter required"
