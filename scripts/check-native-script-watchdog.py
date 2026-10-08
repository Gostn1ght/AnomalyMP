"""Exercise the actual watchdog hook at loading/gameplay/time-wrap boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess

if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/netcoop.cpp').read_text(encoding='latin-1')
start=text.index('volatile LONG wd_armed = 0;')
method=text[start:text.index('// Hitch sampling:',start)]
assert 'g_loading_events.empty()' in method and 'Device.dwPrecacheFrame' in method
source=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using u32=std::uint32_t;using LONG=std::int32_t;
struct lua_State {};
struct lua_Debug {const char* short_src="fixture";int currentline=1;const char* name="fixture";};
struct {u32 dwFrame=10,dwPrecacheFrame=0;} Device;
std::vector<int> g_loading_events;
bool g_dedicated_server=false;
u32 tick=0;unsigned clears=0,aborts=0,flushes=0;
u32 GetTickCount(){return tick;}
LONG InterlockedExchange(volatile LONG* p,LONG value){const LONG old=*p;*p=value;return old;}
void lua_sethook(lua_State*,void(*hook)(lua_State*,lua_Debug*),int mask,int count){
 assert(!hook && !mask && !count);++clears;
}
int lua_getstack(lua_State*,int,lua_Debug*){return 0;}
int lua_getinfo(lua_State*,const char*,lua_Debug*){return 0;}
template<class...T>void Msg(const char*,T...){}
void FlushLog(){++flushes;}
struct Aborted{};
void luaL_error(lua_State*,const char*,u32){++aborts;throw Aborted{};}
'''+method+r'''
int main(){
 unsigned cases=0;
 for(u32 origin:{0u,0xfffffff0u})
 for(u32 elapsed:{0u,19999u,20000u,60000u,60001u,1199999u,1200000u,1200001u})
 for(u32 precache:{0u,1u,60u})for(bool loading:{false,true})
 for(bool dedicated:{false,true})for(bool same_frame:{false,true})for(bool already_logged:{false,true}){
  g_dedicated_server=dedicated;
  Device.dwFrame=same_frame?10:11;Device.dwPrecacheFrame=precache;
  g_loading_events.assign(loading?1:0,1);
  wd_frame=10;wd_since=origin;tick=origin+elapsed;wd_armed=1;wd_logged=already_logged;
  clears=aborts=flushes=0;bool thrown=false;lua_State state;
  try{wd_hook(&state,nullptr);}catch(const Aborted&){thrown=true;}
  const bool expected=same_frame && elapsed>((loading || (!dedicated && precache))?1200000u:60000u);
  assert(thrown==expected && aborts==unsigned(expected));
  assert(clears==unsigned(!same_frame || expected));
  assert(wd_armed==((!same_frame || expected)?0:1));
  if(expected)assert(wd_frame==0);
  if(!same_frame)assert(flushes==0);
  else assert(flushes==unsigned(!already_logged)+unsigned(expected));
  ++cases;
 }
 std::cout<<"PASS actual watchdog hook "<<cases<<" cases: loading bounded20min, client/server gameplay60s incl stale server precache, stack diagnostic/frame disarm/time wrap retained\n";
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'watchdog.cpp';exe=Path(tmp)/('watchdog.exe' if os.name=='nt' else 'watchdog')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
