"""Actual Lua lighting getter/fallback and accepted owner-shot event branch."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
cpp=(root/'src/xrGame/script_game_object3.cpp').read_text(encoding='latin-1')
getter=cpp[cpp.index('float CScriptGameObject::GetLuminocity()'):cpp.index('void CScriptGameObject::ForceSetPosition(')]
engine=(root/'src/xrGame/netcoop.cpp').read_text(encoding='utf-8')
light=engine[engine.index('float server_luminocity('):engine.index('// Memory of a location server')]
weapon=(root/'src/xrGame/Weapon.cpp').read_text(encoding='latin-1')
branch=weapon[weapon.index('\tcase GE_NETCOOP_WPN_AIM:'):weapon.index('\tcase GE_ADDON_CHANGE:')]
source=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>
#include <limits>
using u32=uint32_t;
constexpr float EPS=0.00001f;
template<class T>T _max(T a,T b){return a>b?a:b;}
void clamp(float& v,float lo,float hi){v=v<lo?lo:v>hi?hi:v;}
struct Fvector{float x=0,y=0,z=0;
 void set(const Fvector& v){*this=v;}
 float square_magnitude()const{return x*x+y*y+z*z;}
 Fvector& normalize(){const float n=std::sqrt(square_magnitude());x/=n;y/=n;z/=n;return *this;}
 float distance_to(const Fvector& v)const{return std::sqrt((x-v.x)*(x-v.x)+(y-v.y)*(y-v.y)+(z-v.z)*(z-v.z));}
};
bool _valid(const Fvector& v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
struct ROS{float value=0;float get_luminocity(){return value;}};
struct CObject{virtual ~CObject()=default;ROS* ros=nullptr;Fvector pos;
 ROS* renderable_ROS(){return ros;}const Fvector& Position()const{return pos;}
};
struct CGameObject:CObject{};
struct Item{virtual ~Item()=default;};using PIItem=Item*;
struct CTorch:Item{bool active=false;bool torch_active()const{return active;}};
struct Inventory{std::vector<PIItem> m_all;};
struct CActor:CGameObject{Inventory bag;Inventory& inventory(){return bag;}};
template<class T,class U>T smart_cast(U* o){return dynamic_cast<T>(o);}
struct CEnvDescriptorMixer{Fvector sun_color,hemi_color,ambient;};
struct EnvironmentState{CEnvDescriptorMixer* CurrentEnv=nullptr;};
struct Persistent{EnvironmentState* pEnvironment=nullptr;EnvironmentState& Environment(){return *pEnvironment;}};
Persistent* g_pGamePersistent=nullptr;
struct CScriptGameObject{CGameObject* value=nullptr;CGameObject& object(){assert(value);return *value;}float GetLuminocity();};
namespace netcoop{
bool fixture_active=true,fixture_client=false,fixture_owns_hud=false;const CObject* fixture_owner=nullptr;
bool enabled(){return fixture_active;}bool pure_client(){return fixture_active&&fixture_client;}
bool server_player_copy(const CObject* o){return fixture_active&&!fixture_client&&o&&o==fixture_owner;}
bool client_owns_hud_item(const CObject*){return fixture_owns_hud;}
const CActor* fixture_scoped_actor=nullptr;
struct ServerVictimScope{
 const CActor* previous;
 explicit ServerVictimScope(CActor* actor):previous(fixture_scoped_actor){assert(server_player_copy(actor));fixture_scoped_actor=actor;}
 ~ServerVictimScope(){fixture_scoped_actor=previous;}
};
'''+light+r'''
}
'''+getter+r'''
struct NET_Packet{Fvector position,direction{0,0,1};unsigned reads=0;void r_vec3(Fvector& v){v=reads++?direction:position;}};
struct CHudItem{CGameObject hud;CGameObject& object(){return hud;}};
struct{u32 dwTimeGlobal=1000;}Device;
constexpr int GE_NETCOOP_WPN_AIM=0;
struct CWeapon:CHudItem{
 CObject* parent=nullptr;Fvector m_netcoop_aim_pos,m_netcoop_aim_dir;u32 m_netcoop_aim_time=0,m_netcoop_last_shot=0;
 unsigned iAmmoElapsed=1;std::vector<int> m_magazine{1};unsigned sounds=0,callbacks=0,bullets=0;
 CObject* H_Parent(){return parent;}bool OnServer(){return netcoop::enabled()&&!netcoop::pure_client();}
 void OnShot(){assert(bullets==0);if(OnServer())assert(netcoop::fixture_scoped_actor==parent);++sounds;++callbacks;}
 void FireTrace(const Fvector&,const Fvector& dir){assert(sounds==1&&callbacks==1&&std::fabs(dir.square_magnitude()-1)<1e-6f);++bullets;--iAmmoElapsed;m_magazine.pop_back();}
 void receive(NET_Packet& P){switch(GE_NETCOOP_WPN_AIM){
'''+branch+r'''
 }}
};
int main(){
 CActor owner;ROS ros;owner.ros=&ros;CScriptGameObject script;script.value=&owner;
 netcoop::fixture_owner=&owner;
 for(bool active:{false,true})for(bool client:{false,true}){
  netcoop::fixture_active=active;netcoop::fixture_client=client;
  ros.value=0.1f;const float expected=active&&!client?0.5f:0.1f;
  assert(std::fabs(script.GetLuminocity()-expected)<1e-6f);
 }
 netcoop::fixture_active=true;netcoop::fixture_client=false;
 CEnvDescriptorMixer env;EnvironmentState environment;environment.CurrentEnv=&env;
 Persistent persistent;persistent.pEnvironment=&environment;g_pGamePersistent=&persistent;
 ros.value=0;assert(script.GetLuminocity()==0.05f);
 env.sun_color={1,1,1};env.hemi_color={0.2f,0.2f,0.2f};env.ambient={0.1f,0.1f,0.1f};
 assert(std::fabs(script.GetLuminocity()-0.82f)<1e-6f);
 env.sun_color={};env.hemi_color={};env.ambient={};CTorch torch;torch.active=true;owner.bag.m_all={&torch};
 assert(script.GetLuminocity()==0.8f);torch.active=false;assert(script.GetLuminocity()==0.05f);
 ros.value=0.95f;assert(script.GetLuminocity()==0.95f);
 owner.ros=nullptr;assert(script.GetLuminocity()==0.05f);
 netcoop::fixture_client=true;assert(script.GetLuminocity()==0);owner.ros=&ros;
 netcoop::fixture_client=false;
 NET_Packet packet;packet.direction={0,0,2};CWeapon gun;gun.parent=&owner;
 gun.receive(packet);assert(gun.sounds==1&&gun.callbacks==1&&gun.bullets==1&&gun.iAmmoElapsed==0&&!netcoop::fixture_scoped_actor);
 packet.reads=0;gun.receive(packet);assert(gun.sounds==1&&gun.bullets==1);
 for(unsigned fault=0;fault<5;++fault){
  CWeapon rejected;rejected.parent=&owner;NET_Packet bad;
  if(fault==0)bad.position.x=4;
  if(fault==1)bad.position.x=std::numeric_limits<float>::quiet_NaN();
  if(fault==2)bad.direction={};
  if(fault==3)rejected.m_magazine.clear();
  if(fault==4)rejected.m_netcoop_last_shot=Device.dwTimeGlobal-10;
  rejected.receive(bad);assert(rejected.sounds==0&&rejected.callbacks==0&&rejected.bullets==0);
 }
 CGameObject npc;CWeapon other;other.parent=&npc;packet.reads=0;other.receive(packet);assert(other.sounds==0&&other.bullets==0);
 netcoop::fixture_client=true;CWeapon replica;replica.parent=&owner;packet.reads=0;replica.receive(packet);
 assert(replica.sounds==1&&replica.callbacks==1&&replica.bullets==0);
 netcoop::fixture_owns_hud=true;CWeapon own;own.parent=&owner;packet.reads=0;own.receive(packet);assert(own.sounds==0&&own.bullets==0);
 std::puts("PASS actual SDK lighting getter reuses native server weather/torch fallback; client/SP rendered light retained. Actual accepted owner shot runs ordinary sound/callback once before bullets; origin/direction/ammo/time/ownership and remote-HUD guards retained.");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'perception.cpp';exe=Path(tmp)/('perception.exe' if os.name=='nt' else 'perception')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
