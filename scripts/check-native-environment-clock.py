"""Actual display-clock methods and packet import, compiled only in GitHub Actions."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
base=(root/'src/xrGame/game_base.cpp').read_text(encoding='latin-1')
methods=base[base.index('ALife::_TIME_ID game_GameState::GetGameTime()'):]
assert methods.rstrip().endswith('}')
assert 'm_environment_monotonic_start = Device.dwTimeContinual;' in base[base.index('game_GameState::game_GameState()'):base.index('CLASS_ID game_GameState::getCLASS_ID(')]
client=(root/'src/xrGame/game_cl_base.cpp').read_text(encoding='latin-1')
start=client.index('void game_cl_GameState::net_import_GameTime(')
packet=client[start:client.index('struct not_exsiting_clients_deleter',start)]
environment=(root/'src/xrEngine/Environment.cpp').read_text(encoding='latin-1')
start=environment.index('float CEnvironment::TimeDiff(')
diff=environment[start:environment.index('float CEnvironment::TimeWeight(',start)]
start=environment.index('void CEnvironment::SetGameTime(')
set_env=environment[start:environment.index('float CEnvironment::NormalizeTime(',start)]
source=r'''
#define _EDITOR
#include <cassert>
#include <cmath>
#include <cstdio>
#include <algorithm>
#include <cstdint>
using u64=std::uint64_t;using s64=std::int64_t;using u32=std::uint32_t;using s32=std::int32_t;
namespace ALife{using _TIME_ID=u64;}
template<class T>T _max(T a,T b){return std::max(a,b);}template<class T>T _min(T a,T b){return std::min(a,b);}
bool pure=true;namespace netcoop{bool pure_client(){return pure;}}
struct {u32 dwTimeContinual=0;}Device;
struct game_GameState{
 u64 m_qwStartGameTime=0,m_qwStartProcessorTime=0,m_qwEStartGameTime=0,m_qwEStartProcessorTime=0;
 u32 m_environment_monotonic_start=0;float m_fTimeFactor=6,m_fETimeFactor=6;
 u64 GetGameTime();float GetGameTimeFactor();void SetGameTimeFactor(float);void SetGameTimeFactor(u64,float);
 u64 GetEnvironmentGameTime();float GetEnvironmentGameTimeFactor();void SetEnvironmentGameTimeFactor(float);void SetEnvironmentGameTimeFactor(u64,float);
};
constexpr float DAY_LENGTH=86400.f;
struct CEnvironment{bool bWFX=true;float wfx_time=20000,fGameTime=0,fTimeFactor=6;unsigned invalidations=0;
 float TimeDiff(float,float);void SetGameTime(float,float);void Invalidate(){++invalidations;}};
'''+diff+set_env+r'''
struct NET_Packet{u64 game,env;float factor,env_factor;unsigned u=0,f=0;
 void r_u64(u64& value){value=u++?env:game;}void r_float(float& value){value=f++?env_factor:factor;}};
struct game_cl_GameState:game_GameState{bool m_netcoop_environment_synced=false;void net_import_GameTime(NET_Packet&);};
struct World{game_cl_GameState* state=nullptr;u32 async=0;
 u32 timeServer_Async(){return async;}u64 GetEnvironmentGameTime(){return state->GetEnvironmentGameTime();}
 void SetGameTimeFactor(u64 t,float f){state->SetGameTimeFactor(t,f);}
 void SetEnvironmentGameTimeFactor(u64 t,float f){state->SetEnvironmentGameTimeFactor(t,f);}}world;
World& Level(){return world;}CEnvironment env;
struct Persistent{CEnvironment& Environment(){return env;}}persistent;Persistent& GamePersistent(){return persistent;}
'''+methods+packet+r'''
int main(){
 game_cl_GameState state;world.state=&state;
 // The old -100ms packet correction consumes almost a day during active WFX.
 assert(env.TimeDiff(40000.f,39999.9f)>86399.f);
 const u64 origin=(1'500'000'000'000ULL/86400000)*86400000+86'395'000ULL;
 NET_Packet initial{origin,origin,60,60};state.net_import_GameTime(initial);
 env.fGameTime=float(origin%86400000)/1000.f;u64 previous=origin;
 for(u32 frame=1;frame<=7200;++frame){
  Device.dwTimeContinual=frame*17;world.async=Device.dwTimeContinual+u32(frame%3)*80;
  const u64 authority=origin+u64(Device.dwTimeContinual)*60;
  if(frame%3==0){
   const s64 jitter=(frame%6==0)?-1000:1000;
   NET_Packet p{authority,u64(s64(authority)+jitter),60,60};state.net_import_GameTime(p);
   assert(state.m_qwStartGameTime==authority); // authoritative gameplay calendar is not slewed
  }
  const u64 displayed=state.GetEnvironmentGameTime();
  assert(displayed>=previous&&displayed-previous<=1123);
  assert(std::abs(s64(displayed)-s64(authority))<6000);
  env.SetGameTime(float(displayed%86400000)/1000.f,state.GetEnvironmentGameTimeFactor());
  assert(env.wfx_time>12000&&env.invalidations==0);
  previous=displayed;
 }
 // A scale change adjusts rate without changing the displayed phase at receipt.
 const u64 held=state.GetEnvironmentGameTime();
 NET_Packet scale{held,held,10,10};state.net_import_GameTime(scale);
 assert(state.GetEnvironmentGameTime()==held&&state.GetEnvironmentGameTimeFactor()==10);
 Device.dwTimeContinual+=100;assert(state.GetEnvironmentGameTime()==held+1000);
 const u64 jumped=state.GetEnvironmentGameTime()+120000;
 NET_Packet forward{jumped,jumped,6,6};state.net_import_GameTime(forward);
 assert(state.GetEnvironmentGameTime()==jumped);
 NET_Packet backward{jumped-90000,jumped-90000,6,6};state.net_import_GameTime(backward);
 assert(state.GetEnvironmentGameTime()==jumped-90000&&env.invalidations==1);
 Device.dwTimeContinual=0xfffffff0u;state.SetEnvironmentGameTimeFactor(origin,6);
 Device.dwTimeContinual+=100;assert(state.GetEnvironmentGameTime()==origin+600);
 // SP/non-netcoop retain their original network-clock and packet behavior.
 pure=false;world.async=100;state.SetEnvironmentGameTimeFactor(origin,6);
 Device.dwTimeContinual+=10000;world.async=200;assert(state.GetEnvironmentGameTime()==origin+600);
 NET_Packet sp{origin,origin,6,6};state.net_import_GameTime(sp);
 assert(state.GetEnvironmentGameTime()==origin&&env.invalidations==2);
 std::puts("PASS actual environment clock: 7200 jittered frames, monotonic display across midnight/WFX, untouched authoritative calendar, phase-continuous scale, explicit jumps,32-bit mono wrap, SP retained");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'environment_clock.cpp';exe=Path(tmp)/('environment_clock.exe' if os.name=='nt' else 'environment_clock')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
