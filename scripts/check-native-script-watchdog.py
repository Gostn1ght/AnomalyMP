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
stop = (root/'src/xrGame/level_network.cpp').read_text(encoding='latin-1')
start_level = (root/'src/xrGame/Level_start.cpp').read_text(encoding='latin-1')
assert stop.index('netcoop::script_watchdog_level_end();', stop.index('void CLevel::net_Stop()')) < stop.index('remove_objects();')
assert 'netcoop::script_watchdog_level_begin();' in start_level
source=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <chrono>
using u32=std::uint32_t;using LONG=std::int32_t;
using SRWLOCK=std::mutex;
#define SRWLOCK_INIT {}
void AcquireSRWLockExclusive(SRWLOCK* guard){guard->lock();}
void ReleaseSRWLockExclusive(SRWLOCK* guard){guard->unlock();}
constexpr int LUA_MASKCOUNT=8;
struct lua_State {};
struct lua_Debug {const char* short_src="fixture";int currentline=1;const char* name="fixture";};
struct {u32 dwFrame=10,dwPrecacheFrame=0;} Device;
std::vector<int> g_loading_events;
bool g_dedicated_server=false;
u32 tick=0;unsigned clears=0,aborts=0,flushes=0,arms=0,fetches=0;
bool alive=true;lua_State engine_state;
lua_State* fetch_state(){assert(alive);++fetches;return &engine_state;}
u32 GetTickCount(){return tick;}
LONG InterlockedExchange(volatile LONG* p,LONG value){const LONG old=*p;*p=value;return old;}
LONG InterlockedCompareExchange(volatile LONG* p,LONG value,LONG compare){const LONG old=*p;if(old==compare)*p=value;return old;}
void lua_sethook(lua_State*,void(*hook)(lua_State*,lua_Debug*),int mask,int count){
 if(hook){assert(mask==LUA_MASKCOUNT && count==10000);++arms;}
 else {assert(!mask && !count);++clears;}
}
int lua_getstack(lua_State*,int,lua_Debug*){return 0;}
int lua_getinfo(lua_State*,const char*,lua_Debug*){return 0;}
template<class...T>void Msg(const char*,T...){}
void FlushLog(){++flushes;}
struct Aborted{};
void luaL_error(lua_State*,const char*,u32){++aborts;throw Aborted{};}
std::atomic<bool> entered{false},released{false};
lua_State* blocked_state(){entered=true;while(!released.load())std::this_thread::yield();return fetch_state();}
'''+method+r'''
int main(){
 unsigned cases=0;
 for(u32 origin:{0u,0xfffffff0u})
 for(u32 elapsed:{0u,19999u,20000u,60000u,60001u,1199999u,1200000u,1200001u})
 for(u32 precache:{0u,1u,60u})for(bool loading:{false,true})
 for(bool dedicated:{false,true})for(bool same_frame:{false,true})for(bool already_logged:{false,true})for(bool paused:{false,true}){
  g_dedicated_server=dedicated;
  Device.dwFrame=same_frame?10:11;Device.dwPrecacheFrame=precache;
  g_loading_events.assign(loading?1:0,1);
  wd_frame=10;wd_since=origin;tick=origin+elapsed;wd_armed=1;wd_logged=already_logged;wd_quiescent=paused?1:0;
  clears=aborts=flushes=0;bool thrown=false;lua_State state;
  try{wd_hook(&state,nullptr);}catch(const Aborted&){thrown=true;}
  const bool expected=!paused && same_frame && elapsed>((loading || (!dedicated && precache))?1200000u:60000u);
  assert(thrown==expected && aborts==unsigned(expected));
  assert(clears==unsigned(paused || !same_frame || expected));
  assert(wd_armed==((paused || !same_frame || expected)?0:1));
  if(expected)assert(wd_frame==0);
  if(paused || !same_frame)assert(flushes==0);
  else assert(flushes==unsigned(!already_logged)+unsigned(expected));
  ++cases;
 }
 wd_quiescent=0;wd_armed=0;wd_frame=0;clears=arms=fetches=0;
 assert(wd_try_arm(40,0,20000,fetch_state) && arms==1 && fetches==1);
 wd_pause(fetch_state);assert(wd_quiescent && !wd_armed && clears==1 && fetches==2);
 alive=false;assert(!wd_try_arm(41,0,30000,fetch_state) && fetches==2);
 wd_pause(fetch_state);assert(fetches==2); // No Lua access when no hook exists.
 alive=true;wd_resume();assert(wd_try_arm(41,0,30000,fetch_state));wd_pause(fetch_state);
 wd_resume();std::atomic<bool> paused_done{false};
 std::thread armer([]{assert(wd_try_arm(42,0,40000,blocked_state));});
 while(!entered.load())std::this_thread::yield();
 std::thread pauser([&]{wd_pause(fetch_state);paused_done=true;});
 std::this_thread::sleep_for(std::chrono::milliseconds(5));assert(!paused_done.load());
 released=true;armer.join();pauser.join();
 assert(paused_done.load() && wd_quiescent && !wd_armed);
 alive=false;const unsigned old_fetches=fetches;assert(!wd_try_arm(43,0,50000,fetch_state) && fetches==old_fetches);
 std::cout<<"PASS actual watchdog lifecycle: teardown disarms, late/racing watcher never accesses destroyed Lua, next level resumes\n";
 std::cout<<"PASS actual watchdog hook "<<cases<<" cases: loading bounded20min, client/server gameplay60s incl stale server precache, stack diagnostic/frame disarm/time wrap retained\n";
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'watchdog.cpp';exe=Path(tmp)/('watchdog.exe' if os.name=='nt' else 'watchdog')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
