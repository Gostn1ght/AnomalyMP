"""Actual ambient timer: absent channels must not crash or stop future weather."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / 'netcoop-overlay'
source = (root/'client/sound_ambient.script').read_bytes()
assert source == (root/'server/sound_ambient.script').read_bytes()
lua = LuaRuntime()
lua.execute(r'''
callbacks={};hour=12;weather_name='clear';map_name='marsh';ambient='valid';now=100;plays=0;reads=0
function clamp(x,a,b) return math.max(a,math.min(b,x)) end
function empty_table(t) for k in pairs(t) do t[k]=nil end end
function RegisterScriptCallback(k,f) callbacks[k]=f end
function CreateTimeEvent(_,_,_,fn) timer=fn end
function ResetTimeEvent() end
function time_global() now=now+10;return now end
function GetEvent() return false end
level={get_time_hours=function() return hour end,get_weather=function() return weather_name end,name=function() return map_name end}
level_weathers={get_weather_manager=function() return {get_curr_ambient=function() return ambient end} end}
function ini_file()
 reads=reads+1
 return {section_exist=function(_,name) return name=='channel' end,
 r_float_ex=function(_,_,field) if field=='max_distance' then return 20 elseif field=='min_distance' then return 10 else return 0 end end,
 r_bool_ex=function() return false end}
end
function parse_list(_,section,field)
 if field=='sound_channels_dynamic' then return section=='valid' and {'channel'} or {} end
 return {'ambient/test'}
end
function vector() return {set=function(_,x,y,z) return {x=x,y=y,z=z} end} end
db={actor={position=function() return {x=0,y=0,z=0} end}}
function sound_object() return {play_at_pos=function() plays=plays+1 end} end
ui_options={get=function() return 1 end}
''')
lua.execute(source.decode('cp1251'))
lua.execute(r'''
on_game_start();callbacks.actor_on_first_update()
assert(timer()==false);timer();timer();assert(plays==1)
-- A failed reset previously emptied the table but retained the old size.
hour=13;ambient='missing';assert(timer()==false)
local old_reads=reads;for i=1,10 do assert(timer()==false) end
assert(reads==old_reads and plays==1,'empty ambience must neither error nor spin configuration reads')
-- A change of weather within that hour re-enables ambience.
weather_name='rain';ambient='valid';timer();timer();timer();assert(plays==2)
-- No channels, including an empty/missing ambient name.
hour=14;ambient='';timer();for i=1,3 do assert(timer()==false) end
-- Same-hour map transition and reconnect rebuild the channels.
map_name='escape';ambient='valid';timer();timer();timer();assert(plays==3)
callbacks.actor_on_first_update();timer();timer();timer();assert(plays==4)
''')
# Also exercise the first timer invocation when no ambient has ever succeeded.
lua.execute("callbacks.actor_on_first_update();ambient='missing';assert(timer()==false);assert(timer()==false)")
print('PASS actual ambient timer: missing/empty channels, repeated ticks, weather/map changes and reconnect; valid sounds still play')
