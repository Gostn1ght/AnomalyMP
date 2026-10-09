"""Actual Lua sandbox retirement and trader preservation (no native execution)."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]/"scripts/netcoop-overlay"
source = (root/"server/zz_netcoop_sandbox.script").read_text(encoding="utf-8")
assert source == (root/"client/zz_netcoop_sandbox.script").read_text(encoding="utf-8")
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
callbacks, objects, released, traded = {}, {}, {}, {}
function netcoop_enabled() return true end
function netcoop_pure_client() return false end
function RegisterScriptCallback(name,fn) callbacks[name]=fn end
local modes={removed="remove",wolf="remove",trader="trader"}
function ini_file() return {r_string_ex=function(_,group,name)
    if group=="legacy_profiles" then return modes[name] end
    if group=="retained_scientist" and name=="level" then return "k00_marsh" end
end,r_float_ex=function(_,group,name) return ({x=285.02,y=1.8,z=-160.7,radius=40})[name] end} end
ini_sys={section_exist=function() return true end,
 r_bool_ex=function(_,section) return section=="quest_document" end,
 r_string_ex=function(_,section,key) if key=="kind" then return section=="quest_artefact" and "i_quest" or "i_food" end end}
clsid={inventory_box_s=20}
function IsStalker(_,class) return class==1 end
local sim={object=function(_,id) return objects[id] end,level_name=function(_,id) return id==1 and "k00_marsh" or "l08_yantar" end}
function game_graph() return {vertex=function(_,id) return {level_id=function() return id end} end} end
function vector() return {set=function(self,x,y,z) self.x=x;self.y=y;self.z=z;return self end} end
function alife() return sim end
function alife_release(obj) released[#released+1]=obj.id;objects[obj.id]=nil end
function get_object_story_id(id) return objects[id] and objects[id].story end
function spawn(id,section,class,profile,parent,story)
 local obj={id=id,parent_id=parent or 65535,position={},m_level_vertex_id=7,m_game_vertex_id=8,story=story}
 function obj:section_name() return section end
 function obj:clsid() return class end
 function obj:profile_name() return profile end
 function obj:name() return section..id end
 function obj:invulnerable(v) self.protected=v end
 objects[id]=obj;return obj
end
function alife_create(section,pos,lvid,gvid,parent) if fail_create then return nil end return spawn(60000,section,30,"",parent) end
trade_manager={trade_init=function(obj,cfg) traded[obj.id]=cfg end,get_trade_profile=function(id) return traded[id] end}
local state={}
alife_storage_manager={get_state=function() return state end}
treasure_manager={caches={[10]="quest_document,conserva,quest_artefact",[11]=false}}
task_manager={CRandomTask={give_task=function() error("old task issued") end},
 get_task_manager=function() return {task_info={old={}}} end,task_callback=function() error("old reward") end}
xr_effects={give_task=function() error("story task") end}
axr_task_manager={get_first_available_task=function() error("old offered") end}
''')
lua.execute(source)
lua.execute(r'''
on_game_start()
assert(task_manager.CRandomTask.give_task()==nil and xr_effects.give_task()==nil)
assert(axr_task_manager.get_first_available_task()==nil and task_manager.task_callback()==nil)
spawn(1,"npc",1,"removed",nil,"story")
local wolf=spawn(2,"npc",1,"wolf",nil,"wolf")
traded[2]="obsolete_mini.ltx"
spawn(3,"npc",1,"trader",nil,"trader")
spawn(4,"npc",1,"generic")
spawn(5,"npc",1,"unknown_trader",nil,"unknown");traded[5]="existing.ltx"
spawn(10,"stash",20,"",nil,"story_box")
spawn(11,"quest_stash",20,"")
spawn(12,"quest_document",30,"",10)
spawn(13,"quest_document",30,"")
spawn(14,"conserva",30,"")
update()
assert(objects[1]==nil and objects[13]==nil and objects[12]==nil)
assert(objects[2]==nil and objects[3] and objects[4] and objects[5] and objects[14])
assert(objects[60000]:section_name()=="bandage" and objects[60000].parent_id==10)
assert(treasure_manager.caches[10]=="bandage,conserva,bandage")
assert(treasure_manager.caches[11]=="bandage,conserva,ammo_9x18_fmj")
configure_trader(wolf);assert(traded[2]=="obsolete_mini.ltx")
-- Only the Marsh church ecologist survives explicit story retirement.
local scientist=spawn(51000,"npc",1,"removed",nil,"scientist")
function scientist:community() return "ecolog" end
scientist.m_game_vertex_id=1;scientist.position={distance_to_sqr=function() return 16 end}
registered(scientist);update();assert(objects[51000]==scientist)
scientist.m_game_vertex_id=2;registered(scientist);update();assert(objects[51000]==nil)
local distant=spawn(51001,"npc",1,"removed",nil,"scientist")
function distant:community() return "ecolog" end
distant.m_game_vertex_id=1;distant.position={distance_to_sqr=function() return 10000 end}
registered(distant);update();assert(objects[51001]==nil)
-- No reroll of an emptied story stash on reload or repeated scans.
treasure_manager.caches[11]=false;callbacks.on_game_load();update()
assert(treasure_manager.caches[11]==false)
-- Later registrations are retired without another complete ALife scan.
spawn(50000,"quest_document",30,"");registered(objects[50000]);update();assert(objects[50000]==nil)
-- A failed replacement retains the original quest loot for a safe retry.
spawn(50001,"quest_document",30,"",10);fail_create=true;registered(objects[50001]);update()
assert(objects[50001]);fail_create=false;registered(objects[50001]);update();assert(objects[50001]==nil)
local data={start_dialog="old_story"};character_init("wolf",data);assert(data.start_dialog=="dm_init_trader")
local dialogs={old_story=true,dm_init_trader=true,dm_tech_repair=true}
character_dialogs("wolf",{get_dialogs=function() return {"old_story","dm_init_trader","dm_tech_repair"} end,
 remove=function(_,d) dialogs[d]=nil end,add=function(_,d) dialogs[d]=true end})
assert(not dialogs.old_story and dialogs.dm_init_trader and dialogs.dm_tech_repair)
''')
print("Sandbox Lua PASS: legacy offers/rewards blocked, story NPCs retired, traders/church scientist retained; stale mini trade cannot bypass retirement, quest items removed/replaced, no stash reroll, late registrations and failed conversion retry")
