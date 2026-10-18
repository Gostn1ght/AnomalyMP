"""Actual death-camera timer must not slow or mute the next body."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / 'netcoop-overlay'
data = (root/'client/true_first_person_death.script').read_bytes()
assert data == (root/'server/true_first_person_death.script').read_bytes()
lua = LuaRuntime()
lua.execute('''
coop=true;client=true;callbacks={};clock=0;factor=1;volume=1;actor_id=7;alive=false
function netcoop_enabled() return coop end
function netcoop_pure_client() return client end
function time_global() return clock end
function normalize(v,a,b) return (v-a)/(b-a) end
function exec_console_cmd(s) factor=tonumber(s:match('time_factor (.+)')) end
function RegisterScriptCallback(k,f) callbacks[k]=f end
function UnregisterScriptCallback(k) callbacks[k]=nil end
function AddUniqueCall(f) timer=f end
function RemoveUniqueCall(f) if timer==f then timer=nil end end
level={set_snd_volume=function(v) volume=v end,set_music_volume=function(v) music=v end,
 add_pp_effector=function() effect=true end,set_pp_effector_factor=function() end,
 remove_pp_effector=function() effect=false end}
db={actor={id=function() return actor_id end,alive=function() return alive end}}
''')
lua.execute(data.decode('cp1251'))
lua.execute('''
on_game_start();assert(callbacks.actor_on_before_death)
startCam();clock=4000;timer();assert(factor<1 and volume<1 and effect)
alive=true;clock=5000;timer();assert(factor==1 and volume==1 and music==1 and not timer and not effect)
alive=false;startCam();actor_id=8;timer();assert(factor==1 and not timer)
startCam();local actor=db.actor;db.actor=nil;timer();assert(volume==1 and not timer);db.actor=actor
startCam();clock=9000;timer();callbacks.actor_on_first_update();assert(factor==1 and volume==1 and not timer)
callbacks={};client=false;on_game_start();assert(next(callbacks)==nil)
coop=false;client=true;on_game_start();assert(callbacks.actor_on_before_death)
alive=true;startCam();clock=12000;timer();assert(timer and factor<1)
main_menu_on_quit();assert(factor==1 and not timer)
''')
print('PASS actual death camera: respawn/body change/disconnect/reconnect restore time and audio; headless disabled, SP retained')
