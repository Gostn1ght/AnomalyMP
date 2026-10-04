"""Execute deployed habitat/squad Lua and creation submission paths with Lua 5.1.

Checks eligibility and actual selection statistics, independent native group
membership, enabled-species filtering and item-stack submission. No visual QA.
"""
from pathlib import Path
from collections import Counter
from lupa.lua51 import LuaRuntime
import re, sys

runtime = Path(sys.argv[1]).resolve()
lua = LuaRuntime(unpack_returned_tuples=True)
for name in ('server/scripts/netcoop_world.script', 'client/scripts/netcoop_login_ui.script',
             'client/scripts/ui_mm_faction_select.script', 'server/scripts/sim_board.script'):
    source = (runtime/name).read_text(encoding='cp1251')
    lua.execute('assert(loadstring(...))', source)
cfg = {}
for line in (runtime/'server/configs/netcoop/world_regions.ltx').read_text().splitlines():
    line = line.split(';', 1)[0].strip()
    if line.startswith('['): section = line[1:-1]; cfg[section] = {}
    elif '=' in line:
        key, value = line.split('=', 1); cfg[section][key.strip()] = value.strip()
sections = lua.table()
for name, values in cfg.items():
    sections[name] = lua.table_from(values)
lua.globals().sections = sections
lua.execute('''
math.randomseed(9831)
local cfg = {}
function cfg:line_exist(section, name) return sections[section] and sections[section][name] ~= nil end
function cfg:r_string(section, name) return sections[section][name] end
function cfg:section_exist(section) return sections[section] ~= nil end
function cfg:line_count(section) local n=0; for _ in pairs(sections[section]) do n=n+1 end; return n end
function cfg:r_line(section, index)
 local keys={}; for k in pairs(sections[section]) do keys[#keys+1]=k end; table.sort(keys)
 return true,keys[index+1],sections[section][keys[index+1]]
end
function ini_file() return cfg end
function netcoop_enabled() return true end
ini_sys={section_exist=function() return true end,
 r_bool_ex=function(_,section) return section ~= 'simulation_story_dog' end,
 r_string_ex=function() return 'monster' end}
is_squad_monster={monster=true}
allowed={'dog_','boar_','flesh_','cat_','burer_','tushkano_','bloodsucker_','snork_','fracture_','lurker_','chimera_','m_controller_'}
smr_pop={get_mutant_spawn_table=function() return allowed end}
map='l01_escape'; objects={}
sim={level_name=function() return map end,object=function(_,id) return objects[id] end}
function alife() return sim end
function game_graph() return {valid_vertex_id=function() return true end, vertex=function() return {level_id=function() return 1 end} end} end
smart={m_game_vertex_id=1,squad_id=3,name=function() return 'test_smart' end}
''')
lua.execute((runtime/'server/scripts/netcoop_world.script').read_text())
choose = lua.globals().regional_squad
smart = lua.globals().smart
counts = {}
for region, map_name in [('field', 'l01_escape'), ('forest', 'l10_red_forest'),
                         ('industrial', 'l06_rostok'), ('village', 'l09_deadcity'),
                         ('underground', 'l04u_labx18')]:
    lua.globals().map = map_name
    counts[region] = Counter(choose(smart, 'simulation_dog') for _ in range(8000))
    assert set(counts[region]) <= set(cfg[region])
    assert choose(smart, 'simulation_story_dog') == 'simulation_story_dog'
    assert choose(smart, 'escape_quest_burer') == 'escape_quest_burer'
assert counts['field']['simulation_dog'] > counts['forest']['simulation_dog'] * 3
assert counts['industrial']['simulation_burer'] > counts['field']['simulation_burer'] * 30
assert counts['underground']['simulation_tushkano'] > counts['field']['simulation_tushkano'] * 8
lua.globals().allowed = lua.table_from(['dog_'])
for _ in range(50): assert choose(smart, 'simulation_dog') == 'simulation_dog'
lua.globals().map = 'unknown_map'
assert choose(smart, 'simulation_dog') == 'simulation_dog'
lua.execute('''
member={team=2,squad=3}; squad_a={id=111}; squad_b={id=112}; objects[111]=true; objects[112]=true
''')
group = lua.globals().squad_group
g = lua.globals()
a = group(g.member, g.squad_a, smart)
b = group(g.member, g.squad_b, smart)
assert a != b and group(g.member, g.squad_a, smart) == a
g.objects[111] = None
assert group(g.member, lua.table_from({'id': 113}), smart) == a
lua.execute('''
game={translate_string=function(id) return id end};function printf() end
CUIScriptWnd={}; function class(name) _G[name]={}; return function() end end
''')
lua.execute((runtime/'client/scripts/netcoop_login_ui.script').read_text())
lua.execute('''
submitted=nil
owner={EnterCharacter=function(_,...) submitted={...} end}
function cell(section,count,shown) return {section=section,CountChilds=function() return count-1 end,IsShown=function() return shown end} end
menu={netcoop_status={TextControl=function(s) return s end,SetText=function(s,v) s.text=v end},access=true,points_left=0,character_name={GetText=function() return 'Tester' end},
 selected_economy='st_econ_2',selected_faction='stalker',netcoop_creation_slot=4,netcoop_creation_owner=owner,
 CC={inventory={cell={cell('bandage',3,true),cell('wpn_pm',1,true),cell('hidden',1,false)}}},HideDialog=function() end,Show=function() end}
finish_creation(menu)
assert(submitted[1]==4 and submitted[2]=='Tester' and submitted[4]==2)
assert(submitted[5]=='bandage,bandage,bandage,wpn_pm')
submitted=nil; menu.points_left=-1; finish_creation(menu); assert(submitted==nil)
assert(menu.netcoop_status.text=='st_netcoop_loadout_points_invalid')
''')
assert 'netcoop_login_ui.finish_creation(self)' in (runtime/'client/scripts/ui_mm_faction_select.script').read_text(encoding='cp1251')
assert 'netcoop_world.regional_squad' in (runtime/'server/scripts/sim_board.script').read_text(encoding='cp1251')
print('PASS: Lua 5.1, 40000 regional selections, species locks, story squads, independent packs, slot/loadout submission')
