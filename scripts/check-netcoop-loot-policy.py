"""Actual saved world loot policy and initial NPC generation in Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
server = root / "scripts/netcoop-overlay/server"
sections, current = {}, None
for line in (server / "configs/netcoop/loot_policy.ltx").read_text().splitlines():
    line = line.split(";", 1)[0].strip()
    if line.startswith("["):
        current = line[1:-1]
        sections[current] = {}
    elif "=" in line:
        key, value = line.split("=", 1)
        sections[current][key.strip()] = float(value)

lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
g.config_sections = lua.table_from({k: lua.table_from(v) for k, v in sections.items()})
lua.execute(r'''
state={}; vars={}; now_hours=10; here="k00_marsh"; economy=1; wall_time=12345
os.time=function() return wall_time end
alife_storage_manager={get_state=function() return state end}
game={CTime=function() return {set=function() end} end,
 get_game_time=function() return {diffSec=function() return now_hours*3600 end} end}
level={name=function() return here end}
local presets={econ_1={loots=1.2},econ_2={loots=0.6},econ_3={loots=0.3}}
ini_file=function(path) return {r_float_ex=function(_,section,key)
 if path=="plugins\\difficulty.ltx" then return presets[section] and presets[section][key] end
 local t=config_sections[section];return t and t[key] end} end
game_difficulties={get_eco_factor=function() return economy end}
-- GAMMA's se vars are keyed by ID; the policy must verify names itself.
function se_load_var(id,name,key) return vars[id..":"..key] end
function se_save_var(id,name,key,value) vars[id..":"..key]=value end
logs={};function printf(fmt,...) logs[#logs+1]=string.format(fmt,...) end
function npc(id)
 local n={_id=id,inv={}}
 function n:id() return self._id end;function n:name() return "npc_"..self._id end
 function n:alive() return true end;function n:spawn_ini() return nil end
 function n:iterate_inventory(fn,owner) for _,i in ipairs(self.inv) do fn(owner,i) end end
 return n
end
db={actor={},storage={}};ranks={get_obj_rank_name=function() return "veteran" end}
function character_community() return "stalker" end
function get_object_story_id(id) return id==99 and "story_trader" or nil end
function any_player() return nil end;function bind_actor() end
generated={};draws={};bad_generator=false
local function generate(stage,n)
 if bad_generator then error("generator failed") end
 generated[#generated+1]=stage;draws[#draws+1]=math.random(0,1000)
 n.inv[#n.inv+1]={}
end
death_manager={get_items_by_npc=function() return nil end}
for _,stage in ipairs({"ammo","powders","bullets","casings","sin_artefacts"}) do
 death_manager["try_spawn_"..stage]=function(n) generate(stage,n) end
end
death_manager.create_item_list=function(n,_,_,private) generate(private and "private" or "community",n) end
''')

def load(name):
    g[name] = lua.table()
    lua.execute("local env,source=...; setfenv(assert(loadstring(source)),setmetatable(env,{__index=_G}))()",
                g[name], (server / (name + ".script")).read_text(encoding="utf-8"))

load("netcoop_loot_policy")
load("netcoop_world_events")
compat = (server / "netcoop_server_compat.script").read_text(encoding="utf-8")
lua.execute(compat[compat.index("local WORLD_SEED"):compat.index("-- Its items spawn after it:")]
            + "\nbuild=build_npc_inventory")
lua.execute(r'''
local p=netcoop_loot_policy
local a=npc(1);local seed=p.world_seed();local original=math.random
math.randomseed(997);local expected=math.random();math.randomseed(997)
build(a);assert(#generated==7 and #a.inv==7)
assert(math.random==original and math.random()==expected,"global RNG preserved")
build(a);assert(#generated==7,"no regeneration on repeat/offline reentry")
local saved=p.context_for(a)
assert(saved.economy==1 and saved.chances.ammo==1 and not saved.after_emission)
now_hours=11;state.netcoop_emissions=1;state.netcoop_last_emission_hour=10.5;economy=0.5
local event=netcoop_world_events.record({kind="battle",level=here})
local b=npc(2);local context=p.context_for(b)
assert(context.after_emission and context.battle_seq==event.seq and context.emissions==1)
assert(context.chances.ammo==0.375 and context.chances.powders==0.28125)
assert(context.chances.community==0.9,"GAMMA community economy not multiplied twice")
assert(p.context_for(a)==saved and saved.chances.ammo==1,"birth context immutable")
-- A busy journal cannot erase the saved regional battle context.
for i=1,600 do netcoop_world_events.record({kind="death",level=here}) end
assert(#netcoop_world_events.recent()==512)
local c=p.context_for(npc(3));assert(c.battle_seq==event.seq)
-- Different map and expired/future events do not impose local scarcity.
here="l01_escape";local d=p.context_for(npc(4));assert(d.battle_seq==0 and d.chances.ammo==0.5)
here="k00_marsh";now_hours=17;local old=p.context_for(npc(5))
assert(old.battle_seq==0 and not old.after_emission and old.chances.ammo==0.5)
netcoop_world_events.record({kind="battle",level=here});now_hours=16
assert(p.context_for(npc(6)).battle_seq==0,"future event rejected")
-- Latched configuration cannot reroll a failed stage on restart.
config_sections.base.ammo=0;local blocked=p.context_for(npc(7))
assert(not p.allows(blocked,"ammo"));config_sections.base.ammo=1
assert(not p.allows(p.context_for(npc(7)),"ammo"))
for _,stage in ipairs({"ammo","powders","bullets","casings","sin_artefacts","community","private"}) do
 assert(p.allows(context,stage)==p.allows(context,stage))
end
saved_policy=p;saved_context=context;saved_seed=seed
saved_draws={};assert(p.with_random(context,function()
 for i=1,20 do saved_draws[i]=math.random(0,100) end end))
wall_time=98765
''')
load("netcoop_loot_policy")
lua.execute(r'''
local p=netcoop_loot_policy
assert(p.world_seed()==saved_seed,"world seed survives module reload/wall clock")
assert(p.context_for(npc(2))==saved_context,"snapshot survives restart")
assert(p.with_random(saved_context,function()
 for i=1,20 do assert(math.random(0,100)==saved_draws[i]) end end))
local original=math.random
local ok=p.with_random(saved_context,function() error("test failure") end)
assert(not ok and math.random==original,"RNG restored after failure")
local r=p.random(5)
for i=1,100 do local n=r(0.4,1);assert(n==0 or n==1,"Lua 5.1 float-bound coercion") end
local before=#generated;build(npc(99));assert(#generated==before,"story inventory unchanged")
local protected=npc(8);protected.spawn_ini=function() return {section_exist=function() return true end} end
build(protected);assert(#generated==before,"dont_spawn_loot respected")
bad_generator=true;local failed=npc(9);build(failed);local after=#generated
build(failed);assert(#generated==after and math.random==original,"failure never duplicates partial loot")
local observer=netcoop_world_events
local callback=p.world_event;p.world_event=function() error("broken policy") end
local death=observer.record({kind="battle",level=here});assert(death.seq>0,"policy failure does not stop journal")
p.world_event=callback
economy=0/0;local bounded=p.context_for(npc(10));assert(bounded.economy==1)
-- Actual ALife registration latches before the NPC ever comes online.
callbacks={};function RegisterScriptCallback(name,fn) callbacks[name]=fn end
function netcoop_enabled() return true end;function netcoop_pure_client() return false end
function game_graph() return {vertex=function(_,id) return {level_id=function() return id end} end} end
function alife() return {level_name=function(_,id) return id==1 and "k00_marsh" or "l01_escape" end} end
here="l01_escape";now_hours=30;economy=0.5
p.world_event({kind="battle",level="k00_marsh",h=29,seq=77})
p.on_game_start();local offline={id=11,m_game_vertex_id=1,name=function() return "npc_11" end,alive=function() return true end}
callbacks.server_entity_on_register(offline,"se_stalker")
local birth=p.context_for(npc(11));assert(birth.hour==30 and birth.level=="k00_marsh" and birth.battle_seq==77)
now_hours=50;economy=3;bad_generator=false;here="k00_marsh"
assert(p.context_for(npc(11))==birth and birth.economy==0.5,"first observer cannot reroll birth context")
callbacks.server_entity_on_register(offline,"se_stalker")
assert(p.context_for(npc(11))==birth,"restart registration preserves saved birth")
build(npc(11));assert(se_load_var(11,"npc_11","netcoop_inventory"),"birth inventory generated on later online spawn")
local ignored={id=12,m_game_vertex_id=1,name=function() return "npc_12" end,alive=function() return false end}
callbacks.server_entity_on_register(ignored,"se_stalker");assert(not se_load_var(12,"npc_12","netcoop_loot_context"))
callbacks.server_entity_on_register(offline,"se_monster")
local lookup=game_graph;game_graph=function() error("graph failure") end
callbacks.server_entity_on_register(offline,"se_stalker");game_graph=lookup
-- Real se_load_var is keyed by id; the policy itself validates a recycled id's name.
local replacement=npc(11);replacement.name=function() return "different_npc" end
assert(p.context_for(replacement)~=birth,"recycled id never inherits another NPC context")
-- Saved settings precede GAMMA's first-player on_game_load callback.
economy=nil;state.diff_eco={type=2};local boot=p.context_for(npc(13));assert(boot.economy==0.6)
economy=3;state.diff_eco={type=3,loots=0.4};assert(p.context_for(npc(14)).economy==0.4,"saved override precedes stale cache")
state.diff_eco={type=3};assert(p.context_for(npc(15)).economy==0.3,"saved preset precedes stale cache")
state.diff_eco={type=0/0};assert(p.context_for(npc(16)).economy==1.2,"invalid preset uses GAMMA default")
state.diff_eco=nil;economy=nil;assert(p.context_for(npc(17)).economy==1.2,"fresh world before factor initialization")
state.diff_eco={loots=0/0};assert(p.context_for(npc(18)).economy==1,"invalid saved override bounded")
state.diff_eco={loots=0};local disabled=p.context_for(npc(19))
assert(disabled.economy==0 and not p.allows(disabled,"ammo"),"zero GAMMA loot factor remains disabled")
assert(p.context_for(npc(13))==boot and boot.economy==0.6,"initialization never rerolls boot snapshot")
''')
# Run GAMMA's actual create_item_list against its real named cache upvalues.
stock = (root / "scripts/fixtures/loot/create_item_list.lua").read_text(encoding="utf-8")
g.stock_source = stock
lua.execute(r'''
local src=[[local enble_trade_items=true
local item_by_community={stalker_veteran={{sec="b",cha=0.99},{sec="a",cha=0.99},{sec="essential",cha=1}},
 stalker_private_veteran={{sec="b",cha=0.99},{sec="a",cha=0.99}}}
local item_count={a={1,1},b={1,1},essential={1,1}}
local shuffle_cnt={stalker_veteran=100,stalker_private_veteran=100};local shuffle_max=2
]]..stock_source..[[
return create_item_list,item_by_community,shuffle_cnt]]
local original,cache,counts=assert(loadstring(src))()
death_manager={create_item_list=original};flags={}
local profiles={stalker_veteran={{"b",0.8},{"a",0.6},{"essential",1}},
 stalker_private_veteran={{"b",0.8},{"a",0.6}}}
itms_manager={ini_death={section_exist=function(_,sec) return profiles[sec]~=nil end,
 line_count=function(_,sec) return #profiles[sec] end,
 r_line_ex=function(_,sec,i) local r=profiles[sec][i+1];return true,r[1],tostring(r[2]) end,
 line_exist=function(_,sec,item) return sec=="exclude_from_multi" and item=="essential" end}}
function IsItem() return false end
local records,shuffled={},0
function create_item(_,sec,count,chance)
 if bad_generator then error("stock generator failure") end
 records[#records+1]={sec=sec,count=count,chance=chance,roll=math.random(1,1000)}
end
function shuffle_table(t) shuffled=shuffled+1;math.random();t[1],t[#t]=t[#t],t[1] end
function printdbg() end
local function same_cache()
 local found=0
 for i=1,64 do
  local name,value=debug.getupvalue(original,i);if not name then break end
  if name=="item_by_community" then assert(value==cache);found=found+1 end
  if name=="shuffle_cnt" then assert(value==counts);found=found+1 end
 end
 assert(found==2 and counts.stalker_veteran==100 and counts.stalker_private_veteran==100)
end
local function run()
 records={};local n=npc(20)
 assert(netcoop_loot_policy.with_random({seed=913,economy=0.5},function()
  death_manager.create_item_list(n,"stalker","veteran",false)
  death_manager.create_item_list(n,"stalker","veteran",true)
 end))
 assert(#records==5 and records[1].sec=="a" and records[1].chance==0.3)
 assert(records[2].sec=="b" and records[2].chance==0.4)
 assert(records[3].sec=="essential" and records[3].chance==1)
 assert(records[4].sec=="a" and records[4].chance==0.3 and shuffled==0)
 same_cache();return records
end
bad_generator=false;local first=run()
-- Zero/stale scaled caches and other NPC activation order cannot change this birth.
for _,list in pairs(cache) do for _,row in ipairs(list) do row.cha=0 end;list[1],list[#list]=list[#list],list[1] end
local second=run();for i,row in ipairs(first) do assert(row.sec==second[i].sec and row.roll==second[i].roll) end
local previous=math.random;bad_generator=true
local ok=netcoop_loot_policy.with_random({seed=913,economy=0.5},function()
 death_manager.create_item_list(npc(20),"stalker","veteran",false) end)
assert(not ok and math.random==previous);same_cache()
bad_generator=false;records={}
assert(netcoop_loot_policy.with_random({seed=1,economy=0},function()
 death_manager.create_item_list(npc(20),"stalker","veteran",false) end))
assert(#records==1 and records[1].sec=="essential","GAMMA exclude_from_multi remains exempt")
same_cache()
''')
print("PASS actual saved loot policy and GAMMA generator: ALife birth, bootstrap/saved/zero economy, canonical lists independent of cached scale/shuffle, restored upvalues/RNG, events, restart and generation once")
