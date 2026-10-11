"""Actual client PDA: no chime/read acknowledgement without an equipped device."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute('''
slot = nil
db = {actor = {item_in_slot = function(_, n) assert(n == 8); return slot end,
              id = function() return 7 end}}
sounds, commands = 0, 0
xr_sound = {set_sound_play = function() sounds = sounds + 1; return 123 end}
function netcoop_command() commands = commands + 1 end
''')
client = root / "scripts/netcoop-overlay/client/netcoop_pdanet_client.script"
lua.execute(client.read_text(encoding="utf-8"))
g.install_notification_sound()
g.install_notification_sound()  # wrapping twice must not recurse
assert g.equipped() is False
g.xr_sound.set_sound_play(7, "pda_tips")
assert g.sounds == 0
assert g.xr_sound.set_sound_play(7, "weapon_reload") == 123
assert g.sounds == 1
lua.execute('slot = {section = function() return "wpn_ak74" end}')
assert g.equipped() is False
g.xr_sound.set_sound_play(7, "pda_tips")
assert g.sounds == 1
lua.execute('slot = {section = function() return "device_pda_3" end}')
assert g.equipped() is True
g.xr_sound.set_sound_play(7, "pda_tips")
assert g.sounds == 2

# Run the actual receiver with a chat left open before unequipping the PDA.
serializer = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2,...))), setmetatable(env,{__index=_G}))()",
            serializer, (root / "scripts/netcoop-overlay/server/netcoop_transit.script").read_text(encoding="utf-8"))
lua.execute('opened = {id="c", msgs={}}; slot=nil')
value = lua.eval('{id="c", summary={id="c", unread=1}, msgs={{s=1, text="hello"}}}')
g.receive("1/1|new|" + serializer.serialize(value))
assert g.sounds == 2 and g.commands == 0
assert g.chats[1].unread == 1 and len(g.opened.msgs) == 0
lua.execute('slot = {section = function() return "device_pda" end}')
g.receive("1/1|new|" + serializer.serialize(value))
assert g.sounds == 3 and g.commands == 1 and len(g.opened.msgs) == 1
lua.execute('db.actor=nil')
assert g.equipped() is False
print("PASS actual PDA notifications: equipped slot, sound filtering, unread retained, reconnect without actor")
