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
state = {}
alife_storage_manager = {get_state = function() return state end}
db = {actor = {}}
xr_logic = {pick_section_from_condlist = function(_, _, value) return value end}
-- GAMMA's respawn: a section spawns while fewer of its squads are alive than its limit.
function gamma_respawn(self)
    for k, p in pairs(self.respawn_params) do
        if self.already_spawned[k].num < tonumber(p.num) then
            self.already_spawned[k].num = self.already_spawned[k].num + 1
            spawns = spawns + 1
            return
        end
    end
end
smart_terrain = {se_smart_terrain = {try_respawn = gamma_respawn}}
SIMBOARD = {create_squad = function() quest = quest + 1 end,
    fill_start_position = function() initial = initial + 1 end}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
local smart = {id = 7, respawn_params = {mutants = {num = "2"}, stalkers = {num = "1"}},
    already_spawned = {mutants = {num = 0}, stalkers = {num = 0}}}
for i = 1, 10 do smart_terrain.se_smart_terrain.try_respawn(smart) end
assert(spawns == 3, "the freeplay population fills once: " .. spawns)
-- Every squad dies: nothing is replenished.
smart.already_spawned.mutants.num = 0; smart.already_spawned.stalkers.num = 0
for i = 1, 10 do smart_terrain.se_smart_terrain.try_respawn(smart) end
assert(spawns == 3, "dead squads must not be replenished")
assert(smart.already_spawned.mutants.num == 0, "GAMMA's own counters are left as they were")
SIMBOARD.fill_start_position(); SIMBOARD.create_squad()
assert(initial == 1 and quest == 1, "initial and scripted squads retain their separate creation paths")
local wrapped = smart_terrain.se_smart_terrain.try_respawn
for i=1,10 do callbacks.on_game_load() end
assert(wrapped == smart_terrain.se_smart_terrain.try_respawn, "install is idempotent")
smart_terrain.se_smart_terrain.try_respawn = gamma_respawn
callbacks.on_game_load(); smart_terrain.se_smart_terrain.try_respawn(smart)
assert(spawns == 3, "guard survives a mod replacing the method on load")
cooperative = false
smart.already_spawned.mutants.num = 0
smart_terrain.se_smart_terrain.try_respawn(smart); assert(spawns == 4, "single-player retains original population policy")
''')
print("Actual server world rules: each smart section fills to its freeplay limit once, dead squads are not replaced, idempotent reload guard PASS")

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
cooperative = true; purged = 0; consumed = 0; timers = {}; callbacks = {}; artefacts = 0; npc_items = 0
function netcoop_enabled() return cooperative end
function printf() end
function RegisterScriptCallback(kind, fn) callbacks[kind] = fn end
function RemoveTimeEvent(id, name) timers[id .. name] = nil end
function CreateTimeEvent(id, name, fn) timers[id .. name] = fn end
release_item_manager = {clear = function() purged = purged + 1; return false end}
grok_artefact_despawner = {delete_artefacts = function(id) artefacts = artefacts + id; return id end}
release_npc_inventory = {clean_npc_inv = function(id) npc_items = npc_items + id; return id end}
function consume_item() consumed = consumed + 1 end
-- Simulate the base manager's earlier on_game_load callback capturing clear.
CreateTimeEvent(0, "release_item", release_item_manager.clear)
CreateTimeEvent(0, "unrelated_quest", consume_item)
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
assert(not timers["0release_item"], "remove an already-queued original purge callback")
assert(timers["0unrelated_quest"], "leave other timers intact")
local guarded = release_item_manager.clear
for i=1,100 do assert(release_item_manager.clear() == true) end
assert(purged == 0, "dropped items have no age-based deletion")
local artefact_guard = grok_artefact_despawner.delete_artefacts
local inventory_guard = release_npc_inventory.clean_npc_inv
grok_artefact_despawner.delete_artefacts(7); release_npc_inventory.clean_npc_inv(9)
assert(artefacts == 0 and npc_items == 0, "floor artefacts and persistent NPC inventory are not age-purged")
for i=1,10 do install() end
assert(guarded == release_item_manager.clear, "item guard is idempotent")
assert(artefact_guard == grok_artefact_despawner.delete_artefacts and inventory_guard == release_npc_inventory.clean_npc_inv)
-- The base callback can also run after ours; it then captures the guard.
CreateTimeEvent(0, "release_item", release_item_manager.clear)
assert(timers["0release_item"]() == true and purged == 0)
release_item_manager.clear = function() purged = purged + 1; return false end
CreateTimeEvent(0, "release_item", release_item_manager.clear)
callbacks.on_game_load()
assert(not timers["0release_item"] and release_item_manager.clear() == true)
grok_artefact_despawner.delete_artefacts = function(id) artefacts = artefacts + id; return id end
callbacks.on_game_load(); grok_artefact_despawner.delete_artefacts(7); assert(artefacts == 0)
timers["0unrelated_quest"](); assert(consumed == 1)
cooperative = false
assert(release_item_manager.clear() == false and purged == 1,
       "single-player retains its original purge policy")
assert(grok_artefact_despawner.delete_artefacts(7) == 7 and artefacts == 7)
assert(release_npc_inventory.clean_npc_inv(9) == 9 and npc_items == 9)
''')
print("Actual dropped-item guard: old/new queued callbacks, reload replacement, consumption and unrelated timers PASS")

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

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
cooperative = true; spawned = 0; unregistered = {}; callbacks = {}
function netcoop_enabled() return cooperative end
function printf() end
function RegisterScriptCallback(kind, fn) callbacks[kind] = fn end
function UnregisterScriptCallback(kind, fn) unregistered[#unregistered + 1] = {kind, fn} end
local function spawn() spawned = spawned + 1 end
night_mutants = {try_to_spawn = spawn}
guards_spawner = {spawn_guard = spawn}
sim_squad_bounty = {try_spawn = spawn}
tasks_fate = {spawn_target = spawn}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
night_mutants.try_to_spawn(); guards_spawner.spawn_guard(); sim_squad_bounty.try_spawn()
assert(spawned == 0, "periodic spawners add nobody")
assert(#unregistered == 2 and unregistered[1][1] == "actor_on_update", "registered update callbacks removed")
tasks_fate.spawn_target(); assert(spawned == 1, "quest spawns unchanged")
local off = night_mutants.try_to_spawn
install(); assert(night_mutants.try_to_spawn == off and #unregistered == 2, "idempotent")
''')
print("Actual spawner guard: night mutants, base guards and bounty squads off, quest spawns unchanged PASS")

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
cooperative = true; callbacks = {}
function netcoop_enabled() return cooperative end
function printf() end
function RegisterScriptCallback(kind, fn) callbacks[kind] = fn end
local levels = {[10] = 1, [11] = 1, [20] = 2}
function game_graph() return {vertex = function(_, id) return {level_id = function() return levels[id] end} end} end
smart_terrain = {se_smart_terrain = {target_precondition = function(self, squad) return true end}}
sim_squad_scripted = {sim_squad_scripted = {target_precondition = function(self, squad) return true end}}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
local smart = smart_terrain.se_smart_terrain
local here, there, squad = {m_game_vertex_id = 11}, {m_game_vertex_id = 20}, {m_game_vertex_id = 10}
assert(smart.target_precondition(here, squad), "a target on the squad's map stays available")
assert(not smart.target_precondition(there, squad), "a target on another map is refused")
assert(not sim_squad_scripted.sim_squad_scripted.target_precondition(there, squad), "squad targets too")
local guarded = smart.target_precondition
install(); assert(smart.target_precondition == guarded, "idempotent")
cooperative = false
assert(smart.target_precondition(there, squad), "single-player keeps cross-map travel")
''')
print("Actual squad map guard: generic targets on other maps refused in coop, single-player unchanged PASS")

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
cooperative = true; callbacks = {}; released = {}; calls = {}; now = 0
function netcoop_enabled() return cooperative end
function printf() end
function time_global() return now end
function RegisterScriptCallback(kind, fn) callbacks[kind] = fn end
function AddUniqueCall(fn) calls[#calls + 1] = fn end
getFS = function() return {update_path = function() return "cluster.ltx" end} end
io = {open = function() return {close = function() end} end}
local names = {[1] = "k00_marsh", [2] = "l01_escape"}
function game_graph() return {vertex = function(_, gv) return {level_id = function() return gv end} end} end
squad_objects = {}
function alife() return {level_name = function(_, id) return names[id] end, object = function(_, id) return squad_objects[id] end} end
level = {name = function() return "k00_marsh" end}
store = {}
alife_storage_manager = {get_state = function() return store end}
story = {[30] = true}
function get_object_story_id(id) return story[id] end
function alife_release_id(id) released[#released + 1] = id end
function alife_release(se) released[#released + 1] = se.id end
function squad(id, gv, members)
    return {id = id, m_game_vertex_id = gv, squad_members = function()
        local i = 0
        return function() i = i + 1; return members[i] and {id = members[i]} end
    end}
end
SIMBOARD = {start_position_filled = false, squads = {}}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
assert(#released == 0 and #calls == 2, "a new world waits for its population (and online smarts get their updates)")
-- As in GAMMA: SIMBOARD.squads maps id -> true, the objects come from alife.
squad_objects = {[10] = squad(10, 1, {11, 12}), [20] = squad(20, 2, {21, 22}), [30] = squad(30, 2, {31})}
SIMBOARD.squads = {[10] = true, [20] = true, [30] = true}
SIMBOARD.start_position_filled = true
now = 6000
assert(calls[2]() == true)
local set = {}
for _, id in ipairs(released) do set[id] = true end
assert(set[20] and set[21] and set[22], "a generic squad of another map is released")
assert(not set[10] and not set[11] and not set[30] and not set[31], "own map and story squads stay")
local count = #released
install(); assert(#released == count, "once per world")
''')
print("Actual cluster population split: other maps' generic squads released once, own map and story squads kept PASS")
