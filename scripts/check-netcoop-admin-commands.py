"""Actual server command handler: role gate and idempotent god requests."""
from pathlib import Path
from lupa.lua51 import LuaRuntime
root=Path(__file__).resolve().parents[1]
lua=LuaRuntime()
lua.execute('''
 function printf() end
 modes={};roles={[7]=2,[8]=1};calls=0
 function netcoop_admin_god_enabled(id) return roles[id]==2 and modes[id]==true end
 function netcoop_admin_god_set(id,value)
  calls=calls+1
  if roles[id]~=2 then return false end
  modes[id]=value;return true
 end
 teleports=0
 function vector() return {set=function(self,x,y,z)self.x=x;self.y=y;self.z=z;return self end} end
 function netcoop_admin_teleport(id,pos)
  teleports=teleports+1
  last_teleport={id=id,x=pos.x,y=pos.y,z=pos.z}
  return roles[id]==2
 end
''')
lua.execute((root/'scripts/netcoop-overlay/server/netanomaly_server.script').read_bytes().decode('latin-1'))
call=lua.globals().on_client_command
for role in ('player','leader','none'):
    for cmd in ('god','god on','god off','god 1','god 0'):
        assert call('c','ordinary',8,cmd,role)=='! administrator account required'
assert lua.globals().calls==0
for cmd in ('god on','god on','god 1'):
    assert call('c','admin',7,cmd,'admin')=='* god mode ON'
    assert lua.eval('modes[7]') is True
for cmd in ('god off','god off','god 0'):
    assert call('c','admin',7,cmd,'admin')=='* god mode OFF'
    assert lua.eval('modes[7]') is False
assert call('c','admin',7,'god','admin')=='* god mode ON'
assert call('c','admin',7,'god','admin')=='* god mode OFF'
before=lua.globals().calls
for cmd in ('god invalid','god on off','god 2','god -1'):
    assert call('c','admin',7,cmd,'admin')=='! usage: god [on|off]'
assert lua.globals().calls==before
assert call('c','admin',65535,'god on','admin')=='! your Actor is not on the server'
assert call('c','admin',8,'god on','admin')=='! ADMIN Actor unavailable'
for role in ('player','leader','none'):
    assert call('c','ordinary',8,'admin_teleport 1 2 3',role)=='! administrator account required'
assert lua.globals().teleports==0
for args in ('','1 2','1 2 3 4','nan 0 0','1e309 0 0','50001 0 0','0 -50001 0','0 0 50001'):
    assert call('c','admin',7,'admin_teleport '+args,'admin')=='! usage: admin_teleport <x> <y> <z>'
assert lua.globals().teleports==0
assert call('c','admin',7,'admin_teleport 1 -2.5 1e1','admin')=='* admin teleport accepted'
assert lua.eval('last_teleport.id')==7 and lua.eval('last_teleport.z')==10
assert call('c','admin',8,'admin_teleport 1 2 3','admin')=='! ADMIN teleport rejected'
print('PASS actual admin handler: ordinary/leader denied before native call, on/off idempotent, toggle, malformed/missing/native-rejected owner')
print('PASS actual teleport handler: sender actor only, role/finite/count/range parsing and native rejection')
