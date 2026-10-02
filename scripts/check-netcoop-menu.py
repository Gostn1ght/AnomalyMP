"""Run the actual account/character menu in Lua 5.1 with UI/transport stubs.
Requires lupa; does not validate native transport or visual rendering.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from lupa.lua51 import LuaRuntime
root=Path(__file__).resolve().parents[1]
temporary = TemporaryDirectory(prefix='netcoop-menu-')
cache = Path(temporary.name)
lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().test_path=cache.as_posix()+'/'
lua.execute(r'''
state,role,account,present=0,0,'',false
commands,characters,previews,callbacks,controls={},{},{},{},{}
local Widget={}
function Widget:SetText(v) self.text=v end
function Widget:GetText() return self.text or '' end
function Widget:TextControl() return self end
function Widget:Show(v) self.shown=v end
function Widget:IsShown() return self.shown or false end
function Widget:Enable(v) self.enabled=v end
function Widget:CaptureFocus() end
function Widget:SetWndRect() end
function Widget:SetWndPos() end
function Widget:SetWndSize() end
function Widget:SetAutoDelete() end
function Widget:HideDialog() self.shown=false end
function Widget:ShowDialog() self.shown=true end
function Widget:Register() end
function Widget:AddCallback(id,event,fn,selfref) callbacks[id]=function() return fn(selfref) end end
function Widget:Clear() self.rows={} end
function Widget:AddWindow(w) self.rows=self.rows or {}; self.rows[#self.rows+1]=w end
function Widget:OnKeyboard() return false end
function Widget:Update() end
function Widget:AttachChild() end
function Widget:InitTexture() end
function Widget:SetTextureRect() end
function Widget:SetStretchTexture() end
function Widget:SetFont() end
function Widget:SetTextColor() end
local function widget(id) local w=setmetatable({shown=true}, {__index=Widget}); if id then controls[id]=w end; return w end
CUIScriptWnd=Widget
function class(name)
 _G[name]={}
 return function(base)
  setmetatable(_G[name], {__index=base,__call=function(c,...)
   local obj=setmetatable({}, {__index=c}); obj:__init(...); last_window=obj; return obj
  end})
 end
end
function super() end
function Frect() return {set=function(s) return s end} end
function vector2() return {set=function(s) return s end} end
function CUIStatic() return widget() end
function CScriptXmlInit() return {ParseFile=function() end,InitStatic=function(s,id) return widget(id) end,
 InitEditBox=function(s,id) return widget(id) end,Init3tButton=function(s,id) return widget(id) end,
 InitScrollView=function(s,id) return widget(id) end} end
function getFS() return {update_path=function(s,alias,name) return test_path..name end} end
function netcoop_account() return account end
function netcoop_account_state() return state end
function netcoop_role() return role end
function netcoop_login(login,pass,register) account=login; return true end
auth_requests={}
function netcoop_frontend_auth(options) auth_requests[#auth_requests+1]=options; return true end
function netcoop_character(slot,name,faction,economy,loadout) characters[#characters+1]={slot=slot,name=name,loadout=loadout}; return true end
function netcoop_preview_clear() end
function netcoop_preview_model(model,pose) previews[#previews+1]={model=model,pose=pose}; return true end
function netcoop_rp_list() return 'sit=pose_sit;salute=pose_salute;' end
function exec_console_cmd(cmd) commands[#commands+1]=cmd end
function printf() end
game={translate_string=function(s) return s end}
ini_sys={section_exist=function() return false end}
level={present=function() return present end}
ui_events={BUTTON_CLICKED=1,WINDOW_KEY_PRESSED=2}
DIK_keys={DIK_ESCAPE=1,DIK_RETURN=28,DIK_NUMPADENTER=156,DIK_LEFT=203,DIK_RIGHT=205}
key_bindings={kINVENTORY=9}
function bind_to_dik() return 23 end
CUIMMShniaga={epi_main=0,epi_new_game=1}
''')
menu_source = Path(sys.argv[1]) if len(sys.argv) > 1 else root/'scripts/netcoop-overlay/client/netcoop_login_ui.script'
lua.execute(menu_source.read_text(encoding='cp1251'))
lua.execute(r'''
local menu={HideDialog=function(s) s.hidden=true end,Show=function() end,ShowDialog=function() end}
local approved_menu={}; state=2
assert(frontend_update(approved_menu)==false)
state=0
assert(frontend_update(menu)==true)
controls.input_login:SetText('tester_pending'); controls.input_pass:SetText('')
callbacks.btn_reg(); assert(#characters==0 and #commands==0)
controls.input_pass:SetText('test-password')
callbacks.btn_reg(); assert(characters[#characters].slot==0)
assert(#commands==0 and auth_requests[#auth_requests]=='127.0.0.1/name=tester_pending/port=1267')
assert(frontend_update(menu)==false)
local requests=#auth_requests; callbacks.btn_enter(); assert(#auth_requests==requests)
state=1; on_auth_result(false,0,'Registration pending administrator approval')
last_window:Update()
assert(not controls.btn_reg.shown and controls.input_login.enabled==false)
local n=#characters; callbacks.btn_reg(); assert(#characters==n)
callbacks.btn_enter(); assert(characters[#characters].slot==0)
state=2; cache_characters('Alpha|Beta|||'); cache_previews('actors\\novice.ogf|stalker|\nactors\\armor.ogf|dolg|\n')
on_auth_result(true,1,'Account verified'); last_window:Update()
assert(#commands==0)
assert(controls.name.text=='Alpha' and previews[#previews].model=='actors\\novice.ogf')
callbacks.char_next(); assert(controls.name.text=='Beta' and previews[#previews].model=='actors\\armor.ogf')
callbacks.char_previous(); assert(controls.name.text=='Alpha')
callbacks.preview_pose_1(); assert(previews[#previews].pose==1)
callbacks.char_previous(); assert(controls.info.text:find('5 / 5',1,true))
callbacks.char_next(); callbacks.char_enter()
assert(characters[#characters].slot==1 and characters[#characters].name=='Alpha')
assert(can_mcm()==false); role=2; assert(can_mcm()==true)
''')
print('Actual menu Lua: first screen, saved-account bypass, empty-password rejection, account verification without world-start commands, pending account lock, slot/model mapping and RP selection PASS')

lua.execute(r'''
commands,characters,cloud_requests,drafts={},{},{},{}
cloud_state,cloud_account=0,'cloud_user'
function netcoop_firebase_state() return cloud_state end
function netcoop_firebase_account() return cloud_account end
function netcoop_firebase_email() return 'user@example.invalid' end
function netcoop_firebase_request(action,email,password,username)
 cloud_requests[#cloud_requests+1]={action=action,email=email,username=username}; return true
end
function netcoop_draft(slot,field) return drafts[slot] and drafts[slot][field] or '' end
function netcoop_save_draft(slot,name,description,history,faction,economy,loadout)
 drafts[slot]={name=name,description=description,history=history,faction=faction,economy=tostring(economy),loadout=loadout}; return true
end
function netcoop_character_profile(description,history) profile={description,history}; return true end
''')
lua.execute(menu_source.read_text(encoding='cp1251'))
lua.execute(r'''
local menu={HideDialog=function() end,Show=function() end,ShowDialog=function() end}
assert(frontend_update(menu)==true)
controls.input_email:SetText('user@example.invalid'); controls.input_login:SetText('cloud_user')
controls.input_pass:SetText('tiny'); callbacks.btn_reg(); assert(#cloud_requests==0)
controls.input_pass:SetText('test-password'); callbacks.btn_reg()
assert(cloud_requests[1].action=='register' and #commands==0 and #characters==0)
callbacks.btn_reg(); assert(#cloud_requests==1)
cloud_state=1; on_cloud_result(true,'','cloud_user',false); last_window:Update()
assert(not controls.input_pass.shown and controls.input_email.enabled==false)
callbacks.btn_reg(); assert(cloud_requests[2].action=='resend')
on_cloud_result(true,'','cloud_user',false); last_window:Update()
callbacks.btn_enter(); assert(cloud_requests[3].action=='refresh')
cloud_state=2; on_cloud_result(true,'','cloud_user',true); last_window:Update()
assert(last_window.mode=='profile' and #commands==0)
controls.input_name:SetText('Loner One'); controls.input_description:SetText('Brown jacket')
controls.input_history:SetText('A separate character history')
ui_mm_faction_select={UINewGame=function(owner)
 local hidden={Show=function() end}
 last_creator={owner=owner,SetAutoDelete=function() end,HideDialog=function() end,ShowDialog=function() end,Show=function() end,
  character_name={SetText=function(s,v) s.name=v end,GetText=function(s) return s.name end},scroll_options=hidden,list_map=hidden}
 return last_creator
end}
callbacks.profile_next(); assert(last_creator.character_name.name=='Loner One')
assert(#commands==0 and #characters==0)
last_creator.access=true; last_creator.points_left=10; last_creator.selected_economy='st_econ_1'; last_creator.selected_faction='stalker'
last_creator.CC={inventory={cell={{section='medkit',IsShown=function() return true end,CountChilds=function() return 2 end}}}}
netcoop_login_ui={finish_creation=finish_creation}
finish_creation(last_creator)
assert(drafts[1].loadout=='medkit,medkit,medkit')
assert(drafts[1].history=='A separate character history')
assert(last_window.mode=='characters' and controls.name.text=='Loner One' and #commands==0)
last_window:OnKeyboard(23,ui_events.WINDOW_KEY_PRESSED); assert(controls.inventory_panel.shown)
callbacks.char_enter(); assert(cloud_requests[#cloud_requests].action=='refresh' and #commands==0)
on_cloud_result(false,'NETWORK_ERROR','cloud_user',true); assert(#commands==0)
callbacks.char_enter(); on_cloud_result(true,'','cloud_user',true)
assert(characters[#characters].name=='Loner One' and characters[#characters].slot==1)
assert(profile[1]=='Brown jacket' and #commands==2)
-- A remembered cloud account is refreshed before the frontend skips login.
commands={}; local again={HideDialog=function() end,Show=function() end,ShowDialog=function() end}
local before=#cloud_requests; assert(frontend_update(again)==true)
assert(#cloud_requests==before+1 and cloud_requests[#cloud_requests].action=='refresh' and #commands==0)
''')
print('Firebase menu: separate account/character, verification gate, duplicate request lock, offline starter draft, stack counts, inventory key, refreshed world entry, remembered login PASS')
temporary.cleanup()
