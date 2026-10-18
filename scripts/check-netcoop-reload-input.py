"""Run actual GAMMA input/start callbacks: default controls must reach reload.

The owner had wpn_reload=F10, no custom22, and no R action at all. Exercise
GAMMA's full module, its real callback forwarding and the migration helper.
"""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parent / 'netcoop-overlay'
lua = LuaRuntime()
lua.execute(r'''
coop=true; callbacks={}; bindings={}; names={[19]='kR',[68]='kF10',[20]='kT',[21]='kY'}
key_bindings={kWPN_RELOAD=1,kCUSTOM22=2,kWPN_FIRE=3,kWPN_ZOOM=4,
 kWPN_FIREMODE_PREV=5,kWPN_FIREMODE_NEXT=6,kWPN_FUNC=7,kCUSTOM21=8}
DIK_keys={DIK_R=19,DIK_F10=68,DIK_LMENU=56}
function netcoop_enabled() return coop end
function bind_to_dik(action) return bindings[action] or 0 end
function dik_to_bind(key) for action,dik in pairs(bindings) do if dik==key then return action end end return 999 end
function dik_to_keyname(key) return names[key] end
function exec_console_cmd(command)
 local action,name=command:match('^bind (%S+) (%S+)$')
 local id=({wpn_reload=1,custom22=2})[action];assert(id)
 local key;for dik,n in pairs(names) do if n==name then key=dik end end;assert(key)
 for a,dik in pairs(bindings) do if dik==key then bindings[a]=nil end end
 bindings[id]=key
end
function printf() end
function RegisterScriptCallback(name,fn) callbacks[name]=fn end
function AddScriptCallback() end
itms_manager={ini_parts={}}
game={translate_string=function(s) return s end,actor_lower_weapon=function() end}
function sound_object() return {} end
a_arti_jamming_mcm={get_config=function() return false end}
function ini_file() return {r_float_ex=function() end,line_count=function() return 0 end} end
utils_data={collect_section=function() return {} end}
custom_functor_autoinject={add_functor=function() end}
game_difficulties={get_eco_factor=function() return .5 end}
level={press_action=function(key) assert(dik_to_bind(key)==key_bindings.kWPN_RELOAD); reloads=reloads+1 end}
db={actor={active_item=function() return {id=function() return 71 end} end}}
''')
loader = lua.eval('function(code) local e={};setmetatable(e,{__index=_G});setfenv(assert(loadstring(code)),e)();return e end')
lua.globals().netcoop_reload_input = loader((root/'client/netcoop_reload_input.script').read_text())
lua.execute((root/'client/arti_jamming.script').read_text(encoding='cp1251'))
lua.execute(r'''
-- Fresh installation, migrated installation, personal native reload key,
-- preexisting custom action, occupied R, and original single player.
for _,case in ipairs({
 {old=19,expected=19}, {old=68,expected=19}, {old=20,expected=20},
 {old=68,custom=21,expected=21}, {old=68,occupied=19,expected=0},
 {old=19,sp=true,expected=0},
}) do
 coop=not case.sp;bindings={[1]=case.old,[2]=case.custom,[3]=case.occupied};reloads=0
 on_game_start()
 assert(bind_to_dik(1)==68 and bind_to_dik(2)==case.expected)
 if case.occupied then assert(bind_to_dik(3)==case.occupied) end
 if case.expected~=0 then
  callbacks.on_key_press(case.expected)
  assert(reloads==1,'the actual GAMMA callback must forward one reload')
  callbacks.on_key_press(68);assert(reloads==1,'no recursive forwarding')
  on_game_start();assert(bind_to_dik(2)==case.expected,'reconnect preserves the chosen key')
  jammed_guns[71]=1;unjams=0;unjam=function() unjams=unjams+1 end
  callbacks.on_key_press(case.expected);assert(unjams==1 and reloads==1,'jammed guns keep GAMMA unjam')
  jammed_guns[71]=nil
 end
end
''')
print('PASS actual GAMMA start/key callbacks: fresh/migrated/custom reload keys, occupied keys, unjam, reconnect and SP')
