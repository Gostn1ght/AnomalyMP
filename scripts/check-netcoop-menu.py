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
function netcoop_rp_list() return 'bar_1=bar;hands_pockets=pockets;sit_1=sit1;sit_2=sit2;sit_3=sit3;hands_behind=behind;sleep=sleep;' end
function exec_console_cmd(cmd) commands[#commands+1]=cmd end
function printf() end
game={translate_string=function(s) return s end}
ini_sys={section_exist=function() return false end}
level={present=function() return present end}
ui_events={BUTTON_CLICKED=1,WINDOW_KEY_PRESSED=2}
DIK_keys={DIK_ESCAPE=1,DIK_RETURN=28,DIK_NUMPADENTER=156,DIK_LEFT=203,DIK_RIGHT=205}
key_bindings={kINVENTORY=9}
function bind_to_dik(action,index) assert(type(index)=='number','native binding needs both arguments'); return index==0 and 23 or 24 end
settings_created=0
function Register_UI(id) assert(id=='UIOptions') end
ui_options={UIOptions=function()
 settings_created=settings_created+1
 return setmetatable({background=widget()}, {__index=Widget})
end}
CUIMMShniaga={epi_main=0,epi_new_game=1}
''')
menu_source = Path(sys.argv[1]) if len(sys.argv) > 1 else root/'scripts/netcoop-overlay/client/netcoop_login_ui.script'
lua.execute(menu_source.read_text(encoding='cp1251'))
lua.execute("assert(rawget(netcoop_login_wnd, 'Show') == nil, 'native Show must stay inherited')")
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
assert(controls.name.text=='Alpha' and #previews==0)
callbacks.char_next(); assert(controls.name.text=='Alpha')
assert(last_window:CharacterLimit()==1 and not controls.slot2.shown and not controls.slot10.shown)
local n=#characters; last_window:SelectCharacter(2); assert(#characters==n)
local previous=last_window.mode; last_window:ShowProfile(2); assert(last_window.mode==previous)
assert(callbacks.preview_pose_1==nil and callbacks.char_poses==nil)
role=2; cache_characters('Alpha|Beta||||||||');last_window:ShowCharacters()
assert(last_window:CharacterLimit()==10 and controls.slot10.shown)
callbacks.char_next(); assert(controls.name.text=='Beta')
callbacks.char_previous();assert(controls.name.text=='Alpha')
callbacks.char_previous(); assert(controls.info.text:find('10 / 10',1,true))
callbacks.char_next(); callbacks.char_server(); last_window:Update(); callbacks.server_connect()
assert(characters[#characters].slot==1 and characters[#characters].name=='Alpha')
assert(can_mcm()==true);role=0;assert(can_mcm()==false)
''')
print('Actual menu Lua: first screen, saved-account bypass, empty-password rejection, account verification without world-start commands, pending account lock, one/ten character allowance, admin slot 10 and no 3D preview PASS')

