"""Psi storms online (actual netcoop_psi_storm server module and netcoop_psi_view
client adapter, Lua 5.1): GAMMA's 103 s storm at factor 10 started by the
server, never within 2 game hours of an emission and ended by one; vortices
near each player (shared by players together), struck 20 s later with GAMMA's
psi/shock formula outside shelters, not on admins, psi 0 with a psi helmet;
stalkers within 50 m outside covers die, not monolith/zombied/story/surge
smarts; a late joiner is not struck by old vortices; a restart resumes the
phase; the client shows the server's storm and never makes its own."""
from pathlib import Path
import math
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / "netcoop-overlay"
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
lua.execute(r'''
now, factor, hours0 = 0, 6, 100000
local time_mt = {}
time_mt.__index = time_mt
time_mt.__sub = function(a, b) return setmetatable({value = a.value - b.value}, time_mt) end
function time_mt:diffSec(other) return self.value - other.value end
function time_mt:setHMSms(h, m, s, ms) self.value = h * 3600 + m * 60 + s + ms / 1000 end
function time_mt:set() self.value = 0 end
game_seconds = hours0 * 3600
game = {CTime = function() return setmetatable({value = 0}, time_mt) end,
        get_game_time = function() return setmetatable({value = game_seconds}, time_mt) end}
function time_global() return now end
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
level = {name = function() return "k00_marsh" end, get_time_factor = function() return factor end,
         set_time_factor = function(v) factor = v end, object_by_id = function(id) return npcs[id] end}
options = {["alife/event/psi_storm_state"] = true, ["alife/event/psi_storm_frequency"] = 24,
           ["alife/event/emission_frequency"] = 24, ["alife/event/psi_storm_task"] = true,
           ["alife/event/psi_storm_fate"] = "kill"}
ui_options = {get = function(name) return options[name] end}
events = {}
function SetEvent(k, v1, v2) events[k .. "." .. tostring(v1)] = v2 end
callbacks = {}
function SendScriptCallback(name, a, b, event) callbacks[#callbacks + 1] = event end
broadcasts, sent = {}, {}
function netcoop_broadcast(channel, data) broadcasts[#broadcasts + 1] = {channel, data} end
function netcoop_send_to_actor(id, channel, data) sent[#sent + 1] = {id, channel, data} end
state = {}
alife_storage_manager = {get_state = function() return state end}
god = {}
function netcoop_admin_god_enabled(id) return god[id] == true end
emission_running, cluster = -1, false
netcoop_emission = {
    is_valid_level = function() return true end,
    current_elapsed = function() return emission_running end,
    cluster_mode = function() return cluster end,
    player_cover = function(actor) return actor.cover end,
    scheduled_start = function(hours, frequency)  -- the emission's own rule
        local slot = math.floor(hours / frequency)
        return slot * frequency + ((slot * 2654435761) % 4294967296) / 4294967296 * frequency, slot
    end}
stock = {}
psi_mgr = {kill_crows_at_pos = function(_, pos) stock.crows = (stock.crows or 0) + 1 end}
psi_storm_manager = {get_psi_storm_manager = function() return psi_mgr end}
sm = {hit_power = function(self, power, kind)
        assert(self.drug_telepatic_protection == nil); return power end,
      pos_in_cover = function(_, pos) return pos.cover end,
      turn_to_zombie = function() end, explode = function() end}
surge_manager = {get_surge_manager = function() return sm end}
helmet = false
dialogs_yantar = {actor_has_psi_helmet = function() return helmet end}
level_environment = {is_actor_immune = function() return false end}
VEC_Z = {}
hit = setmetatable({telepatic = 4, shock = 2}, {__call = function() return {} end})
tasks = {}
task_manager = {get_task_manager = function() return {give_task = function(_, name) tasks[#tasks + 1] = name end} end}
function vector() local v = {}
    function v:set(x, y, z) self.x, self.y, self.z = x, y, z return self end
    return v end
function actor(id, x, z, cover)
    local a = {cover = cover, hits = {}, health = 1, p = {x = x, y = 0, z = z}}
    function a:id() return id end
    function a:position() return self.p end
    function a:alive() return self.health > 0 end
    function a:hit(h) self.hits[#self.hits + 1] = {h.type, h.power} end
    return a
end
-- Stalkers for the vortex strike.
npcs, killed = {}, {}
function IsStalker() return true end
function get_object_story_id(id) return id == 903 and "story" or nil end
db = {storage = {}, OnlineStalkers = {}}
SIMBOARD = {smarts = {[1] = {smrt = {props = {surge = "1"}}}, [2] = {smrt = {props = {}}}}}
sim_objects = {}
function alife() return {object = function(_, id) return sim_objects[id] end} end
function stalker(id, x, z, comm, smart, cover)
    local n = {p = {x = x, y = 0, z = z, cover = cover}, alive_ = true}
    function n:character_community() return comm end
    function n:position() return self.p end
    function n:alive() return self.alive_ end
    function n:kill() self.alive_ = false; killed[#killed + 1] = id end
    npcs[id] = n; db.OnlineStalkers[#db.OnlineStalkers + 1] = id
    sim_objects[id] = {group_id = id + 1000}; sim_objects[id + 1000] = {smart_id = smart}
end
''')
g.netcoop_psi_storm = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_psi_storm, (root / "server/netcoop_psi_storm.script").read_text(encoding="utf-8"))
P = g.netcoop_psi_storm

