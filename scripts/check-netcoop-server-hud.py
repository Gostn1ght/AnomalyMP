"""Run the real dedicated HUD adapter; native UI must never be dereferenced."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/netcoop-overlay/server/netcoop_server_hud.script").read_text(encoding="ascii")
lua = LuaRuntime()
lua.execute('''
client = false
function netcoop_pure_client() return client end
function printf() end
function get_hud() error("native server UI must not be called") end
''')
lua.execute(source)
lua.execute('''
on_game_start()
local hud = get_hud()
assert(hud:GetCustomStatic("test") == nil)
local caption = hud:AddCustomStatic("test", true)
assert(caption == hud:AddCustomStatic("test", true))
assert(hud:GetCustomStatic("test") == caption)
caption:wnd():TextControl():SetText("quest notification")
caption:wnd():SetTextureColor(0xffffffff)
caption.m_endTime = 100
hud:RemoveCustomStatic("test")
assert(hud:GetCustomStatic("test") == nil)
hud:HideActorMenu();hud:HidePdaMenu();hud:update_fake_indicators(1, 0.5)
assert(hud:CurrentItemAtCell() == nil and hud:GetWindow() == nil)
local player_hud = {}
client = true
get_hud = function() return player_hud end
on_game_start()
assert(get_hud() == player_hud, "client HUD is preserved")
''')
print("PASS actual server HUD: captions and text calls avoid native UI; remove/reuse work; client HUD preserved")
