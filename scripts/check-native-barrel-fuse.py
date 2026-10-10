"""Actual explosive fuse and event generation: sleeping remote barrel authority."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
def function(path,signature):
 text=(root/path).read_text();start=text.index(signature);brace=text.index('{',start);depth=1;end=brace+1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
source=r'''
#include <cassert>
#include <cstdio>
#include <cmath>
#include <cstdint>
using u16=uint16_t;using u32=uint32_t;
#define ICF inline
#define VERIFY(x) assert(x)
#define TRUE true
#define FALSE false
struct Flags8{unsigned value=0;void assign(unsigned v){value=v;}void set(unsigned bit,bool on){if(on)value|=bit;else value&=~bit;}bool test(unsigned bit){return (value&bit)!=0;}};
bool fis_zero(float x){return std::abs(x)<0.00001f;}
struct{float fTimeGlobal=100;}Device;
namespace netcoop{bool active=true,client=false;bool enabled(){return active;}bool pure_client(){return active&&client;}}
bool OnClient(){return netcoop::client;}
template<class...T>void Msg(const char*,T...){}
struct Fvector{};
struct Object{u16 ID(){return 7;}bool Remote(){return true;}void u_EventGen(struct NET_Packet&,unsigned,unsigned){}void u_EventSend(struct NET_Packet&);};
struct NET_Packet{void w_u16(u16){}void w_vec3(const Fvector&){}};
unsigned events=0;void Object::u_EventSend(NET_Packet&){++events;}
constexpr unsigned GE_GRENADE_EXPLODE=1,BI_NONE=0;
struct SHit{float power;Object*who;};
struct Inventory{
 float condition=1;unsigned processing=0;
 void Hit(SHit*hit){condition-=hit->power;if(condition<0)condition=0;}
 float GetCondition(){return condition;}void ChangeCondition(float change){condition+=change;if(condition<0)condition=0;if(condition>1)condition=1;}
 void processing_activate(){++processing;}u16 ID(){return 11;}struct{const char*c_str(){return "explosive_barrel";}}name;
 decltype(name)& cNameSect(){return name;}void* lua_game_object(){return nullptr;}
};
namespace luabind{template<class T>struct functor{void operator()(void*){}};}
struct ScriptEngine{template<class T>bool functor(const char*,T&){return false;}};
struct Ai{ScriptEngine engine;ScriptEngine&script_engine(){return engine;}}ai_value;
Ai&ai(){return ai_value;}
struct CParticlesPlayer{static void StopParticles(u16,unsigned,bool){}};
class CExplosive{
 Object object;u16 initiator=0xffff;Flags8 m_explosion_flags;static const unsigned flExplodEventSent=1;
public:
 u16 Initiator(){return initiator;}void SetInitiator(u16 id){initiator=id;}void FindNormal(Fvector&){}
 Object*cast_game_object(){return &object;}void GenExplodeEvent(const Fvector&,const Fvector&);
};
'''
source+=(root/'src/xrGame/DelayedActionFuse.h').read_text().replace('#pragma once','')
source+=r'''
class CExplosiveItem:public Inventory,public CDelayedActionFuse,public CExplosive{
 using inherited=Inventory;
public:
 void Hit(SHit*);void UpdateFuse();void ChangeCondition(float change)override{Inventory::ChangeCondition(change);}
 void StartTimerEffects()override{}Fvector position;Fvector&Position(){return position;}
};
'''
for signature in ('CDelayedActionFuse::CDelayedActionFuse()','void CDelayedActionFuse::SetTimer(','void CDelayedActionFuse::Initialize(','bool CDelayedActionFuse::Update('):
 source+='\n'+function('src/xrGame/DelayedActionFuse.cpp',signature)
source+='\n'+function('src/xrGame/ExplosiveItem.cpp','void CExplosiveItem::Hit(')
source+='\n'+function('src/xrGame/ExplosiveItem.cpp','void CExplosiveItem::UpdateFuse(')
source+='\n'+function('src/xrGame/Explosive.cpp','void CExplosive::GenExplodeEvent(')
source+=r'''
int main(){
 Object shooter;CExplosiveItem barrel;barrel.Initialize(5,0.5f);SHit hit{0.6f,&shooter};
 barrel.Hit(&hit);assert(barrel.isActive()&&barrel.processing==1&&barrel.Initiator()==7);
 Device.fTimeGlobal=104;barrel.UpdateFuse();assert(events==0);
 Device.fTimeGlobal=106;barrel.UpdateFuse();assert(events==1&&!barrel.isActive());
 barrel.UpdateFuse();assert(events==1);
 CExplosiveItem replica;replica.Initialize(5,0.5f);netcoop::client=true;
 hit.power=1;replica.Hit(&hit);assert(replica.GetCondition()==1&&!replica.isActive()&&replica.processing==0);
 replica.UpdateFuse();assert(events==1);netcoop::client=false;
 CExplosiveItem environment;environment.Initialize(5,0.5f);hit.power=1;hit.who=nullptr;environment.Hit(&hit);
 assert(environment.Initiator()==11&&environment.isActive());
 Device.fTimeGlobal=112;environment.UpdateFuse();assert(events==2);
 netcoop::active=false;CExplosive vanilla;vanilla.SetInitiator(7);Fvector vector;
 vanilla.GenExplodeEvent(vector,vector);assert(events==2); // SP remote guard retained
 std::puts("PASS actual barrel fuse: remote authority emits explosion, frame-driven waking, no duplicate, client damage disabled, missing hitter safe and stock remote guard retained");
}
'''
with TemporaryDirectory() as tmp:
 cpp=Path(tmp)/'barrel.cpp';exe=Path(tmp)/('barrel.exe' if os.name=='nt' else 'barrel');cpp.write_text(source)
 command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
          ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
 subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
