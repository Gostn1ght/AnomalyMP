"""Cluster weather (doc 43 J01-J03): the actual block of netcoop_server_compat
in two Lua VMs; different weather histories, the same game hour -> the same cycle."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
text = (root / "scripts/netcoop-overlay/server/netcoop_server_compat.script").read_text(encoding="utf-8")
a = text.index("-- Location cluster (doc 43 J01-J03)")
b = text.index("local function server_world_tick()", a)
block = text[a:b] + "\nreturn install_cluster_weather, hour_seed, cluster_hour\n"

def server(start_cycle, history):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
seconds = 0
game = {CTime = function() return {} end,
        get_game_time = function() return {diffSec = function() return seconds end} end}
getFS = function() return {update_path = function() return "cluster.ltx" end} end
io = {open = function() return {close = function() end} end}
os = {time = function() return 12345 end}
function time_global() return 777 end
local graph = {clear = {"clear", "partly", "cloudy"}, partly = {"clear", "partly", "cloudy", "rain"},
               cloudy = {"partly", "cloudy", "rain", "storm"}, rain = {"cloudy", "rain", "storm"}, storm = {"rain", "cloudy"}}
wm = {}
function wm:get_next_weather_cycle(current)
    local next = graph[current] or graph.clear
    return next[math.random(#next)]
end
''')
    install, hour_seed, cluster_hour = lua.execute(block)
    g = lua.globals()
    install(g.wm)
    # Different local history: burn random numbers like a server that ran longer.
    for _ in range(history):
        lua.eval("math.random()")
    return lua, g

results = []
for start, history in (("storm", 3), ("clear", 500)):
    lua, g = server(start, history)
    cycles = []
    for hour in (10, 11, 12, 40, 41):
        g.seconds = hour * 3600 + 1200
        cycles.append(lua.eval("wm:get_next_weather_cycle('" + start + "')"))
    results.append(cycles)
assert results[0] == results[1], results
assert len(set(results[0])) > 1, "the weather still changes over time"
print("Cluster weather: the same cycle on every server for the same game hour, whatever the history PASS")
