"""Loner squads (doc 47 stage 8): the actual netcoop_squads, netcoop_ranks and
netcoop_factions scripts over a shared store."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
server_dir = root / "scripts/netcoop-overlay/server"
store = {}

lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
g.netcoop_store_read = lambda b, k: store.get((b, k), "")
def swap(b, k, expected, value):
    if store.get((b, k), "") != expected:
        return False
    store[(b, k)] = value
    return True
g.netcoop_store_swap = swap
g.netcoop_store_keys = lambda b: " ".join(sorted(k for (bb, k) in store if bb == b and store[(bb, k)]))
lua.execute(r'''
clock = 100000
os = {time = function() return clock end}
function printf() end
tick = 0
function time_global() return tick end
game = {translate_string = function(s) return s end}
function ini_file() return { section_exist = function() return true end, r_string_ex = function() return nil end } end
players, chars, sent = {}, {}, {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
function netcoop_actor_character(id) return chars[id] or "" end
function netcoop_set_character_faction() return true end
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = id .. ":" .. ch .. ":" .. data end
level = {object_by_id = function(id) return players[id] end}
function character_community(o) return o.community end
goodwill = {}
relation_registry = {
    community_goodwill = function(c, id) return (goodwill[id] or {})[c] or 0 end,
    set_community_goodwill = function(c, id, v) goodwill[id] = goodwill[id] or {}; goodwill[id][c] = v end }
xr_conditions = {is_factions_enemies = function() return false end}
function player(id, char, name, faction)
    local o = {community = "actor_" .. faction, rank_ = 1000, rep = 0}
    function o:id() return id end
    function o:character_name() return name end
    function o:character_rank() return self.rank_ end
    function o:character_reputation() return self.rep end
    players[id] = o; chars[id] = char
    return o
end
''')
for name in ("netcoop_factions", "netcoop_ranks", "netcoop_squads"):
    g[name] = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
                g[name], (server_dir / (name + ".script")).read_bytes().decode("cp1251"))
lua.execute(r'''
local s, r = netcoop_squads, netcoop_ranks
local a = player(1, "anna_1", "Anna", "stalker")
local b = player(2, "boris_1", "Boris", "stalker")
local c = player(3, "cyril_1", "Cyril", "stalker")
local d = player(4, "duty_1", "Dima", "dolg")
local function step() tick = tick + 6000; r.update(); s.update() end
step(); step()
-- Consent: an invitation alone does not make a member.
assert(s.command(a, "invite Boris"):find("^~"), "invite")
assert(not s.command(b, ""):find("squad:"), "invited is not a member yet")
assert(s.command(a, "invite Dima"):find("not a Loner"), "only Loners")
assert(s.command(b, "accept"):find("joined"), "accept")
assert(s.command(a, ""):find("Anna") and s.command(a, ""):find("Boris"), "both in the squad")
assert(s.command(c, "accept"):find("no invitation"), "no invitation, no squad")
-- Anna's own change of an attitude reaches Boris at half strength, not Cyril.
goodwill[1] = goodwill[1] or {}; goodwill[1].dolg = (goodwill[1].dolg or 0) - 100
step()
assert(relation_registry.community_goodwill("dolg", 2) == -50, "squadmate gets half: " .. relation_registry.community_goodwill("dolg", 2))
assert(relation_registry.community_goodwill("dolg", 3) == 0, "outsider untouched")
assert(relation_registry.community_goodwill("dolg", 1) == -100, "no echo back to Anna")
step()
assert(relation_registry.community_goodwill("dolg", 2) == -50, "shared once")
-- Joining a faction leaves the squad.
b.community = "actor_csky"
step()
assert(not s.command(a, ""):find("Boris"), "a faction member left the squad")
-- Leave.
assert(s.command(a, "leave"):find("left"), "leave")
''')
print("Squads: Loners only, invite + accept (consent), half-strength shared attitudes without echo, faction join leaves PASS")
