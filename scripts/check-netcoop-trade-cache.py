"""Actual GAMMA saved trade profile: cold ini cache must recover before policy."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
lua=LuaRuntime()
lua.execute('''
reads=0;restocks=0;blocked=false
db={actor={id=function() return 91 end},storage={}}
function printf() end
function time_global() return 100 end
function empty_table(t) t=t or {};for k in pairs(t) do t[k]=nil end;return t end
game_object={enemy=1}
game={CTime=function() return {set=function() end} end,
 get_game_time=function() return {diffSec=function() return 0 end} end}
game_difficulties={get_eco_factor=function() return 24 end}
alife_storage_manager={get_state=function() return {} end}
config={r_string_ex=function(_,s,k)
 if s=='trader' then return ({buy_condition='buy',sell_condition='sell',buy_item_condition_factor='0.05'})[k] end
 if k=='bandage' then return blocked and nil or '1,1' end
end,line_exist=function() return blocked end}
function ini_file(path) assert(path=='items/trade/trade_generic_medic.ltx');reads=reads+1;return config end
xr_logic={parse_condlist=function(_,_,_,s) return s end,pick_section_from_condlist=function(_,_,s) return s end}
npc={id=function() return 27 end,alive=function() return true end,name=function() return 'medic' end,
 relation=function() return 0 end,enable_trade=function() enabled=true end,disable_trade=function() enabled=false end,
 buy_condition=function(_,c,s) assert(c==config and s=='buy') end,sell_condition=function(_,c,s) assert(c==config and s=='sell') end,
 buy_item_condition_factor=function() end,buy_item_exponent=function() end,sell_item_exponent=function() end,
 buy_supplies=function() restocks=restocks+1 end}
level={object_by_id=function(id) assert(id==27);return npc end}
''')
loader=lua.eval('function(s) local e={};setmetatable(e,{__index=_G});setfenv(assert(loadstring(s)),e)();return e end')
lua.globals().trade_manager=loader((root/'scripts/fixtures/trade/trade_manager.lua').read_text(encoding='cp1251'))
lua.execute('''
saved={cfg_ltx='items/trade/trade_generic_medic.ltx',current_buy_condition='buy',current_sell_condition='sell',
 current_buy_item_condition_factor=.05,resupply_time={Y=2026,M=10,D=18,h=12,m=0,s=0,ms=0},checked=true}
trade_manager.trade_load({trade_manager={[27]=saved}})
assert(trade_manager.get_trade_profile(27)==saved and not trade_manager.get_trade_cfg(saved.cfg_ltx))
trade_manager.update(npc);assert(reads==0,'baseline: existing profile alone cannot rebuild the cache')
''')
source=(root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
begin=source.index('function prepare_trade(npc_id, dialog_trade)')
lua.execute(source[begin:source.index('\n-- The price can be positive',begin)])
lua.execute('''
local supply=saved.resupply_time
assert(prepare_trade(27,true)=='' and enabled)
assert(trade_manager.get_trade_cfg(saved.cfg_ltx)==config and reads==1)
assert(trade_manager.get_trade_profile(27)==saved and saved.resupply_time==supply and saved.checked and restocks==0)
assert(prepare_trade(27,true)=='' and reads==1 and restocks==0,'repeat uses cache and preserves supply timestamp')
''')
print('PASS actual GAMMA trade_load/init/update: cold cached medic profile recovers without losing stock or resupply state')
