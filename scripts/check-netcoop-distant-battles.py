"""K10 (doc 43): distant fight sounds come from real offline battles.

The actual netcoop_distant_battles (server) and netcoop_distant_sound (client)
scripts: a GAMMA OCS battle round on this map is reported to players 150-1500 m
away, at the point between the squads, at most once per fight per 15 s and once
per player per 5 s; other maps, powerless rounds, near/far players and dead
players get nothing; the stock battle always runs with the same arguments.
The client places the sound on the real direction within GAMMA's audible
range with volume falling by the real distance."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
tick = 0
function time_global() return tick end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
is_squad_monster = {monster = true, monster_predatory_day = true}
here = 3
sim = {level_id = function() return here end}
function alife() return sim end
players = {}
function netcoop_players() local t = {} for id in pairs(players) do t[#t + 1] = id end table.sort(t) return table.concat(t, ",") end
sent = {}
function netcoop_send_to_actor(id, ch, data) sent[#sent + 1] = {id, ch, data} end
level = {object_by_id = function(id) return players[id] end}
function player(id, x, z, dead)
    players[id] = {position = function() return {x = x, y = 0, z = z} end, alive = function() return not dead end}
end
stock_calls = {}
cached = {}
sim_offline_combat = {ocs_power = cached,
    calculate_squad_power = function(squad, c, raw) assert(raw) return squad.power end,
    simulate_battle = function(...) stock_calls[#stock_calls + 1] = {...} end}
function squad(id, x, z, power) return {id = id, position = {x = x, y = 10, z = z}, power = power} end
''')
g.netcoop_distant_battles = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_distant_battles, (root / "scripts/netcoop-overlay/server/netcoop_distant_battles.script").read_text(encoding="utf-8"))
lua.execute(r'''
netcoop_distant_battles.install()
netcoop_distant_battles.install()  -- twice: wrapped once
battle = sim_offline_combat.simulate_battle
a, b = squad(10, 1000, 0, 50), squad(11, 1000, 200, 40)
player(1, 0, 100)     -- 1000 m away
player(2, 990, 100)   -- 10 m: the fight is online for this one
player(3, 3000, 100)  -- 2000 m: too far
player(4, 400, 100, true)  -- dead
''')
run = lua.eval("function(...) battle(...) end")

def sent():
    return [tuple(x.values()) for x in lua.eval("sent").values()]

run(10, 11, g.a, g.b, "stalker", "bandit", 3)
assert sent() == [(1, "battle", "gunfire 1000.0 10.0 100.0")], sent()
assert len(g.stock_calls) == 1 and lua.eval("""(function() local c = stock_calls[1]
    return c[1] == 10 and c[2] == 11 and c[3] == a and c[4] == b and c[5] == "stalker" and c[6] == "bandit" and c[7] == 3 end)()""")
assert len(g.logs) == 1, list(g.logs.values())  # installed once

# Same fight again within 15 s (either order of ids): silent; battle still runs.
g.tick = 1000
run(11, 10, g.b, g.a, "bandit", "stalker", 3)
assert len(sent()) == 1 and len(g.stock_calls) == 2
# Another fight 3 s later: player 1 was told 3 s ago -> silent for player 1;
# player 2 is 1234 m from it and was never told -> hears it.
g.tick = 3000
lua.execute("c, d = squad(20, 0, 900, 30), squad(21, 100, 900, 30)")
run(20, 21, g.c, g.d, "monster", "monster_predatory_day", 3)
assert sent()[1:] == [(2, "battle", "mutant 50.0 10.0 900.0")], sent()
# 15 s after that fight was first reported: player 1 hears it too.
g.tick = 18000
run(20, 21, g.c, g.d, "monster", "monster_predatory_day", 3)
assert sent()[2:] == [(1, "battle", "mutant 50.0 10.0 900.0"), (2, "battle", "mutant 50.0 10.0 900.0")], sent()
# Mutant vs people: gunfire.
g.tick = 40000
run(10, 20, g.a, g.c, "stalker", "monster", 3)
assert sent()[-1][2].startswith("gunfire "), sent()

# Another map, or a side without power (GAMMA skips the round): nothing.
n = len(sent())
g.tick = 100000
run(10, 11, g.a, g.b, "stalker", "bandit", 4)
lua.execute("e = squad(30, 1000, 0, 0); f = squad(31, 1000, 50, 20)")
run(30, 31, g.e, g.f, "stalker", "bandit", 3)
lua.execute("cached[31] = 0; e.power = 9")
run(30, 31, g.e, g.f, "stalker", "bandit", 3)
assert len(sent()) == n, sent()[n:]
assert len(g.stock_calls) == 8  # every round still went to GAMMA

# A failing report never blocks the battle.
lua.execute("sim.level_id = function() error('boom') end")
run(10, 11, g.a, g.b, "stalker", "bandit", 3)
assert len(g.stock_calls) == 9 and "boom" in g.logs[len(g.logs)]

# Client placement: direction kept, distance clamped to GAMMA's range.
g.netcoop_distant_sound = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_distant_sound, (root / "scripts/netcoop-overlay/client/netcoop_distant_sound.script").read_text(encoding="utf-8"))
place = g.netcoop_distant_sound.placement
x, y, z, v = place(lua.eval("{x = 0, y = 0, z = 0}"), 0, 500, 1000)
assert abs(x) < 1e-6 and abs(z - 110) < 1e-6 and y == 20 and abs(v - 0.15) < 1e-6, (x, y, z, v)
x, y, z, v = place(lua.eval("{x = 10, y = 5, z = 0}"), 70, 5, 80)
assert abs(x - 70) < 1e-6 and abs(z - 80) < 1e-6 and v == 1, (x, z, v)
x, y, z, v = place(lua.eval("{x = 0, y = 0, z = 0}"), -440, 0, 0)
assert abs(x + 110) < 1e-6 and abs(v - 0.25) < 1e-6, (x, v)
assert place(lua.eval("{x = 0, y = 0, z = 0}"), 0.5, 0, 0) is None

# The wiring: the server installs it, the client handles the channel.
srv = (root / "scripts/netcoop-overlay/server/netcoop_server_compat.script").read_text(encoding="utf-8")
cli = (root / "scripts/netcoop-overlay/client/netcoop_client_compat.script").read_text(encoding="utf-8")
assert "netcoop_distant_battles.install()" in srv
assert 'channel == "battle"' in cli and "netcoop_distant_sound.receive(data)" in cli
print("netcoop distant battles: OK")
