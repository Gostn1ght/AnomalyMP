"""Faction membership (doc 47): the actual netcoop_factions.script in two Lua
VMs (two location servers) over one shared store with compare-and-swap."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/netcoop-overlay/server/netcoop_factions.script").read_text(encoding="utf-8")
ltx = (root / "scripts/netcoop-overlay/server/configs/netcoop/factions.ltx").read_bytes().decode("cp1251")
store = {}


def parse_ltx(text):
    sections, current = {}, None
    for line in text.splitlines():
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
        elif "=" in line and current is not None:
            k, v = line.split("=", 1)
            current[k.strip()] = v.strip()
    return sections


sections = parse_ltx(ltx)


def server():
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    g.netcoop_store_read = lambda b, k: store.get((b, k), "")

    def swap(b, k, expected, value):
        if store.get((b, k), "") != expected:
            return False
        if value == "":
            store.pop((b, k), None)
        else:
            store[(b, k)] = value
        return True
    g.netcoop_store_swap = swap
    lua.execute(r'''
SECTIONS = ...
clock = 1000
os = {time = function() return clock end}
logs = {}
function printf(fmt, ...) logs[#logs + 1] = fmt end
function time_global() return 0 end
game = {translate_string = function(s) return s end}
function ini_file() return {
    section_exist = function(_, s) return SECTIONS[s] ~= nil end,
    r_string_ex = function(_, s, k) return SECTIONS[s] and SECTIONS[s][k] end } end
players, chars, sent, saved = {}, {}, {}, {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
function netcoop_actor_character(id) return chars[id] or "" end
function netcoop_actor_login(id) return chars[id] end
function netcoop_set_character_faction(id, f) saved[id] = f; return true end
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = id .. ":" .. data end
level = {object_by_id = function(id) return players[id] end}
function character_community(o) return o.community end
contracts_done = {}
netcoop_contracts = {completed = function(char, f) return contracts_done[char .. f] or 0 end}
function player(id, char, name, faction, rank)
    local o = {community = "actor_" .. faction, rank_ = rank or 0}
    function o:id() return id end
    function o:character_name() return name end
    function o:character_rank() return self.rank_ end
    function o:set_character_community(c) self.community = c end
    players[id] = o; chars[id] = char
    return o
end
''', lua.table_from({k: lua.table_from(v) for k, v in sections.items()}))
    lua.execute(source)
    return lua

a = server()   # Great Swamp
b = server()   # Army Warehouses
a.execute(r'''
vasya = player(5, "vasya_1", "Vasya", "stalker", 300)
local ok, msg = apply(vasya, "freedom")
assert(not ok and msg:find("contracts"), "Freedom needs Lukash's contracts first: " .. tostring(msg))
contracts_done["vasya_1freedom"] = 5
ok, msg = apply(vasya, "freedom"); assert(ok, msg)
assert(vasya.community == "actor_stalker", "an application does not enrol")
''')
b.execute(r'''
boss = player(9, "boss_1", "Boss", "stalker", 900)
local ok, msg = decide(boss, "freedom", "vasya_1", true, false)
assert(not ok, "a stranger cannot accept")
ok, msg = set_leader("freedom", "boss", 1); assert(ok, msg)
assert(boss.community == "actor_freedom" and saved[9] == "freedom", "the leader joins the faction online")
ok, msg = decide(boss, "freedom", "nobody_1", true, false)
assert(not ok, "no enrolment without an application")
ok, msg = decide(boss, "freedom", "vasya_1", true, false); assert(ok, msg)
''')
a.execute(r'''
update_online()
assert(vasya.community == "actor_freedom" and saved[5] == "freedom", "accepted on another server, applied here")
''')
b.execute(r'''
local ok = set_role(boss, "freedom", "vasya_1", "deputy", false); assert(ok)
ok = set_furniture(boss, "freedom", "vasya_1", true, false); assert(ok)
''')
a.execute(r'''
assert(may_place_in_zone(vasya, "freedom"), "a deputy places furniture in the faction's zone")
petya = player(6, "petya_1", "Petya", "stalker", 50)
contracts_done["petya_1freedom"] = 5
assert(apply(petya, "freedom"))
assert(decide(vasya, "freedom", "petya_1", true, false), "a deputy accepts")
assert(not expel(petya, "freedom", "vasya_1", false), "a member cannot expel")
assert(expel(vasya, "freedom", "petya_1", false), "a deputy expels")
update_online(); assert(petya.community == "actor_stalker", "expelled back to the loners")
-- Ecologists: only the leader or an admin enrols, not a deputy.
local eco = player(7, "eco_1", "Eco", "stalker", 10)
assert(apply(eco, "ecolog"))
assert(set_leader("ecolog", "boss2", 1))
local ok, msg = decide(vasya, "ecolog", "eco_1", true, true); assert(ok, "admin enrols ecologists: " .. tostring(msg))
-- Loners are open and leaderless; renegades only by the Zone.
local lone = player(8, "lone_1", "Lone", "bandit", 0)
assert(apply(lone, "stalker"))
assert(not set_leader("stalker", "boss", 1), "loners have no leader")
assert(not apply(lone, "renegade"), "nobody applies to the renegades")
assert(leave(vasya)); update_online(); assert(vasya.community == "actor_stalker")
''')
print("Factions: apply only, contracts gate, leader/deputy/admin decide per faction policy, cross-server membership, expel, furniture grant, loners/renegades rules PASS")