# Cluster schedule: one storm per slot, never within 2 game hours of an emission.
sched = P.scheduled_start
em = g.netcoop_emission.scheduled_start
for h in range(0, 24 * 2000, 24):
    at, slot = sched(h + 0.5, 24)
    if at is None:
        continue
    for k in (-24, 0, 24):
        e, _ = em(at + k, 24)
        assert abs(at - e) >= 2, (h, at, e)
    assert slot * 24 <= at < (slot + 1) * 24

# A single server: GAMMA's interval; nothing during an emission.
lua.execute("emission_running = 5")
P.update_world()
assert lua.eval("state.netcoop_psi_next") is None or P.current_elapsed() < 0
lua.execute("emission_running = -1; state.netcoop_psi_next = hours0 + 1")
P.update_world()
assert P.current_elapsed() < 0
lua.execute("game_seconds = (hours0 + 1) * 3600")
P.update_world()
assert P.current_elapsed() == 0 and g.factor == 10 and g.psi_mgr.started
assert lua.eval("broadcasts[#broadcasts][1]") == "psi_storm" and lua.eval("broadcasts[#broadcasts][2]") == "1|1|0.000|103"

lua.execute("a = actor(1, 0, 0); b = actor(2, 30, 0); c = actor(3, 2000, 0, true)")
upd = lua.eval("function(x) db.actor = x; netcoop_psi_storm.update_player(x) end")
for x in (g.a, g.b, g.c):
    upd(x)
assert lua.eval("sent[1][2]") == "psi_storm"
lua.execute("now = 12000"); upd(g.a)
assert list(g.tasks.values()) == ["hide_from_psi_storm"]

# Vortices from 30 s: near the player; b (30 m away) shares a's vortex.
def vortices():
    return [x for x in lua.eval("broadcasts").values() if x[1] == "psi_vortex"]
lua.execute("math.randomseed(5)")
for t in range(30000, 78000, 500):
    g.now = t
    for x in (g.a, g.b):
        upd(x)
    P.update_world()
    if len(vortices()) >= 1 and t < 40000:
        v = vortices()[0][2].split("|")
        assert math.hypot(float(v[2]), float(v[4])) <= 150.5, v
        first_at = float(v[5])
vs = vortices()
assert 3 <= len(vs) <= 7, len(vs)  # one per 8-16 s for a and b together
# Strikes: a/b were outside shelters within 200 m of their vortices -> psi hits.
assert len(g.a.hits) >= 1 and all(h[1] in (4, 2) for h in g.a.hits.values())
# c is in a shelter far away: never struck.
assert len(g.c.hits) == 0

# GAMMA's formula, cover, admin, helmet: one controlled vortex.
lua.execute(r'''
now = 0; game_seconds = (hours0 + 30) * 3600; factor = 6
netcoop_psi_storm.finish(); state.netcoop_psi_next = hours0 + 30
netcoop_psi_storm.update_world()
d = actor(4, 40, 0); e = actor(5, 40, 0, true); f = actor(6, 40, 0); god[6] = true; h2 = actor(7, 100, 0)
for _, x in ipairs({d, e, f, h2}) do db.actor = x; netcoop_psi_storm.update_player(x) end
now = 30000
''')
# Make the vortex at the origin deterministic: patch math.random for one spawn.
lua.execute(r'''
local r = math.random
math.random = function(a, b) if b == 359 then return 0 end if b == 150 then return 0 end return a end
db.actor = d; netcoop_psi_storm.update_player(d)   -- schedules (8 s)
now = 38000; netcoop_psi_storm.update_player(d)     -- vortex at d's position (40, 0)
math.random = r
''')
v = vortices()[-1][2].split("|")
assert (float(v[2]), float(v[4])) == (40.0, 0.0), v
lua.execute(r'''
stalker(900, 50, 0, "bandit", 2, false)      -- dies
stalker(901, 50, 0, "monolith", 2, false)    -- immune
stalker(902, 50, 0, "bandit", 1, false)      -- surge smart
stalker(903, 50, 0, "bandit", 2, false)      -- story
stalker(904, 50, 0, "bandit", 2, true)       -- in cover
stalker(905, 120, 0, "bandit", 2, false)     -- too far
now = 58000
for _, x in ipairs({d, e, f, h2}) do db.actor = x; netcoop_psi_storm.update_player(x) end
netcoop_psi_storm.update_world()
''')
assert [h[2] for h in g.d.hits.values()] == [2.0, 2.0], list(g.d.hits.values())  # cos(0)+1 psi and shock at 0 m
p = math.cos(60 * math.pi / 200) + 1
assert len(g.h2.hits) == 1 and abs(g.h2.hits[1][2] - p) < 1e-6  # 60 m: psi only
assert len(g.e.hits) == 0 and len(g.f.hits) == 0                  # shelter, admin
assert list(g.killed.values()) == [900] and lua.eval("stock.crows") >= 1
kills = [x for x in lua.eval("broadcasts").values() if x[1] == "psi_kill"]
assert len(kills) == 1 and kills[0][2] == "50.0 0.0 0.0", [tuple(k.values()) for k in kills]
ph = [x for x in g.sent.values() if x[1] == 4 and x[2] == "psi_hit"]
assert ph and ph[-1][3] == "2.000 2.000"
# Helmet: psi power 0, shock unchanged; caches cleared between owners.
lua.execute("helmet = true; sm.drug_telepatic_protection = 1; netcoop_psi_storm.finish()")
assert g.factor == 6 and not g.psi_mgr.started and lua.eval("callbacks[#callbacks]") == "psi_storm_end"

