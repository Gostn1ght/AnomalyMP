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
gui={GetPartner=function() return npc end,TMode_InitProfile=function(self,n) assert(n==npc);refreshed=true end}
ui_inventory.GUI=gui
''')
start = source.index('local function use_trade_profile(data)')
end = source.index('\n-- A server NPC animation', start)
lua.execute(source[start:end] + "\nuse_trade_profile('27 items/trade/trade_generic.ltx');use_trade_profile('bad message')")
lua.execute("assert(refreshed and gui.update_info and applied==cfg,'profile rebuilds open trade UI')")
start = server.index('function prepare_trade(npc_id)')
end = server.index('\nlocal game_loaded', start)
lua.execute(server[start:end])
lua.execute('''
prepare_trade(27);assert(allowed and updated)
xr_wounded={is_wounded=function() return true end};prepare_trade(27);assert(not allowed)
xr_wounded=nil;npc.relation=function() return game_object.enemy end;prepare_trade(27);assert(not allowed)
npc.relation=function() return 0 end
xr_logic={pick_section_from_condlist=function(actor,other,rule) assert(actor==db.actor);return rule end}
db.storage[27]={meet={trade_enable='false'}};prepare_trade(27);assert(not allowed)
db.storage[27].meet.trade_enable='true';prepare_trade(27);assert(allowed)
''')
print('Actual trade Lua: stack submission, missing/empty partner, late profile refresh and freeplay trade gates PASS')
