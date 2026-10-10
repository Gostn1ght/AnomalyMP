"""K08 / L19 (doc 43): the world's event journal (actual netcoop_world_events and
the OCS wrapper in netcoop_distant_battles). A GAMMA offline-combat round with
losses is recorded with both squads before/after, place, level, game time and
outcome; rounds without losses are not; an NPC/mutant death is recorded with
its killer (player login for a player); the journal keeps the newest 512 in
the world state; a failing record never stops the battle."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
function netcoop_enabled() return true end
function netcoop_pure_client() return false end
state = {}
alife_storage_manager = {get_state = function() return state end}
hours = 10
game = {CTime = function() return {set = function() end} end,
        get_game_time = function() return {diffSec = function() return hours * 3600 end} end}
objects = {}
function alife_object(id) return objects[id] end
sim = {level_id = function() return 3 end, level_name = function(_, lid) return lid == 3 and "k00_marsh" or "other" end}
function alife() return sim end
function squad(id, sec, n, x, z)
    local s = {id = id, n = n, position = {x = x, y = 0, z = z}}
    function s:npc_count() return self.n end
    function s:section_name() return sec end
    objects[id] = s
    return s
end
level = {name = function() return "k00_marsh" end}
function netcoop_actor_login(id) return id == 7 and "mahito" or "" end
callbacks = {}
function RegisterScriptCallback(name, f) callbacks[name] = f end
-- GAMMA's battle: the victim squad loses members or is released.
losses = {}
sim_offline_combat = {
    simulate_battle = function(id_1, id_2)
        local l = losses[id_2]
        if l == "gone" then objects[id_2] = nil elseif l then objects[id_2].n = objects[id_2].n - l end
        if broken_battle then error("gamma") end
    end}
''')
for name in ("netcoop_world_events", "netcoop_distant_battles"):
    g[name] = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
                g[name], (root / "scripts/netcoop-overlay/server" / (name + ".script")).read_text(encoding="utf-8"))
lua.execute("netcoop_world_events.on_game_start(); netcoop_distant_battles.install()")
battle = lua.eval("function(...) sim_offline_combat.simulate_battle(...) end")
recent = lua.eval("function(n) return netcoop_world_events.recent(n) end")

lua.execute('a = squad(10, "stalker_sim_squad", 4, 0, 0); b = squad(11, "bandit_sim_squad", 3, 20, 0)')
battle(10, 11, g.a, g.b, "stalker", "bandit", 3)          # no losses: not kept
assert len(recent(10)) == 0
lua.execute("losses[11] = 1")
battle(10, 11, g.a, g.b, "stalker", "bandit", 3)
e = recent(1)[1]
assert (e.kind, e.level, e.result, e.x, e.y, e.z, e.h) == ("battle", "k00_marsh", "losses 0/1", 10, 0, 0, 10), dict(e)
assert (e.a.id, e.a.sec, e.a.c, e.a.n, e.a.after) == (10, "stalker_sim_squad", "stalker", 4, 4)
assert (e.b.id, e.b.sec, e.b.c, e.b.n, e.b.after) == (11, "bandit_sim_squad", "bandit", 3, 2)
lua.execute('losses[11] = "gone"')
battle(10, 11, g.a, g.b, "stalker", "bandit", 3)
assert recent(1)[1].result == "defender destroyed" and recent(1)[1].b.after == 0

# Deaths: killer named by section/community, a player by login.
lua.execute(r'''
function obj(id, sec, community, x)
    return {id = function() return id end, section = function() return sec end,
            character_community = community and function() return community end or nil,
            position = function() return {x = x, y = 1.25, z = 2} end}
end
callbacks.npc_on_death_callback(obj(50, "sim_default_bandit_2", "bandit", 5.04), obj(7, "actor", "stalker", 0))
callbacks.monster_on_death_callback(obj(51, "dog_weak", nil, 6), obj(52, "sim_default_duty_1", "dolg", 0))
callbacks.monster_on_death_callback(obj(53, "flesh_normal", nil, 6), nil)
''')
d = recent(3)
assert (d[3].kind, d[3].id, d[3].sec, d[3].c, d[3].killer, d[3].x, d[3].y) == ("death", 50, "sim_default_bandit_2", "bandit", "player mahito", 5.0, 1.3), dict(d[3])
assert d[2].killer == "sim_default_duty_1 (dolg)" and d[2].c is None
assert d[1].killer == "unknown"
assert [x.seq for x in d.values()] == [5, 4, 3]

# Bounded: the newest 512 survive, in order, in the saved world state.
for i in range(600):
    lua.execute("netcoop_world_events.record({kind = 'test'})")
r = recent(1000)
assert len(r) == 512 and r[1].seq == 605 and r[512].seq == 94
assert lua.eval("state.netcoop_events.seq") == 605

# A failing record (or GAMMA itself) never loses the battle round.
lua.execute("netcoop_world_events.battle_before = function() error('boom') end; losses[11] = 1; a.n = 4; objects[11] = b; b.n = 3")
battle(10, 11, g.a, g.b, "stalker", "bandit", 3)
assert "boom" in g.logs[len(g.logs)] and g.b.n == 2  # GAMMA's round still ran
print("netcoop world events: OK")
