"""FDDA backpack animation online (actual install_backpack_animation from
netcoop_client_compat, run in Lua 5.1 against a stand-in of
liz_fdda_redone_backpack): the inventory arrives from the server after
actor_on_first_update, so before each opening the backpack in slot 13 is
given to the mod's own setter; without a backpack nothing is set; installs once."""
from pathlib import Path
import re
from lupa.lua51 import LuaRuntime

src = (Path(__file__).resolve().parent / "netcoop-overlay/client/netcoop_client_compat.script").read_text(encoding="utf-8")
m = re.search(r"local function install_backpack_animation\(\).*?\nend\n", src, re.S)
assert m, "install_backpack_animation not found"
assert "install_backpack_animation()" in src[m.end():], "not called"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
set_ids, opened = {}, 0
bp = {id = function() return 77 end}
slot13 = nil
db = {actor = {item_in_slot = function(_, n) if n == 13 then return slot13 end end}}
liz_fdda_redone_backpack = {
  on_item_to_slot = function(obj) set_ids[#set_ids + 1] = obj:id() end,
  try_open_backpack = function() opened = opened + 1 end,
}
''')
lua.execute(m.group(0) + "\ninstall = install_backpack_animation")
g.install(); g.install()
mod = g.liz_fdda_redone_backpack
mod.try_open_backpack()
assert g.opened == 1 and len(g.set_ids) == 0          # no backpack: nothing set
lua.execute("slot13 = bp")
mod.try_open_backpack()
assert g.opened == 2 and list(g.set_ids.values()) == [77]
print("FDDA backpack animation reads slot 13 before opening: PASS")
