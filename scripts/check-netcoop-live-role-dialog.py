"""Execute actual live role callbacks and scoped task speaker in Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

overlay = Path(__file__).resolve().parent / 'netcoop-overlay'
client = (overlay / 'client/netcoop_client_compat.script').read_text(encoding='cp1251')
server = (overlay / 'server/netcoop_server_compat.script').read_text(encoding='cp1251')
lua = LuaRuntime()
lua.execute('''
registrations=0;notifications=0;DEV_DEBUG=true
function printf() end
netcoop_login_ui={on_auth_result=function() notifications=notifications+1 end}
ui_debug_launcher={on_game_start=function() assert(DEV_DEBUG);registrations=registrations+1 end}
''')
begin = client.index('local admin_callbacks_installed = false')
lua.execute(client[begin:client.index('\nfunction on_trade_result', begin)])
lua.execute('''
on_role_changed(true,2,'');assert(DEV_DEBUG and registrations==1,'preexisting debug flag must not suppress registration')
on_role_changed(true,2,'');on_auth_result(true,2,'');assert(registrations==1 and notifications==1)
on_role_changed(true,1,'');assert(not DEV_DEBUG,'demotion revokes debug immediately')
on_role_changed(true,2,'');assert(DEV_DEBUG and registrations==1,'regrant does not duplicate callbacks')
on_auth_result(false,2,'');assert(not DEV_DEBUG)
on_auth_result(true,1,'');assert(not DEV_DEBUG and registrations==1)
''')
begin = server.index('local talk_speakers = {}')
lua.execute(server[begin:server.index('\n-- Remote dialogue', begin)])
lua.execute('''
function ensure_task_cache() end
events={};function GetEvent(k) return events[k] end;function SetEvent(k,v) events[k]=v end
talk_speaker(27);assert(GetEvent('used_npc_id')==27,'fetch task has an NPC speaker')
talk_speaker(28);assert(GetEvent('used_npc_id')==28)
talk_speaker(65535);assert(GetEvent('used_npc_id')==27)
talk_speaker(65535);assert(GetEvent('used_npc_id')==nil,'no stale NPC after dialogue')
SetEvent('used_npc_id',19);talk_speaker(27);talk_speaker(65535);assert(GetEvent('used_npc_id')==19)
talk_speaker(65535);assert(GetEvent('used_npc_id')==19,'unmatched cleanup cannot erase other speaker')
''')
print('PASS Lua51: immediate admin grant/revoke, idempotent callbacks, nested task speaker restoration')