# Late joiner: not struck by a vortex that already struck.
lua.execute(r'''
now = 0; game_seconds = (hours0 + 60) * 3600; state.netcoop_psi_next = hours0 + 60; netcoop_psi_storm.update_world()
helmet = false
local r = math.random
math.random = function(a, b) if b == 359 or b == 150 then return 0 end return a end
k = actor(8, 0, 0); db.actor = k; now = 30000; netcoop_psi_storm.update_player(k)
now = 38000; netcoop_psi_storm.update_player(k)
math.random = r
now = 58500; netcoop_psi_storm.update_player(k)
late = actor(9, 0, 0); db.actor = late; netcoop_psi_storm.update_player(late)
''')
assert len(g.k.hits) == 2 and len(g.late.hits) == 0  # psi + shock at 0 m; the late joiner none
# An emission ends the storm.
lua.execute("emission_running = 3; netcoop_psi_storm.update_world()")
assert P.current_elapsed() < 0
lua.execute("emission_running = -1")

# Cluster: the slot's storm starts once, resumes its phase after a restart.
lua.execute("cluster = true; state = {}")
at, slot = sched(5000.2, 24)
assert at is not None
lua.execute(f"game_seconds = {at} * 3600 + 36")
P.update_world()
assert P.current_elapsed() == 0  # the slot's storm starts
# Restart 0.1 game hour into it: a fresh module with the saved world state resumes its phase.
g.netcoop_psi_storm = lua.table()
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            g.netcoop_psi_storm, (root / "server/netcoop_psi_storm.script").read_text(encoding="utf-8"))
P = g.netcoop_psi_storm
lua.execute(f"game_seconds = {at} * 3600 + 360")
P.update_world()
assert abs(P.current_elapsed() - 36) < 0.01, P.current_elapsed()
lua.execute("netcoop_psi_storm.finish()")
P.update_world()
assert P.current_elapsed() < 0  # done for this slot

# Client adapter: shows the server's storm, never its own.
c = lua.table()
lua.execute(r'''
class = {}
engine = {starts = 0, finishes = 0, updates = 0}
function class.start(self, manual) engine.starts = engine.starts + 1; self.started = true; self.inited_time = game.get_game_time() end
function class.update(self) engine.updates = engine.updates + 1 end
function class.finish(self) engine.finishes = engine.finishes + 1; self.started = false end
function class.vortex() error("local vortex") end
function class.vortex_actor_hit() error("local hit") end
cmgr = setmetatable({vortexes = {}}, {__index = class})
psi_storm_manager = {CPsiStormManager = class, get_psi_storm_manager = function() return cmgr end}
db.actor = actor(1, 0, 0)
pp = {}
level.remove_pp_effector = function(id) end
level.add_pp_effector = function(name, id) pp[id] = name end
level.set_pp_effector_factor = function(id, f) pp[id .. "f"] = f end
function particles_object(name) return {play_at_pos = function(self, p) self.p = p end} end
function sound_object(name) return {play_at_pos = function() end} end
''')
g.netcoop_psi_view = c
lua.execute("local env = ...; setfenv(assert(loadstring(select(2, ...))), setmetatable(env,{__index=_G}))()",
            c, (root / "client/netcoop_psi_view.script").read_text(encoding="utf-8"))
lua.execute(r'''
netcoop_psi_view.install()
cmgr:start(); assert(engine.starts == 0)              -- no local storm
netcoop_psi_view.receive("1|1|40.000|103")
assert(engine.starts == 1 and engine.updates == 1)
netcoop_psi_view.vortex("1|7|10.0|2.0|5.0|3.0")
local v = cmgr.vortexes.net7
assert(v and v.particle_pos.y == 22 and v.sound_pos.y == 62)
cmgr:vortex(); cmgr:vortex_actor_hit()                -- no-ops now
netcoop_psi_view.vortex("2|8|0|0|0|0"); assert(cmgr.vortexes.net8 == nil)  -- other storm
netcoop_psi_view.on_hit("0.500 -1.000")
assert(pp[666] == "psi_fade.ppe" and pp["666f"] == 0.5 and pp[667] == nil)
netcoop_psi_view.receive("1|0|103.000|103")
assert(engine.finishes == 1)
''')
print("netcoop psi storm: OK")
