"""Reproduce actual GAMMA nil-parts context-menu failure through client guard."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
client=(root/'scripts/netcoop-overlay/client/netcoop_client_compat.script').read_text(encoding='cp1251')
guard=client[client.index('function install_weapon_menu_guards('):client.index('local function install_server_item_actions(')]
legacy=(root/'scripts/fixtures/weapon-menu/fieldstrip.lua').read_text(encoding='utf-8')
lua=LuaRuntime()
lua.execute(r'''
client=true;parts=nil;reads=0;rolls=0;registered={};registrations=0;mutations=0;maintains=0
function netcoop_pure_client()return client end
function has_parts()return true end
function is_part(k)return k=='bolt' end
arti_jamming={is_barrel=function(k)return k=='barrel' end}
function spairs(t)return pairs(t)end
sort_parts=function()return false end
item_parts={get_parts_con=function(obj,id,evaluate)
 assert(obj==weapon and id==nil);reads=reads+1;if evaluate then rolls=rolls+1 end;return parts
end}
weapon={}
custom_functor_autoinject={add_functor=function(name,predicate,label,condition,action,bags)
 registrations=registrations+1;registered[name]={predicate=predicate,label=label,condition=condition or predicate,action=action,bags=bags}
end}
''')
lua.execute(legacy)
lua.execute(r'''
local ok=pcall(has_parts_fieldstrip,weapon,'actor_bag','inventory')
assert(not ok,'actual stock predicate must reproduce nil parts failure')
zzzz_arti_jamming_repairs={has_parts_fieldstrip=has_parts_fieldstrip,
 check_maintain=function(obj)assert(obj==weapon);maintains=maintains+1;return true end,
 name_fieldstrip=function()return 'fieldstrip' end,name_maintain=function()return 'maintain' end,
 init_fieldstrip_menu=function()mutations=mutations+1 end,
 init_maintenance_menu=function()mutations=mutations+1 end}
original_strip=has_parts_fieldstrip;original_maintain=zzzz_arti_jamming_repairs.check_maintain
''')
lua.execute(guard)
lua.execute(r'''
client=false;install_weapon_menu_guards()
assert(registrations==0 and zzzz_arti_jamming_repairs.has_parts_fieldstrip==original_strip)
client=true;install_weapon_menu_guards();install_weapon_menu_guards()
assert(registrations==2,'registered predicates replaced once, not merely module names')
assert(registered.arti_fieldstrip.label==zzzz_arti_jamming_repairs.name_fieldstrip)
assert(registered.arti_fieldstrip.action==zzzz_arti_jamming_repairs.init_fieldstrip_menu and registered.arti_fieldstrip.bags==true)
assert(registered.arti_maintain.action==zzzz_arti_jamming_repairs.init_maintenance_menu and registered.arti_maintain.bags==false)
rolls=0
for _,bag in ipairs({'actor_equ','actor_belt','actor_bag','npc_bag'})do
 for _,mode in ipairs({'inventory','loot'})do
  assert(not registered.arti_fieldstrip.predicate(weapon,bag,mode))
  assert(not registered.arti_maintain.predicate(weapon,bag,mode))
  local menu={'equip','unload','move'}
  if registered.arti_fieldstrip.predicate(weapon,bag,mode) then menu[#menu+1]='fieldstrip' end
  assert(#menu==3,'missing parts must not prevent independent menu entries')
 end
end
assert(rolls==0 and maintains==0 and mutations==0,'absent metadata is neither rerolled nor mutated')
assert(not registered.arti_fieldstrip.predicate(nil,'actor_bag','inventory'))
parts={bolt=30,barrel=80}
for _,bag in ipairs({'actor_bag','npc_bag','npc_trade'})do
 for _,mode in ipairs({'inventory','loot','trade'})do
  local expected=original_strip(weapon,bag,mode)
  assert(registered.arti_fieldstrip.predicate(weapon,bag,mode)==expected,'valid metadata keeps stock filtering')
 end
end
assert(registered.arti_maintain.predicate(weapon,'actor_bag','inventory') and maintains==1)
parts={barrel=90};assert(not registered.arti_fieldstrip.predicate(weapon,'actor_bag','inventory'))
assert(mutations==0)
''')
print('PASS actual GAMMA nil-parts failure reproduced; guarded registered predicates preserve other menu entries, metadata, actions, bag filtering and SP/server functions. Full authoritative parts actions remain unqualified.')
