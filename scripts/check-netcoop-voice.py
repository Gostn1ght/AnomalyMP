"""Voice chat and walkie-talkies: the Lua sides (actual netcoop_voice_ui and
the 'radio' command of netanomaly_server) and the engine wiring as text.
Radio window: frequency clamped to [netcoop_voice] min/max in its steps,
on/off, the engine told (freq, on, radio in inventory), the server told;
server: the setting is kept with the character, a bad frequency is refused,
the engine gets the stored setting; 'radio get' answers the client. Engine:
voice keys are bindable actions (unbound by default) in Controls, one message
both ways with client and server dispatch, codecs built before MSBuild."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
ov = root / "scripts/netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
cfgs = {min_freq = 3000, max_freq = 5995, freq_step = 5, radio_items = "walkie, sl_radio"}
ini_sys = {r_float_ex = function(_, s, k) return s == "netcoop_voice" and tonumber(cfgs[k]) or nil end,
           r_string_ex = function(_, s, k) return s == "netcoop_voice" and cfgs[k] or nil end}
game = {translate_string = function(id) return "<" .. id .. ">" end}
local_calls, commands, msgs = {}, {}, {}
function netcoop_voice_radio_local(f, o, h) local_calls[#local_calls + 1] = {f, o, h} end
function netcoop_command(c) commands[#commands + 1] = c end
actor_menu = {set_msg = function(_, m) msgs[#msgs + 1] = m end}
inventory = {}
db = {actor = {object = function(_, s) return inventory[s] end, id = function() return 7 end}}
function netcoop_pure_client() return true end
callbacks = {}
function RegisterScriptCallback(n, f) callbacks[n] = f end
tg = 0
function time_global() return tg end
-- a minimal window class for the radio dialog
function class(name) return function(base)
    local c = {}
    c.__index = c
    setmetatable(c, {__call = function(cls, ...) local o = setmetatable({}, cls); o:__init(...); return o end})
    _G[name] = c
end end
function super() end
CUIScriptWnd = {OnKeyboard = function() return false end}
function Frect() return {set = function(self) return self end} end
function vector2() return {set = function(self) return self end} end
function widget()
    local w = {text = ""}
    function w:TextControl() return {SetText = function(_, t) w.text = t end} end
    function w:SetWndPos() end; function w:SetWndSize() end
    return w
end
function CScriptXmlInit() return {ParseFile = function() end, InitStatic = function() return widget() end,
                                  Init3tButton = function() return widget() end} end
ui_events = {BUTTON_CLICKED = 1, WINDOW_KEY_PRESSED = 2}
DIK_keys = {DIK_ESCAPE = 1}
handlers = {}
''')
g.netcoop_voice_ui = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_voice_ui, (ov / "client/netcoop_voice_ui.script").read_text(encoding="utf-8"))
lua.execute(r'''
-- window helpers the class uses
function netcoop_radio_wnd.SetWndRect() end
function netcoop_radio_wnd.SetAutoDelete() end
function netcoop_radio_wnd.Register() end
function netcoop_radio_wnd.AddCallback(self, id, ev, fn) handlers[id] = fn end
function netcoop_radio_wnd.ShowDialog(self) self.shown = true end
function netcoop_radio_wnd.HideDialog(self) self.shown = false end
netcoop_voice_ui.on_game_start()
''')
v = g.netcoop_voice_ui
# No radio: first update tells the engine "no radio", asks the server.
g.callbacks.actor_on_first_update()
assert tuple(g.local_calls[1].values()) == (0, False, False) and g.commands[1] == "radio get"
# The server's stored setting arrives.
v.receive("4210 1")
assert tuple(g.local_calls[2].values()) == (4210, True, False)
# The menu item only for the owner's walkie.
assert v.menu_radio(lua.eval("{parent = function() return {id = function() return 7 end} end}")) == "<st_voice_radio_menu>"
assert v.menu_radio(lua.eval("{parent = function() return nil end}")) is None
# A radio in the inventory (any listed section) is noticed within a second.
lua.execute("inventory.sl_radio = {}; tg = 1500")
g.callbacks.actor_on_update()
assert tuple(g.local_calls[len(g.local_calls)].values()) == (4210, True, True)
# Window: tune within limits, power toggle; every change goes to the server.
v.open_radio(None)
h = g.handlers  # rb1 -1.00, rb2 -step, rb3 +step, rb4 +1.00, rb5 power, rb6 close
for _ in range(40): h.rb4(None)
assert g.commands[len(g.commands)] == "radio 5995 1"
for _ in range(40): h.rb1(None)
assert g.commands[len(g.commands)] == "radio 3000 1"
h.rb3(None); h.rb3(None)
assert g.commands[len(g.commands)] == "radio 3010 1"
h.rb5(None)
assert g.commands[len(g.commands)] == "radio 3010 0"
assert tuple(g.local_calls[len(g.local_calls)].values()) == (3010, False, True)
v.tip("st_voice_no_radio")
assert g.msgs[len(g.msgs)] == "<st_voice_no_radio>"

# Server command 'radio'.
srv = (ov / "server/netanomaly_server.script").read_text(encoding="utf-8")
block = srv[srv.index('	if cmd == "radio" then'):srv.index('	-- PDA network: contacts, general channel, chats')]
lua.execute(r'''
set_calls, sent = {}, {}
function netcoop_voice_radio_set(id, f, o) set_calls[#set_calls + 1] = {id, f, o} end
function netcoop_send_to_actor(id, ch, d) sent[#sent + 1] = {id, ch, d} end
db.storage = {}
function server_actor(id) return id == 9 and {} or nil end
''')
run = lua.eval("function(src) return loadstring('return function(cmd, args, entity_id) ' .. src .. ' return \"-\" end')() end")(block)
assert run("radio", "4500 1", 9) == ""
assert lua.eval("db.storage[9].pstor.netcoop_radio") == "4500 1"
assert tuple(g.set_calls[1].values()) == (9, 4500, True)
run("radio", "9999 1", 9)          # out of range: kept as it was
assert lua.eval("db.storage[9].pstor.netcoop_radio") == "4500 1"
run("radio", "get", 9)
assert tuple(g.sent[1].values()) == (9, "radio", "4500 1")
assert run("radio", "get", 5) == ""  # no Actor on the server: nothing
assert run("other", "", 9) == "-"

# Engine wiring.
src = root / "src"
ctl_h = (src / "xrGame/xr_level_controller.h").read_text(encoding="utf-8", errors="replace")
ctl = (src / "xrGame/xr_level_controller.cpp").read_text(encoding="utf-8", errors="replace")
for name, act in (("voice_near", "kVOICE_NEAR"), ("voice_radio", "kVOICE_RADIO"), ("voice_range", "kVOICE_RANGE")):
    assert act in ctl_h and f'{{"{name}", {act}, _both }}' in ctl
kb = (ov / "client/configs/ui/ui_keybinding.xml").read_bytes().decode("cp1251")
assert all(f'exe="{n}"' in kb for n in ("voice_near", "voice_radio", "voice_range")) and "kb_grp_voice" in kb
assert "M_NETCOOP_VOICE" in (src / "xrServerEntities/xrMessages.h").read_text(encoding="utf-8", errors="replace")
assert "netcoop::client_on_voice(*P)" in (src / "xrGame/Level_network_messages.cpp").read_text(encoding="utf-8", errors="replace")
assert "netcoop::server_on_voice(this, CL, P)" in (src / "xrGame/xrServer.cpp").read_text(encoding="utf-8", errors="replace")
inp = (src / "xrGame/level_input.cpp").read_text(encoding="utf-8-sig", errors="replace")
press = inp[inp.index("void CLevel::IR_OnKeyboardPress"):]
assert press.index("client_voice_key(get_binded_action(key), true)") < press.index("m_rp_index >= 0")  # works in RP poses
assert "client_voice_key(get_binded_action(key), false)" in inp
wf = (root / ".github/workflows/lostzone-dx11.yml").read_text(encoding="utf-8")
assert wf.index("Build voice codecs") < wf.index("Build DX11 on GitHub Actions")
proj = (src / "xrSound/xrSound.vcxproj").read_text(encoding="utf-8-sig")
assert proj.count("opus.lib;speexdsp.lib") == proj.count("<Lib>") >= 1 and 'Include="SoundVoice.cpp"' in proj
for role in ("client", "server"):
    ltx = (ov / f"{role}/configs/mod_system_zzzzzzzz_netcoop_voice.ltx").read_text(encoding="utf-8")
    assert "[netcoop_voice]" in ltx and "radio_items = walkie" in ltx and "netcoop_voice_ui.open_radio" in ltx
for lang in ("rus", "eng"):
    t = (ov / f"client/configs/text/{lang}/st_netcoop.xml").read_bytes().decode("cp1251")
    used = set(re.findall(r'"(st_voice_[a-z_]+)"', (ov / "client/netcoop_voice_ui.script").read_text(encoding="utf-8") +
                         (src / "xrGame/netcoop_voice.inc").read_text(encoding="utf-8")))
    used |= {"kb_grp_voice", "kb_voice_near", "kb_voice_radio", "kb_voice_range"}
    missing = [k for k in used if f'id="{k}"' not in t]
    assert not missing, (lang, missing)
print("netcoop voice: OK")
