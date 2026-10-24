"""Marked stashes are filled on the server when a player comes near (owner
2026-10-24, spec 5.1): GAMMA filled them from the box's use callback, which a
client's opening never ran on the server. The actual stash_fill_update of
netcoop_server_compat, with treasure_manager, players and boxes stubbed."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
text = (root / "scripts/netcoop-overlay/server/netcoop_server_compat.script").read_text(encoding="utf-8")
start = text.index("local STASH_FILL_NEAR, STASH_FILL_EVERY")
end = text.index("\nend\n", text.index("local function stash_fill_update()")) + len("\nend\n")
assert "stash_fill_update();" in text, "the server loop calls it"

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
now = 0
function time_global() return now end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
local V = {}
V.__index = V
function V:distance_to(o) return math.abs(self.x - o.x) end
local function pos(x) return setmetatable({x = x}, V) end
objects = {}
function obj(id, x, name)
  local o = {_id = id, _pos = pos(x), _name = name}
  function o:id() return self._id end
  function o:position() return self._pos end
  function o:alive() return true end
  function o:character_name() return self._name end
  objects[id] = o
  return o
end
level = {object_by_id = function(id) return objects[id] end}
player_ids = "1"
function netcoop_players() return player_ids end
filled = {}
treasure_manager = {caches = {}, try_spawn_treasure = function(box)
  filled[#filled + 1] = box:id(); treasure_manager.caches[box:id()] = true end}
function with_player_bound(fn, ...) return pcall(fn, ...) end
''')
lua.execute(text[start:end] + "\nfill = stash_fill_update")
lua.execute(r'''
obj(1, 0, "Alpha")
obj(100, 10, "box near")
obj(101, 40, "box far")
treasure_manager.caches[100] = "bread,medkit"
treasure_manager.caches[101] = "vodka"
treasure_manager.caches[102] = "ammo"   -- its box is not online here
treasure_manager.caches[103] = true     -- already filled
fill()
assert(#filled == 1 and filled[1] == 100, "only the marked stash near a player")
now = 1000; fill(); assert(#filled == 1, "checked every 2 s")
now = 2500; fill(); assert(#filled == 1, "a filled stash is not filled again")
objects[1]._pos.x = 38
now = 5000; fill(); assert(#filled == 2 and filled[2] == 101, "the far one when he comes near")
player_ids = ""
treasure_manager.caches[104] = "bread"; obj(104, 38, "box")
now = 8000; fill(); assert(#filled == 2, "no player, no filling")
''')
print("PASS stash fill: a marked stash is filled when a player comes within 15 m, once, only online boxes, every 2 s")
