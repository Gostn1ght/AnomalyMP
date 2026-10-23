"""Actual server command handler: role gate and idempotent god requests."""
from pathlib import Path
from lupa.lua51 import LuaRuntime
root=Path(__file__).resolve().parents[1]
lua=LuaRuntime()
lua.execute('''
 function printf() end
 approvals=0
 function netcoop_registration_decide(login,accept)
  approvals=approvals+1
  return login=="guest" and accept
 end
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
for role in ('player','leader','none',None):
    assert call('console','CONSOLE',65535,'approve_registration guest',role)=='! administrator account required'
assert lua.globals().approvals==0
assert call('console','CONSOLE',65535,'approve_registration guest','admin')=='* registration is open; administrator approval is no longer required'
assert call('console','CONSOLE',65535,'reject_registration guest','admin')=='* registration is open; administrator approval is no longer required'
assert lua.globals().approvals==0
# World orders (owner 2026-10-23): with the world master an administrator's
# weather, emission, psi storm, time and time scale go to the master for
# every location; without one the map changes itself.
lua.execute('''
 orders={};local_changes={};master_line="0";master_up=true
 netcoop_master={state=function() if master_line=="1" then return {scale=10} end return nil,master_line=="2" end,
  governs=function() return master_line~="0" end}
 function netcoop_world_order(account,order,source,target,a,b,c,d)
  if not master_up then return false end
  orders[#orders+1]={account=account,order=order,source=source,target=target,a=a,b=b,c=c,d=d};return true
 end
 netcoop_server_compat={master_weather_source=function() return "clear" end,
  set_server_weather=function(n,now) local_changes[#local_changes+1]="weather "..n;return "* local weather" end}
 netcoop_emission={real_duration=function() return 222 end,start=function() local_changes[#local_changes+1]="emission";return true end}
 netcoop_psi_storm={real_duration=function() return 103 end,start=function() local_changes[#local_changes+1]="psi";return true end}
 level={get_time_factor=function() return 6 end,
  change_game_time=function(d,h,m) local_changes[#local_changes+1]=string.format("time %d %d %d",d,h,m) end,
  set_time_factor=function(v) local_changes[#local_changes+1]="scale "..v end}
''')
sent='* sent to the world master: every location follows it'
for cmd in ('weather w_rain2','time 2','timescale 20','emission start','psi start'):
    assert call('c','ordinary',8,cmd,'player')=='! administrator account required'
assert call('c','admin',7,'weather w_rain2 now','admin').startswith('* local weather')
assert call('c','admin',7,'time 1 2 30','admin')=='* time moved forward 1d 2h 30m on this location'
assert call('c','admin',7,'timescale 20','admin')=='* time scale 20.00 on this location'
assert call('c','admin',7,'emission start','admin')=='* emission started for all players'
assert list(lua.eval('local_changes').values())==['weather w_rain2','time 1 2 30','scale 20','emission']
assert len(lua.eval('orders'))==0
lua.execute('master_line="1"')
assert call('c','admin',7,'weather w_rain2 now','admin')==sent
assert call('c','admin',7,'weather storm','admin')==sent
assert call('c','admin',7,'time 3','admin')==sent
assert call('c','admin',7,'time 0 0 45','admin')==sent
assert call('c','admin',7,'timescale 12.5','admin')==sent
assert call('c','admin',7,'emission start','admin')==sent
assert call('c','admin',7,'psi start','admin')==sent
o=lua.eval('orders')
assert [o[i].order for i in range(1,8)]==['weather','weather','advance','advance','scale','emission','psi_storm']
assert o[1].account=='admin' and o[1].source=='clear' and o[1].target=='w_rain2' and o[1].a==1 and o[2].a==600
assert o[3].a==3*3600 and o[4].a==45*60 and o[5].a==12.5
assert abs(o[6].a+o[6].b+o[6].c-2220)<1e-6 and o[6].d==1 and abs(o[7].a*3-1030)<1e-6
for args in ('0','-1','31 0 0','1 2 3 4','abc','+2'):
    assert call('c','admin',7,'time '+args,'admin').startswith('! ')
assert len(lua.eval('orders'))==7 and len(lua.eval('local_changes'))==4
# A required master that cannot be reached changes nothing on this map alone.
lua.execute('master_line="2";master_up=false')
assert call('c','admin',7,'time 2','admin')=='! the world master is not reachable from this location; nothing changed'
assert call('c','admin',7,'emission start','admin').startswith('! the world master')
assert len(lua.eval('local_changes'))==4
print('PASS world orders: master path for weather/time/scale/emission/psi, local without master, nothing local when the master is unreachable')
print('PASS obsolete approval commands: no account moderation performed; player/leader/missing role still rejected')
print('PASS actual admin handler: ordinary/leader denied before native call, on/off idempotent, toggle, malformed/missing/native-rejected owner')
print('PASS actual teleport handler: sender actor only, role/finite/count/range parsing and native rejection')
