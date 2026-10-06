"""Ranks, renegades and bounties (doc 47 §3-5): the actual netcoop_ranks and
netcoop_factions scripts over a shared store."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
server_dir = root / "scripts/netcoop-overlay/server"
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

lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
g.netcoop_store_read = lambda b, k: store.get((b, k), "")
def swap(b, k, expected, value):
    if store.get((b, k), "") != expected:
        return False
    store[(b, k)] = value
    return True
g.netcoop_store_swap = swap
g.netcoop_store_keys = lambda b: " ".join(sorted(k for (bb, k) in store if bb == b))
lua.execute(r'''
FACTIONS = ...
clock = 100000
os = {time = function() return clock end}
function printf() end
tick = 0
function time_global() return tick end
game = {translate_string = function(s) return s end}
function ini_file() return { section_exist = function(_, s) return FACTIONS[s] ~= nil end,
    r_string_ex = function(_, s, k) return FACTIONS[s] and FACTIONS[s][k] end } end
players, chars, sent = {}, {}, {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end return table.concat(t, " ") end
function netcoop_actor_character(id) return chars[id] or "" end
function netcoop_set_character_faction() return true end
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = ch .. ":" .. data end
level = {object_by_id = function(id) return players[id] or others[id] end}
others = {}
function character_community(o) return o.community end
goodwill = {}
relation_registry = {
    community_goodwill = function(c, id) return (goodwill[id] or {})[c] or 0 end,
    set_community_goodwill = function(c, id, v) goodwill[id] = goodwill[id] or {}; goodwill[id][c] = v end }
local hostile = {stalker_bandit = true, bandit_stalker = true, dolg_freedom = true, freedom_dolg = true}
xr_conditions = {is_factions_enemies = function(_, _, p) return hostile[p[1] .. "_" .. p[2]] or false end}
function player(id, char, faction)
    local o = {community = "actor_" .. faction, rank_ = 1000, rep = 0, money = 0}
    function o:id() return id end
    function o:character_name() return char end
    function o:character_rank() return self.rank_ end
    function o:character_reputation() return self.rep end
    function o:change_character_rank(v) self.rank_ = self.rank_ + v end
    function o:give_money(v) self.money = self.money + v end
    function o:set_character_community(c) self.community = c end
    players[id] = o; chars[id] = char
    return o
end
function npc(id, faction) local o = {community = faction}; function o:id() return id end; others[id] = o; return o end
''', lua.table_from({k: lua.table_from(v) for k, v in ltx("factions.ltx").items()}))
g.netcoop_factions = lua.table()
lua.execute("setfenv(assert(loadstring(...)), setmetatable(netcoop_factions,{__index=_G}))()",
            (server_dir / "netcoop_factions.script").read_text(encoding="utf-8"))
g.netcoop_ranks = lua.table()
lua.execute("setfenv(assert(loadstring(...)), setmetatable(netcoop_ranks,{__index=_G}))()",
            (server_dir / "netcoop_ranks.script").read_text(encoding="utf-8"))
lua.execute(r'''
local r = netcoop_ranks
local killer = player(5, "bad_1", "stalker")
local hunter = player(6, "hunter_1", "dolg")
-- Mutant kills raise the killer's rank.
r.on_monster_death({}, killer); assert(killer.rank_ > 1000)
-- Enemies are fair game: bandits do not count.
for i = 1, 6 do r.on_npc_death(npc(100 + i, "bandit"), killer) end
assert(killer.community == "actor_stalker", "killing enemies is not a crime")
-- Four loners (own faction) and a neutral player in 12 hours: renegade.
for i = 1, 4 do r.on_npc_death(npc(200 + i, "stalker"), killer) end
assert(killer.community == "actor_stalker")
local neutral = player(7, "eco_1", "ecolog")
r.on_player_death(7, 5)
assert(killer.community == "actor_renegade", "the fifth bad kill makes a renegade")
local b = r.bounty_of("bad_1"); assert(b and b.reward >= 5000 + 2500 * 5, "wanted with a reward")
assert(netcoop_factions.apply_problem(killer, "stalker"), "cannot just apply while wanted")
-- Another player collects the bounty once.
r.on_player_death(5, 6)
assert(hunter.money == b.reward, "bounty paid")
r.on_player_death(5, 6)
assert(hunter.money == b.reward, "paid only once")
assert(r.bounty_of("bad_1") == nil)
-- Old kills leave the window.
local fresh = player(8, "fresh_1", "stalker")
for i = 1, 4 do r.on_npc_death(npc(300 + i, "stalker"), fresh) end
clock = clock + 13 * 3600
r.on_npc_death(npc(400, "stalker"), fresh)
assert(fresh.community == "actor_stalker", "kills older than 12 h do not add up")
-- Attitudes follow the character to a new Actor id; rank reaches the client.
goodwill[8] = {stalker = -300, dolg = 200}
tick = 10000; r.update()          -- first sight: restore (nothing saved yet)
tick = 70000; r.update()          -- a minute later: capture
players[8] = nil; chars[8] = nil
local again = player(9, "fresh_1", "stalker")
tick = 80000; r.update()
assert(relation_registry.community_goodwill("dolg", 9) == 200, "attitudes restored for the new Actor")
local synced = false
for _, s in ipairs(sent) do if s:find("^player_rank:") then synced = true end end
assert(synced, "rank sent to the client")
''')
print("Ranks: mutant rank credit, renegade after 5 bad kills in 12 h (NPCs and players), bounty paid once, attitudes kept across logins, rank synced PASS")
