"""Crate contents and mass (owner 2026-10-09): the actual netcoop_box_contents
script with GAMMA's xr_box spawn shape and bind_physic_object's 50 % gate.
The plan is rolled once and saved; mass = shell + real contents; the loot
drops exactly once at death whatever the stock second roll says; a failed
spawn is rolled back and GAMMA's own roll runs, never twice; ammo and
"medkit__1" weigh what the engine says; a reused id is replanned; barrels
get their shell only."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
tick = 0
function time_global() return tick end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
function netcoop_pure_client() return false end
-- Items (GAMMA-like INI).
items = {
    -- Real item sections have a cform; GAMMA's create_items skips the others.
    bandage = {inv_weight = 0.1, cform = true},
    medkit = {inv_weight = 0.5, use_condition = true, max_uses = 2, empty_weight = 0.1, cform = true},
    ammo_9x18_fmj = {inv_weight = 0.24, box_size = 30, ammo = true, cform = true},
    wpn_pm = {inv_weight = 0.8, cform = true},
    not_an_item = {inv_weight = 9},
}
ini_sys = {
    section_exist = function(_, s, extra) assert(extra == nil, "section_exist got a second value") return items[s] ~= nil end,
    line_exist = function(_, s, k) return items[s] and items[s][k] ~= nil end,
    r_float_ex = function(_, s, k) return items[s] and items[s][k] end,
    r_bool_ex = function(_, s, k, d) local v = items[s] and items[s][k] if v == nil then return d end return v end,
}
function IsItem(kind, s) return kind == "ammo" and items[s] and items[s].ammo end
-- Randomness under the test's control.
rolls = {}
math.random = function(a, b)
    local v = table.remove(rolls, 1)
    assert(v ~= nil, "unexpected random call")
    return v
end
-- World.
state = {se_object = {}}
function se_save_var(id, _, k, v) state.se_object[id] = state.se_object[id] or {}; state.se_object[id][k] = v end
function se_load_var(id, _, k) return state.se_object[id] and state.se_object[id][k] end
masses = {}
shells = {[10] = 12, [20] = 12, [30] = 25}
function netcoop_prop_shell_mass(id) return shells[id] or 0 end
function netcoop_prop_set_mass(id, m) masses[id] = m return true end
function netcoop_mass_props() return "10 20 30" end
function vector() local v = {x=0,y=0,z=0} function v:set(o) self.x, self.y, self.z = o.x, o.y, o.z return self end return v end
created, released_items, fail_at = {}, {}, nil
next_id = 1000
function alife_create_item(section, where, t)
    if fail_at and #created + 1 >= fail_at then return nil end
    if t and t.ammo then
        local out = {}
        local n = t.ammo
        while true do next_id = next_id + 1; out[#out+1] = {id=next_id, section=section, rounds=math.min(n, items[section].box_size)}; created[#created+1] = out[#out]; n = n - items[section].box_size; if n <= 0 then break end end
        return out
    end
    next_id = next_id + 1
    local e = {id = next_id, section = section}
    created[#created + 1] = e
    return e
end
function alife_release(e) released_items[#released_items + 1] = e.id return true end
function make_crate(id, name, visual, drop)
    return {id = function() return id end, name = function() return name end, get_visual_name = function() return visual end,
        position = function() return {x=0,y=0,z=0} end, level_vertex_id = function() return 1 end, game_vertex_id = function() return 2 end,
        spawn_ini = function() return {section_exist = function(_, s) return drop and s == "drop_box" end} end}
end
objects = {}
level = {object_by_id = function(id) return objects[id] end}
-- GAMMA's xr_box: spawn_items rolls counts and calls the module's create_items.
stock_spawns = 0
xr_box = {}
stock_created = 0
xr_box.create_items = function(obj, section, number, rnd) stock_created = stock_created + 1 end -- GAMMA's own spawning
xr_box.ph_item_box = {}
xr_box.ph_item_box.spawn_items = function(self, obj, who, ini)
    stock_spawns = stock_spawns + 1
    xr_box.create_items(obj, "bandage", 2, 1.0)
    xr_box.create_items(obj, "medkit__1", 1, 1.0)
    xr_box.create_items(obj, "ammo_9x18_fmj", 40, 0.5)
    xr_box.create_items(obj, "wpn_pm", 1, 1.0)
    xr_box.create_items(obj, "not_an_item", 1, 1.0)
end
function xr_box.get_box_manager() return {} end
-- bind_physic_object: the stock death callback with its 50 % gate.
stock_gate = true
bind_physic_object = {generic_physics_binder = {}}
bind_physic_object.generic_physics_binder.death_callback = function(self, victim, who)
    local ini = victim:spawn_ini()
    if ini:section_exist("drop_box") or stock_gate then xr_box.ph_item_box.spawn_items(xr_box.get_box_manager(), victim, who, ini) end
end
''')
g = lua.globals()
g.netcoop_box_contents = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_box_contents, (root / "scripts/netcoop-overlay/server/netcoop_box_contents.script").read_text(encoding="utf-8"))
lua.execute(r'''
local b = netcoop_box_contents
b.install()
-- Weights as the engine computes them.
assert(math.abs(b.item_weight({section="ammo_9x18_fmj", count=40, ammo=true}) - 0.24*40/30) < 1e-9, "ammo by rounds")
assert(math.abs(b.item_weight({section="medkit__1", count=1, ammo=false}) - (0.1 + 0.4*1/2)) < 1e-9, "one use of a medkit")
assert(math.abs(b.item_weight({section="medkit", count=1, ammo=false}) - 0.5) < 1e-9, "full medkit")

-- Crate 10, no drop_box: the 50 % gate passes (0.30), ammo roll passes (0.4).
objects[10] = make_crate(10, "crate_a", "dynamics\\box\\box_wood_01", false)
rolls = {30, 1, 1, 1, 0.4, 1}  -- gate 30/100; bandage x2; medkit__1; ammo 0.4 <= 0.5; pistol
tick = 6000; b.update()
local plan = state.se_object[10].lz_box_contents_v2
assert(plan and plan.gate and #plan.items == 5, "rolled once: 2 bandages, medkit__1, ammo, pistol")
local w = 0.2 + 0.3 + 0.24*40/30 + 0.8
assert(math.abs(plan.weight - w) < 1e-9 and math.abs(masses[10] - (12 + w)) < 1e-9, "mass = shell + contents")
-- No reroll on the next scans or after a restart; mass reapplied.
masses[10] = nil
tick = 12000; b.update()
assert(state.se_object[10].lz_box_contents_v2 == plan and masses[10] and #rolls == 0, "same plan, mass back")
-- Breaks: the stock second gate fails, the planned loot still drops, once.
stock_gate = false
bind_physic_object.generic_physics_binder.death_callback({}, objects[10], nil)
assert(#created == 6 and plan.released and masses[10] == 12, "planned loot dropped: 4 items + 2 ammo boxes; shell mass")
stock_gate = true
xr_box.ph_item_box.spawn_items({}, objects[10], nil, objects[10]:spawn_ini())
bind_physic_object.generic_physics_binder.death_callback({}, objects[10], nil)
assert(#created == 6 and stock_created == 0, "never twice, no stock reroll")

-- Crate 20: the gate fails at planning -> empty, shell mass, nothing drops.
objects[20] = make_crate(20, "crate_b", "dynamics\\box\\box_metall_01", false)
created = {}
rolls = {70}
tick = 18000; b.update(); b.update()
local p2 = state.se_object[20].lz_box_contents_v2
assert(p2 and not p2.gate and #p2.items == 0 and masses[20] == 12, "empty crate weighs its shell")
stock_gate = true
bind_physic_object.generic_physics_binder.death_callback({}, objects[20], nil)
assert(#created == 0, "an empty crate drops nothing even if the stock gate passes")

-- A spawn failure rolls back and GAMMA's own roll runs, once.
state.se_object[10] = nil; created = {}; released_items = {}; stock_spawns = 0
objects[10] = make_crate(10, "crate_c", "dynamics\\box\\box_wood_02", true) -- drop_box: no gate roll
rolls = {1, 1, 1, 0.4, 1}
fail_at = 3
local stock_rolls = {1, 1, 1, 0.4, 1}
local create_capture = 0
bind_physic_object.generic_physics_binder.death_callback({}, objects[10], nil)
assert(#released_items == 2, "the two items made before the failure were rolled back")
assert(stock_created > 0, "GAMMA's own roll spawned the fallback loot")
local p3 = state.se_object[10].lz_box_contents_v2
assert(p3.released, "marked released: the fallback is the only loot")

-- A reused id with another crate: a new plan.
fail_at = nil
objects[10] = make_crate(10, "crate_d", "dynamics\\box\\box_wood_02", true)
rolls = {1, 1, 1, 0.9, 1}
tick = 30000; b.update()
local p4 = state.se_object[10].lz_box_contents_v2
assert(p4 ~= p3 and p4.name == "crate_d" and not p4.released and #p4.items == 4, "replanned for the new crate (ammo roll failed)")

-- Barrel: empty shell mass only, no plan.
objects[30] = make_crate(30, "barrel", "dynamics\\balon\\bochka_close", false)
tick = 40000; b.update(); b.update(); b.update()
assert(masses[30] == 25 and not (state.se_object[30] and state.se_object[30].lz_box_contents_v2), "barrel: shell mass")
''')
print("Crate contents: GAMMA's roll and 50 % gate planned once and saved, mass = shell + contents, loot drops exactly once, "
      "rollback + stock fallback on failure, engine weights for ammo/multi-use, reused ids replanned, barrels shell only PASS")
