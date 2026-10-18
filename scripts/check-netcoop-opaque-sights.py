"""Execute the shipped ADS shader switcher: co-op sights stay opaque, SP is unchanged."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
lua=LuaRuntime()
lua.execute(r'''
coop=true;callbacks={};events={};scheduled=0;writes={}
function netcoop_enabled() return coop end
function printf() end
function RegisterScriptCallback(k,f) callbacks[k]=f end
function get_console_cmd() return '(0,1.3,0,0.5)' end
function get_console() return {execute=function() end} end
function RemoveTimeEvent(_,k) events[k]=nil end
function CreateTimeEvent(_,k,delay,f,id) scheduled=scheduled+1;events[k]=function() return f(id) end end
ini_sys={r_float_ex=function() return nil end,r_string_ex=function() return nil end,r_bool_ex=function() return false end}
local config={target_shader_scopes={['models\\model_scope']=true},rear_irons_shaders={['models\\model_irons']=true}}
function ini_file_ex() return {section_exist=function(_,s) return config[s]~=nil end,collect_section=function(_,s) return config[s] end} end
z_3d_scopes_mcm={get_config=function(k) if k=='shader_switcher_opacity' then return 5 end return true end}
originals={[1]={shader='models\\model_scope',texture='scope'},[2]={shader='models\\model_irons',texture='iron'},[3]={shader='models\\weapons',texture='body'}}
materials={}
for k,v in pairs(originals) do materials[k]={shader=v.shader,texture=v.texture} end
weapon={id=function() return 91 end,section=function() return 'wpn_test' end,
 weapon_in_grenade_mode=function() return false end,get_attachment=function() return nil end,
 get_default_shaders=function() return originals end,get_shaders=function() return materials end}
weapon.set_shader=function(_,id,shader,texture)
 writes[#writes+1]=shader;materials[id].shader=shader;materials[id].texture=texture or materials[id].texture
end
local cw={IsZoomed=function() return true end,IsScopeAttached=function() return false end,GetZoomType=function() return 0 end}
weapon.cast_Weapon=function() return cw end
db={actor={active_item=function() return weapon end}}
level={object_by_id=function(id) if id==91 then return weapon end end}
''')
lua.execute((root/'scripts/netcoop-overlay/client/z_3dss_shader_switcher.script').read_text(encoding='cp1251'))
lua.execute(r'''
on_game_start()
for _=1,3 do actor_on_weapon_zoom_in(weapon);actor_on_weapon_zoom_type_changed(weapon);actor_on_weapon_zoom_out(weapon) end
assert(scheduled==0,'co-op must never queue the translucent ADS material')
for _,s in ipairs(writes) do assert(s~='models\\transparent_hud') end
assert(materials[1].shader=='models\\weapons' and materials[2].shader=='models\\weapons','opaque marker normalization is retained')
assert(materials[3].shader=='models\\weapons' and materials[3].texture=='body')
-- Ordinary SP keeps its enabled option and delayed transparency behavior.
coop=false;actor_on_weapon_zoom_in(weapon);assert(scheduled==1);events['91']()
assert(materials[1].shader=='models\\transparent_hud' and materials[2].shader=='models\\transparent_hud')
assert(materials[3].shader=='models\\weapons','unrelated weapon material untouched')
actor_on_weapon_zoom_out(weapon);assert(materials[1].shader=='models\\weapons')
-- Option refresh/re-entry also restores any already faded items.
actor_on_weapon_zoom_in(weapon);events['91']();coop=true;callbacks.on_option_change()
assert(materials[1].shader=='models\\weapons' and materials[2].shader=='models\\weapons')
assert(callbacks.actor_on_hud_animation_play and callbacks.actor_on_first_update,'normal 3DSS callbacks retained')
''')
print('PASS actual 3DSS switcher: no co-op sight fading, opaque marker normalization, stale-effect cleanup, unrelated body and SP behavior retained')
