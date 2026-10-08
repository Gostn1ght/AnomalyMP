"""Exercise actual story-dialog override with Lua 5.1, including network GUI without NPC."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

overlay = Path(__file__).resolve().parent / "netcoop-overlay"
source = (overlay / "client/z_gavrilenko_tasks_fix.script").read_bytes()
assert source == (overlay / "server/z_gavrilenko_tasks_fix.script").read_bytes()
lua = LuaRuntime(encoding=None)
lua.execute(b'''
callbacks={}; completed=0; queried=0
function RegisterScriptCallback(name,fn) callbacks[name]=fn end
mob_trade={GetTalkingNpc=function() queried=queried+1;return speaker end}
task_manager={get_task_manager=function() return {task_info={story={task_giver_id=7,stage=1}},set_task_completed=function() completed=completed+1 end} end,task_ini={}}
utils_data={parse_ini_section_to_array=function() return {stage_complete=1} end}
function CreateTimeEvent(a,b,c,fn) fn() end
''')
lua.execute(source)
lua.execute(b'''
on_game_start(); assert(callbacks.GUI_on_show==GUI_on_show)
GUI_on_show('Other'); assert(queried==0)
GUI_on_show('Dialog'); assert(queried==1 and completed==0)
speaker={section=function() return 'bar_duty_security_squad_leader' end,id=function() return 7 end}
GUI_on_show('Dialog'); assert(completed==1)
callbacks={};function netcoop_enabled() return true end
on_game_start();assert(next(callbacks)==nil)
GUI_on_show('Dialog');complete_npc_tasks(speaker);assert(queried==2 and completed==1)
''')
print("PASS Lua51: missing speaker safe; SP completion preserved; netcoop legacy completion disabled")
