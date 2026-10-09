"""Real crow packet transform and monster perception branch, CI compilation only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
crow = (root / 'src/xrGame/ai/crow/ai_crow.cpp').read_text(encoding='latin-1')
read = crow[crow.index('void CAI_Crow::net_Import('):crow.index('void CAI_Crow::HitSignal(')]
schedule = crow[crow.index('void CAI_Crow::shedule_Update('):crow.index('// Core events')]
assert 'netcoop::ServerActorScope netcoop_scope(this)' in schedule
assert schedule.index('deadNPCs.clear()') < schedule.index('deadNPCs.push_back(entity)')
monster = (root / 'src/xrGame/ai/monsters/monster_enemy_manager.cpp').read_text(encoding='latin-1')
vision = monster[monster.index('bool CMonsterEnemyManager::enemy_see_me_now()'):monster.index('bool CMonsterEnemyManager::is_faced(')]
source = r'''
#include <cassert>
#include <vector>
#include <cstdio>
#include <cmath>
#include <deque>
typedef unsigned u32; typedef int s32;
template<class T> using xr_deque = std::deque<T>;
struct Fvector{float x=0,y=0,z=0;void set(const Fvector& v){*this=v;}
 float distance_to(const Fvector& o)const{return std::sqrt((x-o.x)*(x-o.x)+(y-o.y)*(y-o.y)+(z-o.z)*(z-o.z));}};
inline bool _valid(const Fvector& v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
struct Fmatrix{Fvector c;void setHPB(float,float,float){c={};}};
struct NET_Packet{std::vector<float>values;unsigned cursor=0;
 float r_float(){return values.at(cursor++);}void r_float(float& v){v=r_float();}
 unsigned r_u32(){return unsigned(r_float());}unsigned char r_u8(){return (unsigned char)r_float();}
 void r_vec3(Fvector& v){v.x=r_float();v.y=r_float();v.z=r_float();}};
#define R_ASSERT(x) assert(x)
namespace netcoop {bool client=false;bool pure_client(){return client;}}
struct CAI_Crow{float fixture_health=0;unsigned id_Team=0,id_Squad=0,id_Group=0;Fmatrix matrix;
 struct NetcoopSample{u32 time;Fvector position;float yaw,pitch;};xr_deque<NetcoopSample> m_netcoop_samples;
 bool Remote(){return true;}bool g_Alive(){return fixture_health>0;}void SetfHealth(float v){fixture_health=v;}
 Fvector& Position(){return matrix.c;}Fmatrix& XFORM(){return matrix;}
 void net_Import(NET_Packet&);};
struct Memory{bool seen=false;bool visible_right_now(const void*){return seen;}
 Memory& visual(){return *this;}};
struct CEntityAlive{virtual ~CEntityAlive()=default;virtual struct CCustomMonster* cast_custom_monster(){return nullptr;}};
struct CCustomMonster:CEntityAlive{Memory store;Memory& memory(){return store;}CCustomMonster* cast_custom_monster()override{return this;}};
struct CActor:CEntityAlive{Memory store;Memory& memory(){return store;}};
CActor fixture_actor;CActor* Actor(){return &fixture_actor;}
namespace netcoop {bool dedicated=false,perceived=false;unsigned calls=0;
 bool server_player_copy(const CEntityAlive* o){return dedicated&&o==Actor();}
 bool server_player_sees(const CEntityAlive*,const CCustomMonster*){++calls;return perceived;}}
struct CMonsterEnemyManager{CEntityAlive* enemy=nullptr;CCustomMonster* monster=nullptr;bool enemy_see_me_now();};
''' + read + vision + r'''
int main(){
 CAI_Crow crow;NET_Packet p{{0.75f,100,0,18,-5,16,0.9f,0.9f,0.2f,0,1,2,3}};
 crow.net_Import(p);assert(crow.fixture_health==0.75f&&p.cursor==13);
 assert(crow.Position().x==18&&crow.Position().y==-5&&crow.Position().z==16);
 assert(crow.id_Team==1&&crow.id_Squad==2&&crow.id_Group==3&&crow.m_netcoop_samples.empty());
 // Pure client: the first snapshot places the crow, later ones are kept for
 // interpolation (UpdateWorkload) instead of snapping the crow there.
 netcoop::client=true;CAI_Crow remote;
 NET_Packet a{{1.f,100,0,10,20,30,0.5f,0.5f,0.1f,0,1,2,3}};remote.net_Import(a);
 assert(remote.Position().x==10&&remote.m_netcoop_samples.size()==1);
 NET_Packet b{{1.f,200,0,12,20,30,0.5f,0.5f,0.1f,0,1,2,3}};remote.net_Import(b);
 assert(remote.Position().x==10&&remote.m_netcoop_samples.size()==2&&b.cursor==13);
 NET_Packet old{{1.f,150,0,99,20,30,0.5f,0.5f,0.1f,0,1,2,3}};remote.net_Import(old);
 assert(remote.m_netcoop_samples.size()==2);
 NET_Packet far{{1.f,300,0,500,20,30,0.5f,0.5f,0.1f,0,1,2,3}};remote.net_Import(far);
 assert(remote.m_netcoop_samples.size()==1&&remote.Position().x==500);
 netcoop::client=false;
 CCustomMonster beast,npc;CMonsterEnemyManager manager;manager.monster=&beast;manager.enemy=Actor();
 netcoop::dedicated=true;netcoop::perceived=true;assert(manager.enemy_see_me_now()&&netcoop::calls==1);
 netcoop::perceived=false;assert(!manager.enemy_see_me_now()&&netcoop::calls==2);
 netcoop::dedicated=false;fixture_actor.store.seen=true;assert(manager.enemy_see_me_now());
 npc.store.seen=true;manager.enemy=&npc;assert(manager.enemy_see_me_now());
 CEntityAlive ordinary;manager.enemy=&ordinary;assert(!manager.enemy_see_me_now());
 std::puts("PASS actual crow packet position (client snapshots kept for interpolation, jumps placed) and monster scoped-player perception; SP/NPC memory preserved");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'crow.cpp'; exe = Path(tmp) / ('crow.exe' if os.name == 'nt' else 'crow')
    cpp.write_text(source, encoding='utf-8')
    command = (['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
               ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True)
    subprocess.run([str(exe)],cwd=tmp,check=True)
