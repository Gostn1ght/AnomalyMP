"""Actual dedicated actor-dependent conditions across empty/death/respawn scopes."""
from pathlib import Path
from lupa.lua51 import LuaRuntime
root=Path(__file__).resolve().parents[1]
source=(root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
start=source.index('local function install_actor_conditions()')
helper=source[start:source.index('function install()',start)]
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
 calls=0;actor={id=7};npc={id=9};xr_conditions={}
 for _,name in ipairs({'actor_enemy','actor_friend','actor_neutral','see_actor'})do
  xr_conditions[name]=function(a,n,token)
   assert(a==actor and n==npc and token=='unchanged')
   calls=calls+1;return 'normal result',token
  end
 end
''')
lua.execute(helper+'\ninstall_actor_conditions()')
for name in ('actor_enemy','actor_friend','actor_neutral','see_actor'):
    f=lua.globals().xr_conditions[name]
    for actor,npc in ((None,None),(None,lua.globals().npc),(lua.globals().actor,None)):
        assert f(actor,npc,'unchanged') is False
    assert f(lua.globals().actor,lua.globals().npc,'unchanged')==('normal result','unchanged')
assert lua.globals().calls==4
lua.execute('xr_conditions=nil')
lua.execute(helper+'\ninstall_actor_conditions()')
print('PASS actual actor conditions: no player/NPC never calls relation; valid actors and all return values/arguments retained; unavailable module safe')
