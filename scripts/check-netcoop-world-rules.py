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

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
function netcoop_enabled() return true end
function printf() end
function RegisterScriptCallback() end
state = {}; writes = {}; short_write = false; save_error = false
marshal = {encode = function(value) return "encoded-complete-snapshot" end}
original_encode = marshal.encode
io = {open = function(path, mode)
    if not writes[path] then return nil end
    return {read = function() return writes[path] end, close = function() return true end}
end}
function getFS() return {update_path = function() return "saves/" end} end
alife_storage_manager = {
    get_state = function() return state end,
    CALifeStorageManager_before_save = function(fname)
        local bytes = marshal.encode(state)
        if save_error then error("injected Lua save exception") end
        writes["saves/" .. fname:sub(0, -6):lower() .. ".scoc"] = short_write and bytes:sub(1, 4) or bytes
    end
}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
local save = alife_storage_manager.CALifeStorageManager_before_save
install(); assert(save == alife_storage_manager.CALifeStorageManager_before_save)
save("Zone_A.scop")
assert(marshal.encode == original_encode, "encoder restored after success")
assert(script_snapshot_matches("Zone_A"), "exact saved script bytes verified")
assert(not script_snapshot_matches("Zone_A"), "one capture cannot bless another save")
short_write = true; save("Zone_A.scop")
assert(not script_snapshot_matches("Zone_A"), "nonempty truncated script file rejected")
short_write = false; save("Zone_A.scop")
writes["saves/zone_a.scoc"] = "stale-snapshot"
assert(not script_snapshot_matches("Zone_A"), "same-slot stale state rejected")
save_error = true; assert(not pcall(save, "Zone_A.scop"))
assert(marshal.encode == original_encode, "encoder restored even when saver raises")
assert(not script_snapshot_matches("Zone_A"))
''')
print("Actual server script-save guard: full bytes, truncated/stale data, one-use capture, encoder restoration on exception PASS")
