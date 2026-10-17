"""Execute the actual reliable trade request/profile callbacks in Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
source = (root/'scripts/netcoop-overlay/client/netcoop_client_compat.script').read_text(encoding='cp1251')
server = (root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
requests={}; npc={id=function() return 27 end,name=function() return 'Trader' end,alive=function() return true end}
db={actor={id=function() return 91 end},storage={}}
ui_inventory={UIInventory={}}
function netcoop_trade(id,sells,items) requests[#requests+1]={id,sells,items};return true end
function printf() end
level={object_by_id=function(id) if id==27 then return npc end end}
game_object={enemy=1};npc.relation=function() return 0 end
npc.enable_trade=function() allowed=true end;npc.disable_trade=function() allowed=false end
trade_manager={trade_init=function(n,c) cfg=c end,get_trade_cfg=function(c) return {name=c} end,
 setup_buy_sell_conditions=function(n,id,c) applied=c.name end,
 update=function() updated=true end,get_trade_profile=function() return 'items/trade/trade_generic.ltx' end}
''')
start = source.index('local function install_server_trade()')
end = source.index('\nfunction on_server_text', start)
lua.execute(source[start:end] + '\ninstall_server_trade()')
lua.execute(r'''
local ui=ui_inventory.UIInventory
local bag={indx_id={[11]=1,[12]=1,[13]=2}}
bag.GetCell_ID=function(self,id) if id~=13 then return {} end end
local wnd=setmetatable({CC={actor_trade=bag,npc_trade=bag},GetPartner=function() return npc end},{__index=ui})
wnd:TMode_Sell();wnd:TMode_Buy()
assert(#requests==2 and requests[1][1]==27 and requests[1][2]==true and requests[2][2]==false)
local count=0;for id in requests[1][3]:gmatch('%d+') do count=count+1;assert(id=='11' or id=='12') end
assert(count==2,'every stacked item submitted exactly once, stale items omitted')
bag.indx_id={};wnd:TMode_Buy();assert(#requests==2,'empty trade sends no packet')
wnd.GetPartner=function() return nil end;wnd:TMode_Sell();assert(#requests==2)
gui={mode='trade',GetPartner=function() return {id=function() return 27 end} end,
 TMode_InitProfile=function(self,n) assert(n==npc);refreshed=true end,
 TMode_RefreshInventories=function() inventory_refreshed=(inventory_refreshed or 0)+1 end}
ui_inventory.GUI=gui
''')
start = source.index('local function use_trade_profile(data)')
end = source.index('\n-- A server NPC animation', start)
lua.execute(source[start:end] + "\nuse_trade_profile('27 items/trade/trade_generic.ltx');use_trade_profile('bad message');test_trade_profile=use_trade_profile")
lua.execute("assert(refreshed and inventory_refreshed==1 and gui.update_info and applied==cfg,'late profile rebuilds matching trade UI and inventories')")
lua.execute("gui.mode='loot';test_trade_profile('27 items/trade/trade_generic.ltx');assert(inventory_refreshed==1,'loot window unchanged');gui.mode='trade'")
lua.execute('UIInventory={}')
lua.execute((root/'scripts/fixtures/trade/refresh_inventory.lua').read_text(encoding='utf-8'))
lua.execute(r'''
local function item(id) return {id=function() return id end,section=function() return 'item' end} end
local function bag(ids)
 return {indx_id=ids or {},AddItem=function(self,o) self.indx_id[o:id()]=true end,
  RemoveItem_byID=function(self,id) self.indx_id[id]=nil end}
end
gui.CC={actor_trade_bag=bag({[99]=true}),actor_trade=bag({[12]=true}),npc_trade_bag=bag(),npc_trade=bag()}
gui.Picker_Toggle=function() end
gui.ParseInventory=function(self,owner) return owner==db.actor and {[11]=item(11),[12]=item(12)} or {[21]=item(21)} end
gui.TMode_RefreshInventories=UIInventory.TMode_RefreshInventories
test_trade_profile('27 items/trade/trade_generic.ltx')
assert(gui.CC.actor_trade_bag.indx_id[11] and gui.CC.npc_trade_bag.indx_id[21],'late profile repopulates both actual bags')
assert(not gui.CC.actor_trade_bag.indx_id[12] and gui.CC.actor_trade.indx_id[12],'selected stack remains in the deal without duplication')
assert(not gui.CC.actor_trade_bag.indx_id[99],'stale item removed')
test_trade_profile('27 items/trade/trade_generic.ltx')
assert(not gui.CC.actor_trade_bag.indx_id[12],'duplicate profile remains idempotent')
''')
start = server.index('function prepare_trade(npc_id, dialog_trade)')
end = server.index('\nlocal game_loaded', start)
lua.execute(server[start:end])
lua.execute('''
prepare_trade(27);assert(allowed and updated)
xr_wounded={is_wounded=function() return true end};prepare_trade(27);assert(not allowed)
xr_wounded=nil;npc.relation=function() return game_object.enemy end;prepare_trade(27);assert(not allowed)
npc.relation=function() return 0 end
xr_logic={pick_section_from_condlist=function(actor,other,rule) assert(actor==db.actor);return rule end}
db.storage[27]={meet={trade_enable='false'}};prepare_trade(27);assert(not allowed)
prepare_trade(27,true);assert(allowed,'server dialogue may open a technician trade')
xr_wounded={is_wounded=function() return true end};prepare_trade(27,true);assert(not allowed,'dialogue cannot bypass wounded policy')
xr_wounded=nil;npc.relation=function() return game_object.enemy end;prepare_trade(27,true);assert(not allowed,'dialogue cannot bypass hostility')
npc.relation=function() return 0 end
db.storage[27].meet.trade_enable='true';prepare_trade(27);assert(allowed)
-- A trader that came online with no player in scope has no profile yet
-- (GAMMA's trade_init needs db.actor): made from its logic at the trade.
local made
local saved_profile,saved_init=trade_manager.get_trade_profile,trade_manager.trade_init
trade_manager.get_trade_profile=function(id,key) return made end
trade_manager.trade_init=function(n,c) assert(db.actor);made=c end
db.storage[27]={ini={r_string_ex=function(_,s,k) assert(s=='logic@trader' and k=='trade');return 'items\\\\trade\\\\trade_barman.ltx' end},section_logic='logic@trader'}
prepare_trade(27);assert(allowed and made=='items\\\\trade\\\\trade_barman.ltx')
made=nil;db.storage[27]={};prepare_trade(27);assert(allowed and made=='items\\\\trade\\\\trade_generic.ltx')
trade_manager.get_trade_profile,trade_manager.trade_init=saved_profile,saved_init;db.storage[27]=nil
''')
# Execute the installed GAMMA policy, including ammo/multiuse exceptions and
# the stricter stock shown on the NPC side. No duplicate price formula here.
lua.execute(r'''
trade_profile={cfg_ltx='trade.ltx',current_buy_condition='buy',current_sell_condition='sell',
 current_buy_item_condition_factor=0.6}
trade_manager.get_trade_profile=function(_,key) return key and trade_profile[key] or trade_profile end
forbidden=false;missing_list=false;quest=false;no_trade=false;ammo=false;uses=false;anim=false;fake=false
function SYS_GetParam(_,_,key) if key=='quest_item' then return quest end;if key=='can_trade' then return not no_trade end end
function IsItem(kind) return ({ammo=ammo,multiuse=uses,anim=anim,fake_ammo=fake})[kind] end
function printe() end
trade_manager.get_trade_cfg=function() return {
 line_exist=function() return forbidden end, r_string_ex=function() return nil end} end
item={section=function() return 'item' end,condition=function() return condition end,
 cost=function() return cost end,ammo_get_count=function() return count end,
 get_remaining_uses=function() return count end}
condition=1;cost=100;count=10
''')
lua.execute((root / 'scripts/fixtures/trade/get_item_trade_status.lua').read_text(encoding='utf-8'))
lua.execute('utils_item={get_item_trade_status=get_item_trade_status}')
lua.execute(r'''
assert(trade_item_allowed(27,item,true) and trade_item_allowed(27,item,false))
condition=0.59;assert(not trade_item_allowed(27,item,true),'below threshold rejected despite positive price')
condition=0.6;assert(trade_item_allowed(27,item,true),'threshold inclusive')
condition=0.1;ammo=30;assert(trade_item_allowed(27,item,true),'GAMMA ammo exempt from wear threshold')
count=29;assert(not trade_item_allowed(27,item,false),'partial trader box hidden by GAMMA cannot be purchased')
count=30;assert(trade_item_allowed(27,item,false));ammo=false;uses=3;count=1
assert(trade_item_allowed(27,item,true) and not trade_item_allowed(27,item,false),'partial uses may be sold but not bought')
count=3;assert(trade_item_allowed(27,item,false));uses=false;condition=1
quest=true;assert(not trade_item_allowed(27,item,true) and not trade_item_allowed(27,item,false));quest=false
no_trade=true;assert(not trade_item_allowed(27,item,true));no_trade=false
forbidden=true;assert(not trade_item_allowed(27,item,true) and not trade_item_allowed(27,item,false));forbidden=false
anim=true;assert(not trade_item_allowed(27,item,false));anim=false
fake=true;assert(not trade_item_allowed(27,item,false));fake=false
cost=0;assert(not trade_item_allowed(27,item,false));cost=100
assert(not trade_item_allowed(28,item,true) and not trade_item_allowed(27,nil,true))
npc.alive=function() return false end;assert(not trade_item_allowed(27,item,true));npc.alive=function() return true end
local saved_actor=db.actor;db.actor=nil;assert(not trade_item_allowed(27,item,true));db.actor=saved_actor
trade_profile.current_buy_item_condition_factor=0/0;assert(not trade_item_allowed(27,item,true))
trade_profile.current_buy_item_condition_factor=0.6
trade_profile.current_buy_condition=nil;assert(not trade_item_allowed(27,item,true),'missing buy list cannot fall back to sell list')
trade_profile.current_sell_condition=nil;assert(not trade_item_allowed(27,item,false))
trade_profile=nil;assert(not trade_item_allowed(27,item,true),'missing profile fails closed')
''')
print('Actual trade Lua: stack requests, player-specific gates, actual GAMMA condition/quest/stock policy, ammo/multiuse exceptions and missing profiles PASS')
