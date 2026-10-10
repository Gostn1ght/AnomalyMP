"""Artefact respawn on a location server (owner 2026-10-10). Actual
netcoop_artefacts driving a stand-in with GAMMA's grok_artefact_spawner logic:
no player on the map, nothing spawns; a player arriving restarts GAMMA's delays
(30-77 s, each next try x1.14); after the delay the fields refill, again while
players stay. The dedicated callback filter lets the emission's world event
(actor_on_interaction "anomalies") through: bind_anomaly_zone and drx_da_main
refill artefacts on "emission_end"."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
tg = 0
function time_global() return tg end
players = ""
function netcoop_players() return players end
function printf() end
level = {name = function() return "k00_marsh" end}
refills = 0
dynamic = 0
-- GAMMA's spawner (grok_artefacts_random_spawner.script), its real logic:
grok_artefacts_random_spawner = {spawned = 0, regular_fields_chance = 65, dynamic_fields_chance = 25,
    black_listed_levels = {}}
local s = grok_artefacts_random_spawner
function s.grok_artefact_spawner()
    tg_now = time_global()
    if s.spawned == 0 then
        s.delay1 = s.delay1 * 1.14 or 15250
        s.delay2 = s.delay2 * 1.14 or 31520
        s.grok_delay = tg_now + math.random(s.delay1, s.delay2)
        s.spawned = 1
    end
    if s.spawned == 1 and tg_now > s.grok_delay then
        refills = refills + 1
        s.spawned = 0
    end
end
''')
mod = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            mod, (root / "server/netcoop_artefacts.script").read_text(encoding="utf-8"))
s = g.grok_artefacts_random_spawner
# no player on the map: nothing happens, no error from nil delays
for _ in range(10):
    g.tg += 60000
    mod.update_world()
assert g.refills == 0 and s.delay1 is None
# a player arrives: GAMMA's delays (30-77 s, x1.14), then the fields refill
g.players = "7"
mod.update_world()
assert 30250 <= s.delay1 <= 30250 * 1.15 and s.spawned == 1
for _ in range(200):
    g.tg += 1000
    mod.update_world()
assert g.refills >= 1, g.refills
first = g.refills
# keeps going while players stay; a second player restarts the short delays
g.players = "7,9"
mod.update_world()
assert s.delay1 <= 30250 * 1.15
for _ in range(400):
    g.tg += 1000
    mod.update_world()
assert g.refills > first

# the dedicated filter: anomalies' world events pass, client feedback does not
compat = (root / "server/netcoop_server_compat.script").read_text(encoding="utf-8")
block = compat[compat.index("_G.SendScriptCallback = function(name, ...)"):]
assert block.index('name == "actor_on_interaction" and select(1, ...) == "anomalies"') < block.index('string.find(name, "^actor_on_")')
assert "netcoop_artefacts.update_world" in compat
# the emission sends that event at its end (GAMMA's refill trigger)
emission = (root / "server/netcoop_emission.script").read_text(encoding="utf-8")
assert 'SendScriptCallback("actor_on_interaction", "anomalies", nil, "emission_end")' in emission
print("netcoop artefacts: OK")
