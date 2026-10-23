"""The world master's weather on a location (owner 2026-10-23): the actual
block of netcoop_server_compat. A cycle, a preset of a cycle (the
administrator's debug menu / weather editor) and an unlisted weather are
shown as the master keeps them; a short transition switches at once; GAMMA's
own reselect never leaves the master's weather."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
text = (root / "scripts/netcoop-overlay/server/netcoop_server_compat.script").read_text(encoding="utf-8")
a = text.index("-- Location cluster (doc 43 J01-J03)")
b = text.index("local function server_world_tick()", a)
block = text[a:b] + "\nreturn apply_master_weather\n"

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
game = {CTime = function() return {} end,
        get_game_time = function() return {diffSec = function() return 7200 end} end}
os = {time = function() return 12345 end}
function time_global() return 777 end
function printf() end
function random_key_table(t) local keys = {} for k in pairs(t) do keys[#keys + 1] = k end table.sort(keys) return keys[1] end
set = {}
level = {set_weather = function(name, now) set[#set + 1] = {name = name, now = now} end}
netcoop_master = {}
function netcoop_master.weather_cycle(s) return s.world_ms >= s.weather.transition and s.weather.target or s.weather.source end
selects = {}
wm = {presets = {clear = {w_clear1 = true, w_clear2 = true}, rain = {w_rain1 = true, w_rain2 = true}}}
function wm:select_weather(now)
    selects[#selects + 1] = {cycle = self.cycle, preset = self.preset, now = now, transition = self.transition_period}
    self.weather_file = self.preset
end
function master(id, target, transition_s)
    return {world_ms = 1000, scale = 10, weather = {id = id, source = "clear", target = target,
            transition = 1000, settled = 1000 + transition_s * 1000}}
end
''')
apply = lua.execute(block)
g = lua.globals()

# The director's cycle with a transition.
apply(g.wm, lua.eval('master("W1", "rain", 3600)'))
s = lua.eval("selects[1]")
assert (s.cycle, s.now, s.transition) == ("rain", False, True), (s.cycle, s.now, s.transition)
assert g.weather_forced is False
apply(g.wm, lua.eval('master("W1", "rain", 3600)'))
assert len(lua.eval("selects")) == 1, "the same weather is applied once"

# The administrator's preset "now": its cycle, that very preset, at once.
apply(g.wm, lua.eval('master("W2", "w_rain2", 1)'))
s = lua.eval("selects[2]")
assert (s.cycle, s.preset, s.now, s.transition) == ("rain", "w_rain2", True, False)
assert g.weather_forced is True, "clients switch at once"
# GAMMA's hourly reselect picked another preset: the master's comes back,
# as a transition this time.
g.wm.preset = "w_rain1"
apply(g.wm, lua.eval('master("W2", "w_rain2", 1)'))
s = lua.eval("selects[3]")
assert (s.preset, s.now) == ("w_rain2", False)

# A big map's "_large" variant belongs to the plain preset's cycle.
apply(g.wm, lua.eval('master("W3", "w_clear2_large", 600)'))
s = lua.eval("selects[4]")
assert (s.cycle, s.preset) == ("clear", "w_clear2")

# A weather no cycle lists (the weather editor's own): set as is.
apply(g.wm, lua.eval('master("W4", "editor_sky", 1)'))
w = lua.eval("set[1]")
assert (w.name, w.now) == ("editor_sky", True) and g.wm.weather_file == "editor_sky"
apply(g.wm, lua.eval('master("W4", "editor_sky", 1)'))
assert len(lua.eval("set")) == 1
g.wm.weather_file = "w_clear1"
apply(g.wm, lua.eval('master("W4", "editor_sky", 1)'))
assert len(lua.eval("set")) == 2 and lua.eval("set[2]").now is False
print("PASS master weather on a location: cycle, preset with its cycle, _large, unlisted weather, now, kept against GAMMA's reselect")
