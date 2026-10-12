"""Vehicles (doc 100): the actual netcoop_vehicle_client prompts and the
server's car trunks (netcoop_vehicles.script) with host stubs."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
client = (root / "scripts/netcoop-overlay/client/netcoop_vehicle_client.script").read_text(encoding="ascii")
server = (root / "scripts/netcoop-overlay/server/netcoop_vehicles.script").read_text(encoding="ascii")

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
game = {translate_string = function(id) return "<" .. id .. ">" end}
key_bindings = {kUSE = 1, kJUMP = 2, kTORCH = 3, kDETECTOR = 4}
names = {"F", "SPACE", "L", "O"}
function bind_to_dik(b) return b end
function dik_to_keyname(d) return string.lower(names[d]) end
function class(name) _G[name] = {} return function() end end
CUIScriptWnd = {}
''')
lua.execute(client)
lua.execute(r'''
assert(prompt_text("driver", 0) == "[F]  <st_netcoop_car_drive>")
assert(prompt_text("passenger", 0) == "[F]  <st_netcoop_car_sit>")
assert(prompt_text("trunk", 0) == "[F]  <st_netcoop_car_trunk>")
assert(prompt_text("taken", 0) == "<st_netcoop_seat_taken>", "a taken seat says so, no key")
assert(prompt_text("", 0) == nil)
local hint = prompt_text("seated_driver", 1000)
assert(hint:find("%[SPACE%] <st_netcoop_car_handbrake>") and hint:find("%[L%] <st_netcoop_car_lights>"), hint)
assert(prompt_text("seated_driver", 8999) ~= nil and prompt_text("seated_driver", 9001) == nil, "controls for 8 s")
assert(prompt_text("", 9100) == nil)
assert(prompt_text("seated", 10000) == "[F]  <st_netcoop_car_exit>", "a new seat shows the hint again")
''')

srv = LuaRuntime(unpack_returned_tuples=True)
srv.execute(r'''
state, objects, anchors, released, logs, callbacks = {}, {}, {}, {}, {}, {}
next_id = 500
alife_storage_manager = {get_state = function() return state end}
function vector() local v = {} function v:set(x, y, z) self.x, self.y, self.z = x, y, z return self end return v end
function printf(fmt, ...) logs[#logs + 1] = fmt end
function IsInvbox(_, cls) return cls == "box" end
function alife_object(id) return objects[id] end
function alife_create(section, pos, lv, gv)
    next_id = next_id + 1
    local se = {id = next_id, section = section, pos = pos}
    function se:clsid() return "box" end
    objects[se.id] = se
    return se
end
function alife_release(se) released[#released + 1] = se.id; objects[se.id] = nil end
online = {}
function alife() return {set_switch_online = function(_, id, v) online[id] = v end, set_switch_offline = function() end} end
function netcoop_box_anchor(box, car) anchors[box] = car end
function netcoop_pure_client() return false end
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
car = {position = function() return {x = 10, y = 5, z = 20} end, level_vertex_id = function() return 1 end,
       game_vertex_id = function() return 2 end, section = function() return "veh_niva" end}
level = {object_by_id = function(id) return id == 42 and car or nil end}
''')
srv.execute(server)
srv.execute(r'''
on_game_start()
local box = trunk_box(42)
assert(box == 501 and objects[501].section == "netcoop_car_trunk", "a trunk is made on first use")
assert(objects[501].pos.y == -45, "under the map, below the car")
assert(anchors[501] == 42 and online[501] == true, "anchored to the car, always online")
assert(trunk_box(42) == 501, "the same trunk next time")
assert(trunk_box(7) == 0, "no car, no trunk")
callbacks.server_entity_on_unregister({id = 42})
assert(released[1] == 501 and state.netcoop_car_trunks[42] == nil, "a car that is gone takes its trunk")
assert(trunk_box(42) == 502, "a new trunk for a car seen again")
''')
print("Vehicles: seat/trunk/taken prompts, driver controls hint for 8 s, trunk made once under the car, anchored, always online, released with the car PASS")
