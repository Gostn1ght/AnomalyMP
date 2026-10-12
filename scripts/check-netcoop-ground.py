"""Safe ground placement (doc 43 L11). Actual netcoop_ground against a stand-in
of the static level geometry: a floor at y=0, a wall at x=1.5, a steep slope
at z>3 and a hole (no floor) at x<-3. Items land on the floor, never behind the
wall, are spread instead of stacked, avoid the slope and over the hole fall
back to the AI vertex. Crate loot uses it for every item (actual
netcoop_box_contents.spawn_plan)."""
from pathlib import Path
import math
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
local V = {}
V.__index = V
function vector() return setmetatable({x = 0, y = 0, z = 0}, V) end
function V:set(x, y, z)
    if type(x) == "table" then self.x, self.y, self.z = x.x, x.y, x.z else self.x, self.y, self.z = x, y, z end
    return self
end
function V:magnitude() return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z) end
function V:normalize() local m = self:magnitude(); if m > 0 then self.x, self.y, self.z = self.x / m, self.y / m, self.z / m end; return self end

-- Static geometry: floor y=0 except a hole at x<-3, a slope (normal y 0.3) at
-- z>3, a wall plane x=1.5 (height 0..3).
rays = 0
local function hit_down(p)
    if p.x < -3 then return nil end
    if p.z > 3 then return p.y, vector():set(0.95, 0.3, 0) end
    return p.y - 0, vector():set(0, 1, 0)
end
local function hit_wall(from, dir, range)
    if dir.x == 0 then return nil end
    local t = (1.5 - from.x) / dir.x
    if t < 0 or t > range then return nil end
    local y = from.y + dir.y * t
    if y < 0 or y > 3 then return nil end
    return t
end
function ray_pick()
    local r = {}
    function r:set_position(p) self.p = vector():set(p) end
    function r:set_direction(d) self.d = vector():set(d) end
    function r:set_range(v) self.r = v end
    function r:set_flags(f) self.f = f end
    function r:query()
        rays = rays + 1
        assert(self.f == 2, "static geometry only")
        self.dist, self.n = nil, nil
        if self.d.y < -0.99 then
            local dist, n = hit_down(self.p)
            if dist and dist <= self.r then self.dist, self.n = dist, n end
        else
            self.dist = hit_wall(self.p, self.d, self.r)
            self.n = vector():set(-1, 0, 0)
        end
        return self.dist ~= nil
    end
    function r:get_distance() return self.dist or -1 end
    function r:get_normal() return self.n end
    return r
end
level = {}
function level.vertex_id(p) return 1000 + math.floor(p.x * 10) end
function level.vertex_position(id) return vector():set(-4, -2, 0) end
function printf() end
''')
ground = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            ground, (root / "server/netcoop_ground.script").read_text(encoding="cp1251"))
g.netcoop_ground = ground
V = lambda x, y, z: lua.eval("function(x,y,z) return vector():set(x,y,z) end")(x, y, z)

# One item dropped from a point 0.3 m above the floor: it rests on the floor.
p, lvid, gvid = ground.safe_point(V(0, 0.3, 0), 7, 9)
assert abs(p.y - 0.05) < 1e-6 and p.x == 0 and p.z == 0 and gvid == 9, (p.x, p.y, p.z)
# An item stuck in the air or under the floor lands on it as well.
p = ground.safe_point(V(0.2, 2.5, 0.1), 7, 9)[0]
assert abs(p.y - 0.05) < 1e-6
p = ground.safe_point(V(0.2, -0.5, 0.1), 7, 9)[0]
assert abs(p.y - 0.05) < 1e-6, p.y

# Twelve items from one crate: spread on the floor, never two on one spot,
# never behind the wall at x=1.5 (those fall back to the crate's point).
points = [ground.safe_point(V(1.2, 0.3, 0), 7, 9, i, 12)[0] for i in range(1, 13)]
for a in points:
    assert abs(a.y - 0.05) < 1e-6 and a.x < 1.5, (a.x, a.y, a.z)
spread = {(round(a.x, 3), round(a.z, 3)) for a in points if (a.x, a.z) != (1.2, 0)}
assert len(spread) >= 6, spread
for i, a in enumerate(points):
    for b in points[i + 1:]:
        if (a.x, a.z) != (1.2, 0) or (b.x, b.z) != (1.2, 0):
            assert math.hypot(a.x - b.x, a.z - b.z) > 0.2 or ((a.x, a.z) == (b.x, b.z) == (1.2, 0))

# A steep slope is not ground; over a hole there is no surface: the AI vertex.
p, lvid = ground.safe_point(V(0, 0.3, 3.5), 55, 9)[:2]
assert abs(p.x + 4) < 1e-6 and abs(p.y + 1.95) < 1e-6 and lvid == 55, (p.x, p.y)
p, lvid = ground.safe_point(V(-3.5, 0.3, 0), 66, 9)[:2]
assert abs(p.x + 4) < 1e-6 and lvid == 66
# Without a valid vertex the original point is kept (never a nil position).
p = ground.safe_point(V(-3.5, 0.3, 0), 4294967295, 9)[0]
assert p.x == -3.5 and abs(p.y - 0.3) < 1e-6

# Created items get a yaw in [0, 2pi).
se = lua.eval("{angle = vector()}")
ground.settle(se)
assert 0 <= se.angle.y < 2 * math.pi and se.angle.x == 0

# Actual crate loot: every item goes through safe_point with its own index.
lua.execute(r'''
calls = {}
local real = netcoop_ground.safe_point
netcoop_ground.safe_point = function(pos, lvid, gvid, index, total)
    calls[#calls + 1] = {index = index, total = total}
    return real(pos, lvid, gvid, index, total)
end
made = {}
function alife_create_item(section, where, props)
    made[#made + 1] = {id = 100 + #made, section = section, pos = where[1], angle = vector()}
    return made[#made]
end
function alife_release() end
ini_sys = {r_float_ex = function() return 30 end}
function resolved_section(s) return s end
''')
box = lua.table()
src = (root / "server/netcoop_box_contents.script").read_text(encoding="cp1251")
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()", box, src)
spawn_plan = lua.eval("function(src, env) local f = assert(loadstring(src .. '\\nreturn spawn_plan')); setfenv(f, env); return f() end")(src, box)
crate = lua.eval('''{position = function() return vector():set(0.4, 0, 0) end,
    level_vertex_id = function() return 7 end, game_vertex_id = function() return 9 end, id = function() return 5 end}''')
plan = lua.eval('{items = {{section = "medkit", count = 3}, {section = "ammo_9x18", count = 60, ammo = true}, {section = "bread", count = 2}}}')
ok = spawn_plan(crate, plan)
assert ok is True, ok
assert len(g.made) == 6 and len(g.calls) == 6
assert [g.calls[i + 1].index for i in range(6)] == [1, 2, 3, 4, 5, 6] and all(g.calls[i + 1].total == 6 for i in range(6))
xs = {(round(g.made[i + 1].pos.x, 3), round(g.made[i + 1].pos.z, 3)) for i in range(6)}
assert len(xs) == 6 and all(abs(g.made[i + 1].pos.y - 0.05) < 1e-6 for i in range(6))
print("PASS ground placement: floor from above/below, spread without stacking, wall/slope/hole handled, AI-vertex fallback, yaw, crate loot per item")
