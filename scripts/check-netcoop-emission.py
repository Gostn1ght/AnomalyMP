"""Exercise shared emission timing, per-owner damage and late joins with Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / 'netcoop-overlay'
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
now, factor, respawns, tasks, mortality, starts, ends, updates = 0, 6, 0, {}, 0, 0, 0, 0
local time_mt = {}
time_mt.__index = time_mt
time_mt.__sub = function(a,b) return setmetatable({value=a.value-b.value},time_mt) end
function time_mt:diffSec(other) return self.value-other.value end
function time_mt:setHMSms(h,m,s,ms) self.value=h*3600+m*60+s+ms/1000 end
game = {CTime=function() return setmetatable({value=0},time_mt) end,
        get_game_time=function() return setmetatable({value=100000+now*factor/1000},time_mt) end}
function time_global() return now end
level = {name=function() return 'k00_marsh' end, get_time_factor=function() return factor end,
         set_time_factor=function(value) factor=value end, stop_weather_fx=function() ends=ends+1 end}
level_weathers = {valid_levels={k00_marsh=true}}
ui_options = {get=function(name)
    if name=='alife/event/emission_state' then return true end
    if name=='alife/event/emission_frequency' then return 24 end
    return 'kill_at_end'
end}
function printf() end
function SendScriptCallback(kind,system,obj,event) if event=='emission_end' then respawns=respawns+1 end end
events = {}
function SetEvent(k,v1,v2) if v2~=nil then events[k]=events[k] or {}; events[k][v1]=v2 else events[k]=v1 end end
function netcoop_broadcast(channel,data) broadcast=data end
function netcoop_send_to_actor(id,channel,data) sent_id, sent_data=id,data end
db = {zone_by_name={}}
local zone = {id=function() return 7 end, inside=function(self,pos) return pos.cover end,
              position=function() return {} end}
db.zone_by_name.shelter=zone
xr_logic={pick_section_from_condlist=function(actor,zone,cond) return cond end}
function load_var(actor,key,default) return actor[key] or default end
function character_community(actor) return actor.community or 'actor_stalker' end
netcoop_server_compat={god_mode={}}
function netcoop_admin_god_enabled(id) return netcoop_server_compat.god_mode[id]==true end
VEC_Z={}
hit=setmetatable({telepatic=4},{__call=function() return {} end})
alife_storage_manager={get_state=function() return {} end}
bind_anomaly_zone={force_spawn_artefacts=function() respawns=respawns+1 end}
task_manager={get_task_manager=function() return {give_task=function(self,name)
  assert(name=='hide_from_surge'); tasks[db.actor:id()]=(tasks[db.actor:id()] or 0)+1
end} end}
mgr={covers={shelter='true'},survive='false',initialize=function() end,
     hit_power=function(self,power) assert(self.drug_telepatic_protection==nil); return power end,
     kill_objects_at_pos=function() mortality=mortality+1 end,kill_crows_at_pos=function() end}
surge_manager={get_surge_manager=function() return mgr end}
function actor(id,cover)
 local a={health=1,damage=0,pos={cover=cover,distance_to_sqr=function() return 1 end}}
 function a:id() return id end; function a:position() return self.pos end
 function a:alive() return self.health>0 end
 function a:hit(h) self.damage=self.damage+h.power; self.health=self.health-h.power end
 return a
end
a,b,c=actor(1,false),actor(2,true),actor(3,false)
db.actor=a
''')
lua.globals().netcoop_emission = lua.table()
lua.execute('setfenv(assert(loadstring(...)), setmetatable(netcoop_emission,{__index=_G}))()',
            (root/'server/netcoop_emission.script').read_text())
lua.execute('''
e=netcoop_emission
assert(e.start()); assert(not e.start()); assert(factor==10)
e.update_player(a); e.update_player(b)
assert(events.current_safe_cover==7 and events.nearest_safe_cover==7)
now=109000; db.actor=a; e.update_player(a); db.actor=b; e.update_player(b)
assert(a.damage>0 and b.damage==0)
assert(tasks[1]==1 and tasks[2]==1)
netcoop_server_compat.god_mode[3]=true
db.actor=c; e.update_player(c); assert(c.damage==0 and sent_id==3)
assert(sent_data:match('^1|1|109%.000|222$'))
-- Immunity/drug caches cannot leak between owners.
mgr.drug_telepatic_protection=99
now=110000; db.actor=a; e.update_player(a); assert(mgr.drug_telepatic_protection==nil)
-- Repeated packets/ticks cannot repeat wave damage or quest creation.
now=137000; db.actor=a; a.health=10; e.update_player(a); local damage=a.damage
e.update_player(a); assert(a.damage==damage and tasks[1]==1)
-- Leaving shelter during the same event exposes only that player.
now=138000; b.pos.cover=false; db.actor=b; e.update_player(b); assert(b.damage>0)
now=222000; db.actor=a; e.update_player(a); assert(a.health<=0)
now=223000; e.update_world(); assert(respawns==1 and mortality==1 and factor==6)
assert(not e.finish()); e.update_world(); assert(respawns==1)
assert(broadcast=='1|0|0.000|222')
''')
# Separate VM for client tests; stock methods mocked to detect authority leaks.
client = LuaRuntime(unpack_returned_tuples=True)
client.execute('''
now, starts, updates, cleanups, fx_stops, active_seconds = 0,0,0,0,0,0
function time_global() return now end
db={actor={alive=function() return true end}}
local mt={}; mt.__index=mt
mt.__sub=function(a,b) return setmetatable({value=a.value-b.value},mt) end
function mt:setHMSms(h,m,s,ms) self.value=ms/1000 end
game={CTime=function() return setmetatable({value=0},mt) end,
      get_game_time=function() return setmetatable({value=10000},mt) end}
level={get_time_factor=function() return 10 end,stop_weather_fx=function() fx_stops=fx_stops+1 end}
local cls={start=function(self) starts=starts+1; self.started=true end,
           update=function(self) updates=updates+1; active_seconds=(10000-self.inited_time.value)/10 end,
           end_surge=function(self) assert(not self.started); cleanups=cleanups+1 end}
mgr=setmetatable({}, {__index=cls})
surge_manager={CSurgeManager=cls,get_surge_manager=function() return mgr end}
''')
client.globals().netcoop_emission_view = client.table()
client.execute('setfenv(assert(loadstring(...)), setmetatable(netcoop_emission_view,{__index=_G}))()',
               (root/'client/netcoop_emission_view.script').read_text())
client.execute('''
e=netcoop_emission_view; e.install()
mgr:start(); assert(starts==0)
e.receive('7|1|150.000|222'); assert(starts==1 and active_seconds==150)
now=500; mgr:update(); assert(active_seconds==150.5)
e.receive('7|1|151.000|222'); assert(starts==1 and active_seconds==151)
e.receive('6|0|0.000|222'); assert(cleanups==0)
e.receive('7|0|0.000|222'); assert(cleanups==1 and fx_stops==0)
mgr:update(); local previous=updates; mgr:update(); assert(updates==previous)
e.reset(); e.receive('1|1|20.000|222'); assert(starts==2 and active_seconds==20)
''')
lua.execute('''
e=netcoop_emission
-- Cluster schedule: the same slot hour on every server, one start per slot.
local a1 = e.scheduled_start(100.2, 24); local a2 = e.scheduled_start(110.7, 24)
assert(a1 == a2 and a1 >= 96 and a1 < 120, "one start time per 24 h slot")
assert(e.scheduled_start(130, 24) >= 120, "next slot")
store = {}
alife_storage_manager={get_state=function() return store end}
getFS=function() return {update_path=function() return "cluster.ltx" end} end
io={open=function() return {close=function() end} end}
e.reset_cluster_mode(); assert(e.cluster_mode())
local at = e.scheduled_start(100, 24)
factor=6; now=(at*3600-100000)*1000/6 + 1000
e.update_world(); assert(factor==10, "starts at the scheduled hour")
now=now+223000; e.update_world(); assert(factor==6)
now=now+1000; e.update_world(); assert(factor==6, "once per slot")
''')
lua.execute('''
-- Restart during an emission (doc 43 J05): a fresh module resumes at the phase.
local e1 = netcoop_emission
local at = e1.scheduled_start(150, 24)
store = {}
factor = 6; now = (at*3600 - 100000)*1000/6 + 1000
e1.update_world(); assert(factor == 10, "started")
local saved = store
netcoop_emission = {}
''')
lua.execute('setfenv(assert(loadstring(...)), setmetatable(netcoop_emission,{__index=_G}))()',
            (root/'server/netcoop_emission.script').read_text())
lua.execute('''
local e2 = netcoop_emission
e2.reset_cluster_mode()
now = now + 60000 * 6 / 10  -- one real minute of emission passed in game time
factor = 6
e2.update_world()
assert(factor == 10, "the restarted server resumes the emission")
assert(broadcast:match("|1|"), "and tells clients it is active: " .. tostring(broadcast))
''')
print('PASS: shared clock, shelter IDs, per-owner protection, late join, single respawn and client presentation')

# Exact GAMMA end_surge: normal completion deliberately does NOT stop WFX.
# The client adapter's extra stop used to cut its recovery tail. Test the
# actual stock cleanup through the actual adapter, plus the manual SP path.
stock = LuaRuntime(unpack_returned_tuples=True)
stock.execute('''
now,stops,forced,mortality,statistics,events,intervals,indicators=0,0,0,0,0,0,0,0
factor,pp,cam,waves,sounds,lights=10,0,0,0,0,0
function time_global() return now end
game={get_game_time=function() return 12345 end}
db={actor={alive=function() return true end},signal_light={}}
game_statistics={increment_statistic=function() statistics=statistics+1 end}
function SendScriptCallback() events=events+1 end
level={get_time_factor=function() return factor end,
 set_time_factor=function(value) factor=value end,
 stop_weather_fx=function() stops=stops+1 end,
 remove_pp_effector=function() pp=pp+1 end,
 remove_cam_effector=function() cam=cam+1 end}
AC_ID,surge_shock_pp_eff,earthquake_cam_eff=7,8,9
xr_sound={stop_sound_looped=function() sounds=sounds+1 end}
local wm={weather_fx='saved_fx',forced_weather_change=function() forced=forced+1 end}
level_weathers={get_weather_manager=function() return wm end}
local cls={start=function(self) self.started=true end,update=function() end}
function cls:new_surge_time() intervals=intervals+1 end
function cls:displayIndicators(value) assert(value==0); indicators=indicators+1 end
function cls:kill_all_unhided() mortality=mortality+1 end
function cls:kill_wave() waves=waves+1 end
surge_manager={CSurgeManager=cls,get_surge_manager=function() return mgr end}
CSurgeManager=cls
function make_mgr()
 mgr=setmetatable({started=true,game_time_factor=6,
  blowout_sound=true,wave_sound=true,second_message_given=true,
  blowout_waves={{effect={playing=function() return true end}}},
  blowout_sounds={{playing=function() return true end,stop=function() sounds=sounds+1 end}}},
 {__index=cls})
 db.signal_light={{stop_light=function() lights=lights+1 end,stop=function() lights=lights+1 end}}
 return mgr
end
''')
fixture = root.parent / 'fixtures/emission/surge-end.lua'
stock.execute(fixture.read_text(encoding='utf-8'))
stock.execute('''
-- Stock normal completion has a weather tail, manual completion explicitly cuts it.
make_mgr():end_surge(false)
assert(stops==0 and forced==0 and mortality==1 and statistics==1 and events==2)
make_mgr():end_surge(true)
assert(stops==1 and forced==1 and mortality==2)
''')
stock.globals().netcoop_emission_view = stock.table()
stock.execute('setfenv(assert(loadstring(...)), setmetatable(netcoop_emission_view,{__index=_G}))()',
              (root/'client/netcoop_emission_view.script').read_text())
stock.execute('''
local before={stops,forced,mortality,statistics,events,intervals,indicators,pp,cam,waves,sounds,lights}
make_mgr(); e=netcoop_emission_view; e.install()
-- Establish an active event without invoking unrelated stock update behavior.
db.actor=nil; e.receive('9|1|100.000|222'); db.actor={alive=function() return true end}
e.receive('9|0|0.000|222')
assert(stops==before[1] and forced==before[2], 'normal authority end must retain stock WFX recovery')
assert(mortality==before[3] and statistics==before[4] and events==before[5], 'client cannot repeat authority mortality/respawn')
assert(not mgr.started and mgr.finished and mgr.last_surge_time==12345 and factor==6)
assert(intervals==before[6]+1 and indicators==before[7]+1 and pp==before[8]+1 and cam==before[9]+1)
assert(waves==before[10]+1 and sounds==before[11]+4 and lights==before[12]+2)
local interval=intervals
e.receive('9|0|0.000|222'); assert(intervals==interval, 'duplicate end cannot redo cleanup')
''')
print('PASS actual GAMMA end_surge through client adapter: WFX recovery retained, stock sound/wave/light/PP/camera cleanup and factor restore retained; no client mortality/respawn; manual SP control still cuts WFX')
