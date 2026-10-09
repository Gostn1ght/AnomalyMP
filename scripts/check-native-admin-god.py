"""Actual connection-scoped god functions and actor condition predicate, GHA only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
native=(root/'src/xrGame/netcoop.cpp').read_text(encoding='latin-1')
owner=native[native.index('struct FindActorOwner\n'):native.index('void server_forward_news(',native.index('struct FindActorOwner\n'))]
start=native.index('static xr_set<u16> s_admin_god_actors;')
end=native.index('bool script_respawn(',start)
if 'bool script_admin_teleport(' in native[start:end]:
    end=native.index('bool script_admin_teleport(',start)
methods=native[start:end]
condition=(root/'src/xrGame/ActorCondition.cpp').read_text(encoding='latin-1')
predicate=condition[condition.index('BOOL GodMode('):condition.index('CActorCondition::CActorCondition(')]
assert 'netcoop_admin_god = false;' in (root/'src/xrGame/xrServer.cpp').read_text()
assert 'GodMode()' not in condition
burer=(root/'src/xrGame/ai/monsters/burer/burer.cpp').read_text(encoding='latin-1')
burer_guard=burer[burer.index('void xr_stdcall CBurer::StaminaHit()'):burer.index('\tCWeapon* const active_weapon',burer.index('void xr_stdcall CBurer::StaminaHit()'))]
controller=(root/'src/xrGame/ai/monsters/controller/controller.cpp').read_text(encoding='latin-1')
controller_hit=controller[controller.index('void CController::HitEntity('):controller.index('bool CController::tube_ready()',controller.index('void CController::HitEntity('))]
spawn=(root/'src/xrGame/xrServer_process_spawn.cpp').read_text(encoding='latin-1')
bind=spawn[spawn.index('// PROCESS NAME;'):spawn.index('// PROCESS RP;')]
source=r'''
#include <cassert>
#include <cstdio>
#include <map>
#include <set>
#include <vector>
using u16=unsigned short;using BOOL=int;
constexpr int FALSE=0,eGameIDSingle=1,AF_GODMODE=1,AF_GODMODE_RT=2;
template<class T>using xr_set=std::set<T>;
struct CObject{virtual ~CObject()=default;};
struct CEntity:CObject{};
struct Conditions{float power=1;unsigned hits=0;void PowerHit(float,bool){++hits;}float GetPower()const{return power;}};
struct Inventory{bool accepts=false;unsigned actions=0;bool Action(u16,int){++actions;return accepts;}};
struct CActor:CEntity{u16 id=0;bool alive=true;::Conditions cond;::Inventory inv;unsigned drops=0;
 u16 ID()const{return id;}bool g_Alive()const{return alive;}
 ::Conditions& conditions(){return cond;}::Inventory& inventory(){return inv;}void g_PerformDrop(){++drops;}};
constexpr int M_SPAWN_OBJECT_ASPLAYER=1;
struct Owner{u16 ID=0;struct {bool player=true;bool is(int)const{return player;}}s_flags;};
struct IClient{virtual ~IClient()=default;};
struct xrClientData:IClient{struct {bool bLocal=false;}flags;Owner* owner=nullptr;int netcoop_role=0;bool netcoop_admin_god=false;
 unsigned clears=0;void ClearInputState(){++clears;}};
template<class T>T smart_cast(CObject* o){return dynamic_cast<T>(o);}
'''+owner+r'''
struct Server{std::vector<IClient*> clients;unsigned scans=0;
 template<class F>IClient* FindClient(F f){++scans;for(auto* c:clients)if(f(c))return c;return nullptr;}
};
struct Objects{std::map<u16,CObject*> values;CObject* net_Find(u16 id){auto i=values.find(id);return i==values.end()?nullptr:i->second;}};
struct World{::Server* Server=nullptr;::Objects Objects;}world;
bool g_pGameLevel=true,enabled_flag=true,pure_flag=false;int game_kind=eGameIDSingle;
World& Level(){return world;}int GameID(){return game_kind;}
struct {int flags=0;bool test(int mask)const{return (flags&mask)!=0;}}psActorFlags;
namespace netcoop{
 constexpr int role_admin=2;
 bool enabled(){return enabled_flag;}bool pure_client(){return pure_flag;}
'''+methods+r'''
}
void bind_owner(xrClientData* CL,Owner* E){
'''+bind+r'''
}
'''+predicate+r'''
CActor* current_actor=nullptr;CActor* Actor(){return current_actor;}
#define xr_stdcall
struct CBurer{unsigned effects=0;void StaminaHit();};
'''+burer_guard+r'''
 ++effects;
}
struct Fvector{};namespace ALife{enum EHitType{hit};}
constexpr int kDROP=1,CMD_STOP=2;
struct BaseMonster{unsigned forwarded=0;void HitEntity(const CEntity*,float,float,Fvector&,ALife::EHitType,bool){++forwarded;}};
struct CController:BaseMonster{using inherited=BaseMonster;float m_stamina_hit=2;
 void HitEntity(const CEntity*,float,float,Fvector&,ALife::EHitType,bool);};
'''+controller_hit+r'''
int main(){
 Server server;world.Server=&server;
 CActor admin,player,dummy;admin.id=7;player.id=8;dummy.id=0;
 Owner ao,po;ao.ID=7;po.ID=8;
 xrClientData ac,pc;ac.owner=&ao;ac.netcoop_role=2;pc.owner=&po;pc.netcoop_role=1;
 server.clients={&ac,&pc};world.Objects.values={{u16(7),&admin},{u16(8),&player}};
 assert(netcoop::script_admin_god_set(7,true));
 assert(netcoop::script_admin_god_enabled(7));
 assert(!netcoop::script_admin_god_set(8,true)&&!pc.netcoop_admin_god);
 psActorFlags.flags=AF_GODMODE|AF_GODMODE_RT;
 assert(GodMode(&admin)&&!GodMode(&player)&&GodMode(&dummy));
 CBurer b;CController c;Fvector dir;current_actor=&admin;
 b.StaminaHit();c.HitEntity(&admin,1,1,dir,ALife::hit,true);
 assert(b.effects==0&&admin.cond.hits==0&&admin.inv.actions==0&&admin.drops==0&&c.forwarded==1);
 current_actor=&player;b.StaminaHit();c.HitEntity(&player,1,1,dir,ALife::hit,true);
 assert(b.effects==1&&player.cond.hits==1&&player.inv.actions==1&&player.drops==1&&c.forwarded==2);
 c.HitEntity(&admin,1,1,dir,ALife::hit,true);
 assert(player.cond.hits==1&&c.forwarded==3); // non-current target keeps ordinary forwarding
 player.inv.accepts=true;c.HitEntity(&player,1,1,dir,ALife::hit,true);
 assert(player.cond.hits==2&&player.inv.actions==2&&player.drops==1&&c.forwarded==4);
 CActor next;next.id=9;Owner no;no.ID=9;world.Objects.values[u16(9)]=&next;
 bind_owner(&ac,&no);assert(ac.owner==&no&&ac.clears==1&&GodMode(&next)&&!GodMode(&admin)&&!GodMode(&player));
 bind_owner(&ac,&no);assert(ac.clears==1&&GodMode(&next));
 Owner nonplayer;nonplayer.ID=10;nonplayer.s_flags.player=false;
 bind_owner(&ac,&nonplayer);assert(ac.owner==&no&&GodMode(&next));
 bind_owner(&ac,&no);ac.netcoop_role=1;bind_owner(&ac,&no);assert(!GodMode(&next));
 ac.netcoop_role=2;ac.netcoop_admin_god=false;bind_owner(&ac,&no);assert(!GodMode(&next));
 bind_owner(&ac,&ao);assert(netcoop::script_admin_god_set(7,true));
 assert(netcoop::script_admin_god_set(7,true)&&netcoop::script_admin_god_set(7,true));
 assert(netcoop::script_admin_god_set(7,false)&&!GodMode(&admin));
 const unsigned scans=server.scans;
 for(int i=0;i<64000;++i)assert(!GodMode(&player));
 assert(server.scans==scans); // normal-player condition checks do not scan clients
 assert(netcoop::script_admin_god_set(7,true));ac.netcoop_role=1;
 assert(!netcoop::script_admin_god_enabled(7)&&!GodMode(&admin));
 ac.netcoop_role=2;ac.netcoop_admin_god=false; // actual Clear resets the connection field
 assert(!netcoop::script_admin_god_enabled(7));
 admin.alive=false;assert(!netcoop::script_admin_god_set(7,true));admin.alive=true;
 assert(!netcoop::script_admin_god_set(65535,true));
 ao.ID=9;assert(!netcoop::script_admin_god_set(7,true));ao.ID=7;
 ac.flags.bLocal=true;assert(!netcoop::script_admin_god_set(7,true));ac.flags.bLocal=false;
 for(int disabled=0;disabled<3;++disabled){
  enabled_flag=disabled!=0;pure_flag=disabled==1;g_pGameLevel=disabled!=2;
  assert(!netcoop::script_admin_god_set(7,true)&&!netcoop::script_admin_god_enabled(7));
 }
 enabled_flag=true;pure_flag=false;g_pGameLevel=true;world.Server=nullptr;
 assert(!netcoop::script_admin_god_set(7,true));world.Server=&server;
 unsigned cases=0;
 for(int enabled=0;enabled<2;++enabled)for(int pure=0;pure<2;++pure)
 for(int kind=0;kind<2;++kind)for(int flags=0;flags<4;++flags){
  enabled_flag=enabled!=0;pure_flag=pure!=0;game_kind=kind;psActorFlags.flags=flags;
  assert((GodMode(&player)!=FALSE)==((enabled&&!pure)?false:kind==eGameIDSingle&&flags!=0));
  ++cases;
 }
 std::printf("PASS actual admin god: connection/actor/role isolation, actual owner binding/respawn hints, burer guard/controller stamina-drop path, revoke/reconnect/dead/missing guards, idempotent on/off,64000 ordinary checks without client scans, %u SP/client predicate cases\n",cases);
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'god.cpp';exe=Path(tmp)/('god.exe' if os.name=='nt' else 'god')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
