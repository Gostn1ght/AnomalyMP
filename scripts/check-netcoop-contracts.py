"""Contracts (doc 47; doc 43 I01/I02/I06): the actual netcoop_contracts and
netcoop_factions scripts in two Lua VMs over one shared store."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
server_dir = root / "scripts/netcoop-overlay/server"
contracts_src = (server_dir / "netcoop_contracts.script").read_text(encoding="utf-8")
factions_src = (server_dir / "netcoop_factions.script").read_text(encoding="utf-8")
store = {}

def ltx(name):
    sections, current = {}, None
    for line in (server_dir / "configs/netcoop" / name).read_bytes().decode("cp1251").splitlines():
        line = line.split(";", 1)[0].strip()
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
        elif "=" in line and current is not None:
            k, v = line.split("=", 1)
            current[k.strip()] = v.strip()
    return sections

def server():
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    g.netcoop_store_read = lambda b, k: store.get((b, k), "")
    def swap(b, k, expected, value):
        if store.get((b, k), "") != expected:
            return False
        store[(b, k)] = value
        return True
    g.netcoop_store_swap = swap
    configs = {"netcoop\\contracts.ltx": ltx("contracts.ltx"), "netcoop\\factions.ltx": ltx("factions.ltx")}
    lua.execute(r'''
CONFIGS = ...
os = {time = function() return 1000 end}
function printf() end
function time_global() return 0 end
game = {translate_string = function(s) return s end}
function ini_file(name) local c = CONFIGS[name]; return {
    section_exist = function(_, s) return c[s] ~= nil end,
    r_string_ex = function(_, s, k) return c[s] and c[s][k] end } end
players, chars, released = {}, {}, {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
function netcoop_actor_character(id) return chars[id] or "" end
function netcoop_set_character_faction() return true end
function netcoop_send_to_actor() end
function alife_release_id(id) released[#released + 1] = id end
level = {object_by_id = function(id) return players[id] or npcs[id] end}
function character_community(o) return o.community end
npcs = {}; db = {OnlineStalkers = {}}
function npc(id, profile, community, pos)
    local o = {community = community, pos = pos}
    function o:alive() return true end
    function o:profile_name() return profile end
    function o:position() return {distance_to = function(_, p) return math.abs(p.x - pos) end, x = pos} end
    function o:section() return "stalker" end
    npcs[id] = o; db.OnlineStalkers[#db.OnlineStalkers + 1] = id
    return o
end
function player(id, char, x)
    local o = {community = "actor_stalker", money = 0, rank_ = 0, x = x, items = {}}
    function o:id() return id end
    function o:character_name() return char end
    function o:character_rank() return self.rank_ end
    function o:change_character_rank(v) self.rank_ = self.rank_ + v end
    function o:give_money(v) self.money = self.money + v end
    function o:set_character_community(c) self.community = c end
    function o:position() return {x = self.x, distance_to = function(_, p) return math.abs(p.x - self.x) end} end
    function o:iterate_inventory(fn) for _, item in ipairs(self.items) do fn(nil, item) end end
    players[id] = o; chars[id] = char
    return o
end
function monster(section) return {section = function() return section end} end
function item(id, section) return {id = function() return id end, section = function() return section end} end
''', lua.table_from({k: lua.table_from({s: lua.table_from(v) for s, v in c.items()}) for k, c in configs.items()}))
    g.netcoop_factions = lua.table()
    lua.execute("setfenv(assert(loadstring(...)), setmetatable(netcoop_factions,{__index=_G}))()", factions_src)
    g.netcoop_contracts = lua.table()
    lua.execute("setfenv(assert(loadstring(...)), setmetatable(netcoop_contracts,{__index=_G}))()", contracts_src)
    return lua

military = server()   # Lukash's map
swamp = server()      # another location server
military.execute(r'''
lukash = npc(100, "mil_smart_terrain_7_7_freedom_leader_stalker", "freedom", 0)
p = player(5, "vasya_1", 50)
local c = netcoop_contracts
local ok, msg = c.take(p, "freedom"); assert(not ok, "must stand at the contact")
p.x = 2
ok, msg = c.take(p, "freedom"); assert(ok, msg)
ok = c.take(p, "freedom"); assert(not ok, "one contract at a time")
''')
swamp.execute(r'''
p = player(7, "vasya_1", 0)   -- the same character, later on another map
for i = 1, 8 do netcoop_contracts.on_monster_death(monster("dog_weak"), p) end
netcoop_contracts.on_monster_death(monster("bloodsucker_strong"), p)
''')
military.execute(r'''
local c = netcoop_contracts
local ok, msg = c.finish(p, "freedom"); assert(ok, msg)
assert(p.money == 3000 and p.rank_ == 20, "paid once: " .. p.money)
ok = c.finish(p, "freedom"); assert(not ok and p.money == 3000, "no second payment")
-- Contract 2: fetch 5 dog tails, handed over at the contact.
assert(c.take(p, "freedom"))
p.items = {item(1, "mutant_part_dog_tail"), item(2, "mutant_part_dog_tail")}
ok, msg = c.finish(p, "freedom"); assert(not ok and msg:find("3 more"), msg)
for i = 3, 5 do p.items[#p.items + 1] = item(i, "mutant_part_dog_tail") end
ok = c.finish(p, "freedom"); assert(ok and #released == 5 and p.money == 7000)
assert(c.completed("vasya_1", "freedom") == 2)
-- Joining Freedom needs 5 of Lukash's contracts.
local fok, fmsg = netcoop_factions.apply(p, "freedom"); assert(not fok and fmsg:find("contracts"), fmsg)
''')
print("Contracts: taken at the contact, kills counted on any server, fetch handed in, paid exactly once, chain gates joining PASS")
