"""Run actual server mine Lua: ownership, persistence, all contacts and credit."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
clock=1000;tick=0;world={};objects={};entities={};created=0;detonations={};consume_fail=false;touch=false
function printf() end
function time_global() return tick end
alife_storage_manager={get_state=function() return world end}
game={CTime=function() return {set=function() end} end,get_game_time=function() return {diffSec=function() return clock end} end}
local function vec(x) return {x=x,distance_to=function(self,b) return math.abs(self.x-b.x) end} end
actor={id=function() return 7 end,alive=function() return true end,position=function() return vec(10) end,
 level_vertex_id=function() return 1 end,game_vertex_id=function() return 2 end}
objects[7]=actor
level={object_by_id=function(id) return objects[id] end,vertex_position=function() return vec(10) end,get_time_factor=function() return 6 end}
ini_sys={section_exist=function(_,s) return s=='mine_new_blow' or s=='rpg_new_blow' or s=='ied_new_blow' end}
function alife_create(section,p,lv,gv)
 assert(p.x==10 and lv==1 and gv==2);created=created+1;local id=100+created
 local se={id=id,name=function() return 'instance_'..id end,section_name=function() return section end}
 entities[id]=se;objects[id]={id=function() return id end,position=function() return p end};return se
end
function alife_object(id) return entities[id] end
function alife_release(obj) if consume_fail then error('consume') end obj.used=true end
function alife_release_id(id) entities[id]=nil;objects[id]=nil end
function netcoop_players() return player_ids or '7' end
function netcoop_actor_login(id) return id==7 and 'owner' or id==9 and 'owner' or 'another' end
function netcoop_mine_contact(id) assert(objects[id]);return touch end
function netcoop_explode_as(id,owner) detonations[#detonations+1]={id=id,owner=owner};return true end
function item(sec,parent) return {section=function() return sec end,parent=function() return parent or actor end} end
''')
source = (root/'scripts/netcoop-overlay/server/netcoop_mines.script').read_text()
lua.execute(source)
lua.execute(r'''
local wrong={id=function() return 99 end}
assert(plant(7,item('mine_new',wrong),'txr_mines.func_prox_plant','owner')~='')
assert(plant(7,item('wpn_pm'),'txr_mines.func_prox_plant','owner')~='')
assert(created==0)
local one=item('mine_new');assert(plant(7,one,'txr_mines.func_prox_plant','owner')=='');assert(one.used)
assert(world.netcoop_mines[101].deadline==1030)
touch=true;update();assert(#detonations==0,'arming delay')
clock=1031;tick=200;touch=false;update();assert(#detonations==0,'no creature')
touch=true;tick=400;update();assert(#detonations==1 and detonations[1].owner==7)
tick=600;update();assert(#detonations==1,'no double explosion')
assert(plant(7,item('ied_new'),'txr_mines.func_timer_plant_10','owner')=='')
objects[102]=nil;clock=2000;tick=800;update();assert(world.netcoop_mines[102],'offline timer remains pending')
''')
# Restart the actual script; persistent deadline survives, local tick state resets.
lua.execute(source)
lua.execute(r'''
objects[102]={id=function() return 102 end};player_ids='8 9';tick=1000;update()
assert(#detonations==2 and detonations[2].owner==9,'owner reconnected with another actor id')
assert(plant(7,item('ied_rpg_new'),'txr_mines.func_timer_plant_30','owner')=='')
entities[103]={name=function() return 'reused' end,section_name=function() return 'rpg_new_blow' end}
clock=3000;tick=1200;update();assert(not world.netcoop_mines[103] and #detonations==2,'reused id is not detonated')
consume_fail=true;assert(plant(7,item('mine_new'),'txr_mines.func_prox_plant','owner')~='')
assert(not entities[104] and not world.netcoop_mines[104],'failed consumption rolls back the mine')
consume_fail=false;assert(plant(7,item('ied_new'),'txr_mines.func_timer_plant_10','owner')=='')
player_ids='8';clock=4000;tick=1400;update();assert(detonations[3].owner==65535,'never credits an unrelated reused actor id')
''')
client=(root/'scripts/netcoop-overlay/client/netcoop_client_compat.script').read_text(encoding='cp1251')
server=(root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
for action in ('func_prox_plant','func_timer_plant_10','func_timer_plant_30'):
    assert f'["txr_mines.{action}"] = true' in client and f'["txr_mines.{action}"] = true' in server
assert 'netcoop_mines.plant(actor_id, item, action, login)' in server
assert 'netcoop_mines.update()' in server
print('PASS mine actions: server-only placement/consumption, persistent/offline timers, one explosion, reconnect credit, rollback and reused-id guard')
