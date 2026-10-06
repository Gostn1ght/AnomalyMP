"""Personal PDA (owner 2026-10-06): the actual netcoop_pda (client) and
netcoop_pda_store (server) scripts. A PAW pin is placed without ALife, saved
to the character in chunks and restored on another client; another character
does not get it."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
overlay = root / "scripts/netcoop-overlay"


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
    tick = 0
    function time_global() return tick end
    function printf() end
    local V = {}
    V.__index = V
    function vector() return setmetatable({x = 0, y = 0, z = 0}, V) end
    function V:set(x, y, z) self.x, self.y, self.z = x, y, z return self end
    clsid = {script_zone = 77}
    level = {name = function() return "k00_marsh" end, object_by_id = function() return nil end}
    db = {actor = nil}
    spots = {}
    function netcoop_map_position_set(id, x, y, z, lvl) spots[id] = {x, y, z, lvl} end
    function netcoop_map_position_clear(id) spots[id] = nil end
    function netcoop_pure_client() return true end
    callbacks = {}
    function RegisterScriptCallback(name, f) callbacks[name] = f end
    sent = {}
    function netcoop_command(text) sent[#sent + 1] = text end
    -- A minimal PAW: its pin path as in tasks_placeable_waypoints.
    tasks_placeable_waypoints = setmetatable({pins = {}}, {__index = _G})
    -- As PAW's own load_state: pins come from the saved pawsys.
    function tasks_placeable_waypoints.load_state(data) tasks_placeable_waypoints.pins = data.pawsys.pins end
    function tasks_placeable_waypoints.show_all_pins() end
    local paw = tasks_placeable_waypoints
    setfenv(1, paw)
    ''')
    return lua


def load(lua, rel, name):
    g = lua.globals()
    g[name] = lua.table()
    lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
                g[name], (overlay / rel).read_bytes().decode("cp1251"))


# Server side with a shared store.
server = LuaRuntime(unpack_returned_tuples=True)
store = {}
server.globals().netcoop_store_read = lambda b, k: store.get((b, k), "")
def swap(b, k, old, new):
    if store.get((b, k), "") != old:
        return False
    store[(b, k)] = new
    return True
server.globals().netcoop_store_swap = swap
server.execute(r'''
chars = {[1] = "anna_1", [2] = "boris_1"}
function netcoop_actor_character(id) return chars[id] or "" end
outbox = {}
function netcoop_send_to_actor(id, ch, data) outbox[#outbox + 1] = {id, ch, data} end
''')
load(server, "server/netcoop_pda_store.script", "netcoop_pda_store")

# Client 1 (Anna): place a pin through PAW's own call, then save.
c1 = runtime()
load(c1, "client/netcoop_pda.script", "netcoop_pda")
c1.execute(r'''
netcoop_pda.on_game_start()
local paw = tasks_placeable_waypoints
local pos = vector():set(120.5, 2, -310.25)
local se = paw.alife_create("script_zone", pos, 4567, 89)   -- PAW: register_script_zone
assert(se and se.id >= 64000, "a pin id without ALife")
assert(spots[se.id] and spots[se.id][4] == "k00_marsh", "the engine knows the pin position")
assert(paw.alife_object(se.id):name() == "paw_pin_" .. se.id, "PAW finds its pin object")
paw.pins[se.id] = {id = se.id, name = "Тайник у вышки", icon = "bwhr_loot", text = "мой тайник"}
pin_id = se.id
netcoop_pda.receive("1/1|")            -- the server had nothing saved yet
tick = 6000; callbacks.actor_on_update()
assert(#sent >= 1, "saved to the server")
''')
for text in list(c1.globals().sent.values()):
    server.globals().netcoop_pda_store.command(1, text[len("pda "):])
assert store.get(("pda", "anna_1")), "stored for Anna's character"

# Client 2 (Anna on another computer): asks, gets the chunks back.
c2 = runtime()
load(c2, "client/netcoop_pda.script", "netcoop_pda")
c2.execute("netcoop_pda.on_game_start(); tick = 6000; callbacks.actor_on_update()")
assert c2.globals().sent[1] == "pda get"
server.execute("outbox = {}")
server.globals().netcoop_pda_store.command(1, "get")
for msg in list(server.globals().outbox.values()):
    assert msg[1] == 1 and msg[2] == "pda"
    c2.globals().netcoop_pda.receive(msg[3])
pin_id = c1.globals().pin_id
c2.execute(r'''
local pin = tasks_placeable_waypoints.pins[%d]
assert(pin and pin.name == "Тайник у вышки" and pin.icon == "bwhr_loot", "the pin came back")
assert(spots[%d] and spots[%d][1] == 120.5 and spots[%d][3] == -310.25, "at the same place")
''' % (pin_id, pin_id, pin_id, pin_id))

# Boris (another character) gets nothing of Anna's.
server.execute("outbox = {}")
server.globals().netcoop_pda_store.command(2, "get")
assert list(server.globals().outbox.values())[0][3] == "1/1|", "another character's PDA is empty"

# Removing a pin clears its map position.
c1.execute("tasks_placeable_waypoints.alife_release({id = pin_id}); assert(not spots[pin_id])")
print("PDA: PAW pins without ALife, saved per character in chunks, restored on another client, private to the character PASS")
