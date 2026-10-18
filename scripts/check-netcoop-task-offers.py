"""Actual GAMMA task generator and dedicated-server config-cache initialization."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
source=(root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
lua=LuaRuntime()
lua.execute('''
function printf() end
available_tasks={};CFG_CACHE={};init_count=0
sections={trader_task_1={job_descr='bring ammunition'},trader_task_2={job_descr='locked'},other_task_1={job_descr='other trader'}}
task_info={};db={storage={[27]={}},actor={}}
task_manager={get_task_manager=function() return {task_info=task_info} end,task_ini={
 r_string_ex=function(_,section,key) return sections[section] and sections[section][key] end,
 r_float_ex=function() return nil end,
 section_for_each=function(_,fn) init_count=init_count+1 for k in pairs(sections) do fn(k) end end}}
function empty_table(t) for k in pairs(t) do t[k]=nil end end
function starts_with(s,p) return s:sub(1,#p)==p end
xr_conditions={has_completed_task_prerequisites=function(_,_,p) return p[1]~='trader_task_2' end}
npc={id=function() return 27 end,section=function() return 'trader' end}
''')
lua.execute((root/'scripts/fixtures/task-offers/generate_cache.lua').read_text(encoding='utf8'))
lua.execute((root/'scripts/fixtures/task-offers/generate_available_tasks.lua').read_text(encoding='utf8'))
lua.execute('axr_task_manager={CFG_CACHE=CFG_CACHE,generate_cache=generate_cache}')
start=source.index('local task_cache_ready = false')
lua.execute(source[start:source.index('\nlocal game_loaded',start)])
lua.execute('''
generate_available_tasks(npc,false);assert(#available_tasks[27]==0,'reproduce empty dedicated cache before SP load_state')
ensure_task_cache();assert(init_count==1)
generate_available_tasks(npc,false)
assert(#available_tasks[27]==1 and available_tasks[27][1]=='trader_task_1','ordinary job offered, locked prerequisites still enforced')
ensure_task_cache();ensure_task_cache();assert(init_count==1,'no cache rebuild per dialogue/frame')
task_info.trader_task_1={status='in_progress'}
generate_available_tasks(npc,false);assert(#available_tasks[27]==0,'already taken task remains unavailable to this player')
task_info={};generate_available_tasks(npc,false);assert(#available_tasks[27]==1,'another player uses their own task history')
''')
# The first dialogue must initialize before any condition/action examines offers.
start=source.index('function talk_speaker(npc_id)')
speaker=source[start:source.index('\n-- Remote dialogue',start)]
assert 'if npc_id ~= 65535 then ensure_task_cache() end' in speaker
assert 'ensure_task_cache()' in source[source.index('local function server_game_load()'):source.index('-- World systems')]
print('PASS actual GAMMA task offers: cold dedicated cache, ordinary offers, prerequisites, taken tasks, separate player history and idempotent startup')
