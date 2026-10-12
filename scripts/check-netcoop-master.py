"""World master schedules on a location server (actual netcoop_master, Lua 5.1):
the engine's line is parsed exactly, malformed lines are not trusted, the
weather cycle switches at the master's transition, events run only inside
their window with the real seconds elapsed, and GAMMA's pre-blowout delta is
aligned with the master's next event."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
m = lua.table()
lua.execute("local env=...; setfenv(assert(loadstring(select(2,...))), setmetatable(env,{__index=_G}))()",
            m, (root / "server/netcoop_master.script").read_text(encoding="utf-8"))
g = lua.globals()

s, required = m.state("0")
assert s is None and required is False
s, required = m.state("2")
assert s is None and required is True
for bad in ("1", "1 x 10|-|-|-", "1 100 0|-|-|-", "1 100 10|-|-", "1 100 10|a b|-|-", "1 100 10|-|E 5 3|-"):
    s, required = m.state(bad)
    assert required is True and (s is None or s.emission is None), bad
line = "1 7200000 10.0000|W1 clear rain 7000000 10600000|EM 9000000 11220000|PS 30000000 31030000"
s, required = m.state(line)
assert required and s.world_ms == 7200000 and s.scale == 10
assert s.weather.source == "clear" and s.weather.target == "rain"
assert m.weather_cycle(s) == "rain"
s.world_ms = 6999999
assert m.weather_cycle(s) == "clear"
# Events: due only inside the window, elapsed in real seconds, never twice.
s.world_ms = 8999999
assert m.event_due(s, "emission") is False
s.world_ms = 9020000
due, elapsed, ident = m.event_due(s, "emission")
assert due is True and abs(elapsed - 2.0) < 1e-9 and ident == "EM"
assert m.event_due(s, "emission", "EM") is False
s.world_ms = 11220000
assert m.event_due(s, "emission") is False
assert m.event_due(s, "psi_storm") is False
# GAMMA's manager: _delta = time since its last event + time until the master's.
lua.execute('''
game = {get_game_time = function() return {diffSec = function(_, other) return 500 end} end}
mgr = {last_surge_time = {}}
''')
s.world_ms = 7000000
m.align_manager(g.mgr, "last_surge_time", s, "emission")
assert g.mgr._delta == 500 + 2000, g.mgr._delta
# Without an engine function a single server keeps GAMMA's schedules.
assert m.governs() is False
g.netcoop_master_state = lua.eval('function() return "2" end')
assert m.governs() is True
print("PASS world master state: exact parse, malformed lines rejected, weather switch, event windows, pre-blowout alignment")