lua.execute(r'''
commands,characters,cloud_requests,drafts={},{},{},{}
cloud_state,cloud_account=0,'cloud_user'
function netcoop_firebase_state() return cloud_state end
function netcoop_firebase_account() return cloud_account end
function netcoop_firebase_email() return 'user@example.invalid' end
cloud_identity='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
function netcoop_firebase_identity() return cloud_identity end
function netcoop_firebase_request(action,email,password,username)
 cloud_requests[#cloud_requests+1]={action=action,email=email,username=username,code=action=='verify' and password or nil}; return true
end
draft_stores={}; draft_scope='127.0.0.1:1267'; draft_stores[draft_scope]=drafts
draft_owners={[cloud_identity]=draft_stores}; current_draft_owner=cloud_identity
function netcoop_draft_server(address)
 if current_draft_owner~=cloud_identity then
  draft_stores=draft_owners[cloud_identity] or {};draft_owners[cloud_identity]=draft_stores;current_draft_owner=cloud_identity
 end
 draft_scope=address;draft_stores[address]=draft_stores[address] or {}; drafts=draft_stores[address];return true
end
function netcoop_draft(slot,field) return drafts[slot] and drafts[slot][field] or '' end
function netcoop_save_draft(slot,name,description,history,faction,economy,loadout)
 drafts[slot]={name=name,description=description,history=history,faction=faction,economy=tostring(economy),loadout=loadout}; return true
end
function netcoop_character_profile(description,history) profile={description,history}; return true end
ini_sys={section_exist=function(s,section) return section=='medkit' or section=='wpn_ak74' end}
function SYS_GetParam(kind,section,key,fallback)
 if key=='visual' and section=='wpn_ak74' then return 'rifle.ogf' end
 if key=='slot' and section=='wpn_ak74' then return 2 end
 if key=='inv_grid_width' then return section=='wpn_ak74' and 5 or 1 end
 if key=='inv_grid_height' then return section=='wpn_ak74' and 2 or 1 end
 return fallback
end
function GetFontLetterica16Russian() return {} end
function CUIMessageBoxEx() return CUIStatic() end
function GetARGB() return 0 end
utils_xml={get_icons_texture=function() return 'icons' end,get_item_axis=function() return 0,0,50,50 end}
function netcoop_preview_weapon(section) last_weapon=section;return true end
function netcoop_preview_point(index) return {x=300+index*200,y=400+index*80} end
camera_done=true; camera_target=-1
function netcoop_preview_focus(object) camera_target=object;camera_done=false end
function netcoop_preview_ready() return camera_done end
function finish_camera() camera_done=true;last_window:Update() end
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
assert(not controls.input_pass.shown and controls.input_email.enabled==false and controls.input_code.shown)
callbacks.btn_reg(); assert(cloud_requests[2].action=='resend')
on_cloud_result(true,'','cloud_user',false); last_window:Update()
local before=#cloud_requests; controls.input_code:SetText('12345'); callbacks.btn_enter(); assert(#cloud_requests==before)
controls.input_code:SetText('123456');callbacks.btn_enter();assert(cloud_requests[3].action=='verify' and cloud_requests[3].code=='123456')
on_cloud_result(false,'INVALID_CODE','cloud_user',false); last_window:Update(); assert(last_window.mode=='account')
controls.input_code:SetText('654321');callbacks.btn_enter();assert(cloud_requests[4].action=='verify')
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
assert(not controls.input_email.shown and not controls.background.shown)
assert(#controls.inventory_scroll.rows==1)
drafts[1].loadout='medkit,medkit,medkit,wpn_ak74';last_window:ShowCharacters()
assert(last_weapon==nil and #controls.inventory_scroll.rows==2)
last_window:OnKeyboard(23,ui_events.WINDOW_KEY_PRESSED)
assert(controls.inventory_panel.shown and last_window.character_panel.shown and #previews==0)
finish_camera(); assert(controls.inventory_panel.shown)
last_window:OnKeyboard(24,ui_events.WINDOW_KEY_PRESSED); assert(not controls.inventory_panel.shown)
callbacks.char_inventory(); assert(controls.inventory_panel.shown)
finish_camera(); assert(controls.inventory_panel.shown)
last_window:OnKeyboard(DIK_keys.DIK_ESCAPE,ui_events.WINDOW_KEY_PRESSED)
assert(not controls.inventory_panel.shown and last_window.character_panel.shown and #commands==0)
callbacks.char_settings();assert(settings_created==0)
finish_camera();assert(settings_created==1 and not last_window.shown)
last_window:CloseRoomView(); last_window:ShowDialog(true);last_window:Show(true)
callbacks.char_settings();finish_camera();assert(settings_created==1)
last_window:CloseRoomView(); last_window:ShowDialog(true);last_window:Show(true)
local options_factory=ui_options.UIOptions;last_window.opt_dlg=nil
ui_options.UIOptions=function() error('fixture options failure') end
callbacks.char_settings();finish_camera();assert(last_window.shown and controls.status.text=='st_netcoop_settings_error')
ui_options.UIOptions=options_factory
-- Changing servers must not expose or reuse another server's draft.
controls.server_edit:SetText('Other-Server.example:1268');callbacks.server_save()
assert(draft_scope=='other-server.example:1268' and (last_window.names[1] or '')=='' and #previews==0)
assert(draft_stores['127.0.0.1:1267'][1].name=='Loner One')
controls.server_edit:SetText('127.0.0.1:1267');callbacks.server_save();assert(last_window.names[1]=='Loner One' and #previews==0)
callbacks.char_server(); assert(controls.server_panel.shown); finish_camera();callbacks.server_connect(); assert(cloud_requests[#cloud_requests].action=='refresh' and #commands==0)
on_cloud_result(false,'NETWORK_ERROR','cloud_user',true); assert(#commands==0)
callbacks.server_connect(); on_cloud_result(true,'','cloud_user',true)
assert(characters[#characters].name=='Loner One' and characters[#characters].slot==1)
assert(profile[1]=='Brown jacket' and #commands==2)
cache_characters('Server saved name||||');last_window:ShowCharacters();assert(last_window.names[1]=='Server saved name')
cloud_identity='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';last_window:ShowCharacters();assert((last_window.names[1] or '')=='' and #previews==0)
cloud_identity='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';last_window:ShowCharacters();assert(last_window.names[1]=='Server saved name')
-- Network failure while refreshing a verified account does not ask for another email code.
last_window:ResetCloud();assert(not controls.input_code.shown and not controls.btn_reg.shown)
-- A remembered cloud account is refreshed before the frontend skips login.
commands={}; local again={HideDialog=function() end,Show=function() end,ShowDialog=function() end}
local before=#cloud_requests; assert(frontend_update(again)==true)
assert(#cloud_requests==before+1 and cloud_requests[#cloud_requests].action=='refresh' and #commands==0)
''')
lua.execute(r"""
on_cloud_result(true,'','cloud_user',true);last_window:Update()
assert(last_window.mode=='characters')
commands={};controls.server_edit:SetText('role-test.example:1267');callbacks.server_check()
assert(cloud_requests[#cloud_requests].action=='refresh')
on_cloud_result(true,'','cloud_user',true)
assert(characters[#characters].slot==0 and #commands==0)
on_auth_result(false,0,'Server is unavailable')
assert(last_window.mode=='characters' and last_window:CharacterLimit()==1 and #commands==0)
callbacks.server_check();on_cloud_result(true,'','cloud_user',true)
role=2;cache_characters('Admin One|||||||||Admin Ten');on_auth_result(true,2,'Account verified')
assert(last_window:CharacterLimit()==10 and #commands==0)
last_window.slot=10;last_window:ChangeSlot(0);assert(controls.name.text=='Admin Ten')
controls.server_edit:SetText('another-role-server.example:1267');callbacks.server_save()
assert(last_window:CharacterLimit()==1 and not controls.slot10.shown)
""")
print('Firebase menu: separate account/character, verification gate, duplicate request lock, offline starter draft, stack counts, inventory key, refreshed world entry, remembered login PASS')
temporary.cleanup()

