"""Starting kit (owner's log 2026-10-10: "loadout rejected" five times, then
only a PDA): the kit check is freeplay's points, counts and economy, not the
60 backpack cells GAMMA's mandatory items alone fill half of; the starting
ammo is freeplay's whole allowance. The craft tooltip mod's ini is given to
it before the loadout picker shows tooltips (actual craft_tooltip_ready from
netcoop_login_ui, Lua 5.1, against a stand-in with GAMMA's local upvalue)."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
chars = (root / "src/xrGame/netcoop_characters.inc").read_text(encoding="utf-8", errors="replace")
validate = chars[chars.index("static bool character_validate_loadout("):chars.index("static bool character_select(")]
assert "storage_capacity" not in validate and "storage_section_cost" not in validate
assert "used > budget" in validate and "++selected[item] > available" in validate
spawn = chars[chars.index("void server_character_spawn_items("):chars.index("// Refuse the whole checkpoint")]
assert "storage_capacity" not in spawn and "starter_cells" not in spawn

ui = (root / "scripts/netcoop-overlay/client/netcoop_login_ui.script").read_text(encoding="utf-8")
m = re.search(r"local function craft_tooltip_ready\(\).*?\nend\n", ui, re.S)
assert m and ui.index("pcall(craft_tooltip_ready)") < ui.index("self.creator:ShowDialog(true)")
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
function ini_file(name) return {name = name} end
local ini_craft, ini_cook
zzz_craft_use_in_tooltip_mcm = {
  getCraftableItems = function() return ini_craft.name end,
  getCookableItems = function() return ini_cook.name end,
}
''')
lua.execute(m.group(0) + "\nready = craft_tooltip_ready")
mod = g.zzz_craft_use_in_tooltip_mcm
g.ready()
assert mod.getCraftableItems() == "items\\settings\\craft.ltx" and mod.getCookableItems() == "items\\settings\\cook.ltx"
g.ready()  # already set: left as is
print("Starting kit: no backpack-cell refusal, full freeplay ammo; craft tooltip ready in the menu: PASS")
