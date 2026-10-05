"""Execute the actual server population guard; no native build needed."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/netcoop-overlay/server/zz_netcoop_world_rules.script").read_text()
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
cooperative = true; spawns = 0; initial = 0; quest = 0; callbacks = {}
function netcoop_enabled() return cooperative end
function printf() end
function RegisterScriptCallback(kind, fn) callbacks[kind] = fn end
smart_terrain = {se_smart_terrain = {try_respawn = function() spawns = spawns + 1 end}}
SIMBOARD = {create_squad = function() quest = quest + 1 end,
    fill_start_position = function() initial = initial + 1 end}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
local flags = {disabled = false}
callbacks.on_try_respawn({}, flags); assert(flags.disabled)
for i=1,100 do smart_terrain.se_smart_terrain.try_respawn({}) end
assert(spawns == 0, "dead members must not be replenished")
SIMBOARD.fill_start_position(); SIMBOARD.create_squad()
assert(initial == 1 and quest == 1, "initial and scripted squads retain their separate creation paths")
local wrapped = smart_terrain.se_smart_terrain.try_respawn
for i=1,10 do callbacks.on_game_load() end
assert(wrapped == smart_terrain.se_smart_terrain.try_respawn, "install is idempotent")
smart_terrain.se_smart_terrain.try_respawn = function() spawns = spawns + 1 end
callbacks.on_game_load(); smart_terrain.se_smart_terrain.try_respawn({})
assert(spawns == 0, "guard survives a mod replacing the method on load")
cooperative = false
flags.disabled = false; callbacks.on_try_respawn({}, flags); assert(not flags.disabled)
smart_terrain.se_smart_terrain.try_respawn({}); assert(spawns == 1, "single-player retains original population policy")
''')
print("Actual server world rules: no NPC/mutant replenishment, preserved initial population, idempotent reload guard PASS")