# The base menu must not load another Lua class during its native constructor.
# Loading the account module here can disrupt luabind construction.
lua.execute((root/'scripts/netcoop-overlay/client/ui_main_menu.script').read_text(encoding='cp1251'))
lua.execute(r'''
local old_xml=CScriptXmlInit
function CScriptXmlInit()
 local x=old_xml()
 x.InitFrame=x.InitStatic; x.InitTextWnd=x.InitStatic
 return x
end
function CUIMessageBoxEx() return CUIStatic() end
function GetARGB() return 0 end
function CUIScriptWnd:SetTextAlignment() end
function CUIScriptWnd:SetColor() end
main_menu.get_main_menu=function() return {} end
netcoop_login_ui=setmetatable({}, {__index=function() error('Account module loaded during native main-menu construction') end})
local function test_menu(in_game,admin,expected)
 present=in_game;role=admin and 2 or 1
 local menu=setmetatable({}, {__index=main_menu})
 menu:InitControls()
 assert(#menu.menu_buttons==expected)
 menu:Show(false);for _, b in ipairs(menu.menu_buttons) do assert(not b.shown) end
 menu:Show(true);for _, b in ipairs(menu.menu_buttons) do assert(b.shown) end
end
test_menu(false,false,3);test_menu(false,true,3)
test_menu(true,false,4);test_menu(true,true,4)
''')
print('Actual base-menu controls: no nested account-class load, player/admin buttons and show/hide PASS')
