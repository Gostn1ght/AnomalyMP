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
ini_file=function() return {r_float_ex=function(_,section,key)
 local t=config_sections[section];return t and t[key] end} end
game_difficulties={get_eco_factor=function() return economy end}
function se_load_var(id,name,key) return vars[id..":"..name..":"..key] end
function se_save_var(id,name,key,value) vars[id..":"..name..":"..key]=value end
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
''')
print("PASS actual saved loot policy: economy/emission/local battle, journal eviction, restart RNG/context, initial generation once, story/protection/errors and Lua 5.1 bounds")
