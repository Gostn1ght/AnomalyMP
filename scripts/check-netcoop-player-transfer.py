"""Exercise the actual player cluster_move function with transfer I/O faults."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import re
import subprocess
if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
cluster = (root/"src/xrGame/netcoop_cluster.inc").read_text(encoding="utf-8")
a = cluster.index('static bool cluster_move(xrServer* server, xrClientData* CL, CLevelChanger* changer)\n{')
b = cluster.index('// -netcoop_cluster_selftest:', a)
body = cluster[a:b]
status_start = cluster.index('static LPCSTR cluster_target_problem(u32 port)\n{')
status_end = cluster.index('\nstatic bool cluster_secret()',status_start)
status_body = cluster[status_start:status_end]
status_ttl = re.search(r'static const u32 cluster_status_ttl_s\s*=\s*(\d+)\s*;',cluster).group(1)
engine = (root/"src/xrGame/netcoop.cpp").read_text(encoding="utf-8")
start = engine.index('static void store_money(xrClientData* CL)\n{')
end = engine.index('\nvoid server_on_client_disconnect(', start)
money = engine[start:end].replace('static void store_money(', 'static void captured_store_money(')
characters = (root/"src/xrGame/netcoop_characters.inc").read_text(encoding="utf-8")
inventory_start = characters.index('static bool character_inventory_complete(')
inventory_end = characters.index('\nstatic void character_capture_items(',inventory_start)
inventory_body = characters[inventory_start:inventory_end]
save_body = characters[characters.index('static bool character_save_actor('):characters.index('\nvoid server_character_save_actor(')]
assert save_body.index('character_inventory_complete(server, actor, 0, visited)') < save_body.index('character.items.clear()')
disconnect_start = engine.index('static void destroy_pending_actors(xrServer* server)\n{')
disconnect_end = engine.index('\nstruct StoreMoney',disconnect_start)
disconnect_body = engine[disconnect_start:disconnect_end]
give_start = engine.index('static void give_to_server(xrServer* server, CSE_Abstract* entity, u32 depth)\n{')
give_body = engine[give_start:disconnect_start].replace('give_to_server(', 'captured_give_to_server(')
disconnect_fixture = r'''
namespace disconnect_fixture {
template<class T>using xr_vector=std::vector<T>;
struct CInventoryOwner {virtual ~CInventoryOwner()=default;virtual void StopTalk(){}};
struct CGameObject {virtual ~CGameObject()=default;bool destroyed=false;void DestroyObject(){destroyed=true;}};
struct CActor:CGameObject,CInventoryOwner {bool alive=true;bool g_Alive()const{return alive;}bool IsTalking()const{return false;}CInventoryOwner* GetTalkPartner(){return nullptr;}};
template<class T,class P>T smart_cast(P* object){return dynamic_cast<T>(object);}
struct xrClientData {};
struct CSE_Abstract {u16 ID=7;xrClientData* owner=nullptr;std::vector<u16>children;};
struct Game {CSE_Abstract entity;std::map<u16,CSE_Abstract*>entries{{7,&entity}};CSE_Abstract* get_entity_from_eid(u16 id){auto found=entries.find(id);return found==entries.end()?nullptr:found->second;}};
struct xrServer {Game* game;xrClientData client;void* GetServerClient(){return &client;}};
struct StubObjects {CGameObject* actor=nullptr;CGameObject* net_Find(u16){return actor;}};
struct Runtime {StubObjects Objects;};
Runtime runtime;Runtime& Level(){return runtime;}bool g_pGameLevel=true;
struct Lock {int depth=0;void Enter(){++depth;}void Leave(){assert(depth>0);--depth;}};
Lock s_pending_lock;xr_vector<u16>s_pending_actor_destroy;
std::map<u16,xr_string>s_actor_character;
struct Leaving {u16 actor=0;};std::map<u32,Leaving>s_cluster_leaving;
bool save_ok=true;int saves=0,gives=0,releases=0,tasks=0;
bool cluster_actor_leaving(u16 actor){for(const auto& entry:s_cluster_leaving)if(entry.second.actor==actor)return true;return false;}
bool character_save_actor(u16,std::nullptr_t,bool){++saves;return save_ok;}
void cluster_lease_release(LPCSTR){++releases;}
void server_release_task_manager(u16){++tasks;}
void Msg(const char*,...){}
'''+give_body+r'''
void give_to_server(xrServer* server,CSE_Abstract* entity,u32 depth){++gives;captured_give_to_server(server,entity,depth);}
'''+disconnect_body+r'''
void reset(CActor& actor){actor.destroyed=false;actor.alive=true;runtime.Objects.actor=&actor;saves=gives=releases=tasks=0;save_ok=true;s_pending_actor_destroy={7};s_actor_character={{7,"tester:1"}};s_cluster_leaving.clear();}
void run(){
 Game game;xrServer server{&game,{}};CActor actor;
 reset(actor);save_ok=false;destroy_pending_actors(&server);
 assert(!actor.destroyed && s_actor_character.count(7)==1 && s_pending_actor_destroy==xr_vector<u16>{7});
 assert(saves==1 && gives==1 && releases==0 && tasks==0 && s_pending_lock.depth==0);
 save_ok=true;destroy_pending_actors(&server);
 assert(actor.destroyed && s_actor_character.empty() && s_pending_actor_destroy.empty());
 assert(saves==2 && gives==2 && releases==1 && tasks==1);
 reset(actor);actor.alive=false;save_ok=false;destroy_pending_actors(&server);
 assert(!actor.destroyed && s_pending_actor_destroy.size()==1 && releases==0);
 save_ok=true;destroy_pending_actors(&server);
 assert(!actor.destroyed && s_pending_actor_destroy.empty() && s_actor_character.empty() && releases==1 && tasks==0);
 reset(actor);s_actor_character.clear();s_cluster_leaving[5]={7};save_ok=false;destroy_pending_actors(&server);
 assert(actor.destroyed && saves==0 && releases==0 && s_cluster_leaving.empty());
 reset(actor);s_actor_character.clear();save_ok=false;destroy_pending_actors(&server);
 assert(actor.destroyed && saves==0 && s_pending_actor_destroy.empty());
 // Match the deepest valid inventory preflight: the ninth leaf also migrates
 // to the server, so no supported child retains a disconnected client owner.
 std::vector<CSE_Abstract> children(9);CSE_Abstract* parent=&game.entity;
 for(u16 i=0;i<9;++i){auto& child=children[i];child.ID=u16(20+i);parent->children.push_back(child.ID);game.entries[child.ID]=&child;parent=&child;}
 give_to_server(&server,&game.entity,0);
 for(const auto& child:children)assert(child.owner==&server.client);
 std::cout<<"PASS actual disconnect cleanup: failed tracked save retains actor/inventory/ownership for retry; success releases and destroys once; corpses and moved/untracked actors keep their policies\n";
}
}
'''
inventory_fixture = r'''
namespace inventory_fixture {
template<class T>using xr_vector=std::vector<T>;
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=1,ID_Parent=0xffff;std::vector<u16>children;};
struct CSE_ALifeInventoryItem:CSE_Abstract {};
template<class T>T smart_cast(CSE_Abstract* item){return dynamic_cast<T>(item);}
struct Game {std::map<u16,CSE_Abstract*>items;CSE_Abstract* get_entity_from_eid(u16 id){auto it=items.find(id);return it==items.end()?nullptr:it->second;}};
struct xrServer {Game* game;};
'''+inventory_body+r'''
struct Tree {
 Game game;xrServer server{&game};CSE_Abstract root;
 std::vector<std::unique_ptr<CSE_Abstract>>storage;
 CSE_Abstract* add(u16 id,CSE_Abstract* parent,bool inventory=true){
  std::unique_ptr<CSE_Abstract>item;
  if(inventory)item.reset(new CSE_ALifeInventoryItem);else item.reset(new CSE_Abstract);
  item->ID=id;item->ID_Parent=parent->ID;parent->children.push_back(id);
  auto result=item.get();game.items[id]=result;storage.push_back(std::move(item));return result;
 }
 bool complete(){xr_vector<u16>visited{root.ID};return character_inventory_complete(&server,&root,0,visited);}
};
void run(){
 {Tree t;assert(t.complete());t.add(2,&t.root);assert(t.complete());}
 {Tree t;t.root.children.push_back(2);assert(!t.complete());}
 {Tree t;auto item=t.add(2,&t.root);item->ID_Parent=3;assert(!t.complete());}
 {Tree t;auto item=t.add(2,&t.root);item->ID=3;assert(!t.complete());}
 {Tree t;t.add(2,&t.root,false);assert(!t.complete());}
 {Tree t;t.add(0xffff,&t.root);assert(!t.complete());}
 {Tree t;t.add(2,&t.root);t.root.children.push_back(2);assert(!t.complete());}
 {Tree t;auto item=t.add(2,&t.root);item->children.push_back(t.root.ID);assert(!t.complete());}
 {Tree t;for(u16 id=2;id<514;++id)t.add(id,&t.root);assert(t.complete());t.add(514,&t.root);assert(!t.complete());}
 {Tree t;CSE_Abstract* parent=&t.root;for(u16 id=2;id<11;++id)parent=t.add(id,parent);assert(t.complete());t.add(11,parent);assert(!t.complete());}
 std::cout<<"PASS actual inventory capture preflight: complete boundary, missing/foreign/non-item/duplicate/cycle/depth/count refusal\n";
}
}
'''
source = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <cassert>
#include <cstdint>
#include <map>
#include <string>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <iostream>
#include <algorithm>
#include <memory>
#include <vector>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned int;
using xr_string=std::string;using LPCSTR=const char*;using string_path=char[260];using string256=char[256];
template<size_t N>void xr_sprintf(char(&s)[N],const char* f,...) {va_list v;va_start(v,f);vsnprintf(s,N,f,v);va_end(v);}
int xr_strcmp(const char* a,const char* b){return std::strcmp(a,b);}
struct xrServer {};
namespace GameGraph {using _GRAPH_ID=u16;struct CVertex{u16 level_id()const{return 2;}};}
struct Id{u32 value()const{return 5;}};
struct CSE_ALifeTraderAbstract {u32 m_dwMoney=100;};
struct Owner : CSE_ALifeTraderAbstract {u16 ID=7;};
template<class T> T smart_cast(Owner* owner) {return static_cast<T>(owner);}
struct xrClientData{Owner* owner;Id ID;std::string netcoop_login="tester";u8 netcoop_character_slot=1;};
struct CLevelChanger {
 bool open=true;bool IsLevelChangerEnabled()const{return open;}
 GameGraph::_GRAPH_ID next_game_vertex()const{return 2;}u32 next_level_vertex()const{return 23;}
 int next_position()const{return 456;}int next_angles()const{return 789;}
};
struct SharedName {const char* operator*()const{return "target";}};
struct LevelName {SharedName name()const{return {};}};
struct Header {LevelName level(u16)const{return {};}};
struct Graph {bool valid_vertex_id(u16)const{return true;}const GameGraph::CVertex* vertex(u16)const{static GameGraph::CVertex v;return &v;}Header header()const{return {};}};
struct AI {Graph game_graph()const{return {};}};
AI ai(){return {};}
const char* cluster_current_level(){return "source";}
u32 cluster_port(){return 1267;}u32 real_time_ms(){return 100;}
bool location_ok=true,ticket_ok=true,save_ok=true,accounts_ok=true;
bool status_ok=true;
std::string target_status="100 0 16";
u32 cluster_now(){return 100;}
void cluster_dir(string_path& path){std::snprintf(path,sizeof(path),"cluster/");}
bool cluster_read_line(const char*,xr_string& value){value=target_status;return status_ok;}
std::string events, refusal;int saved_destination=0;
bool cluster_location(const char*,std::string& host,u32& port){host="localhost";port=1277;return location_ok;}
void cluster_refuse(xrServer*,xrClientData*,const char* message){refusal=message;events+='R';}
struct ClusterLeaving{u16 actor=0;u32 since=0;std::string level;};
std::map<u32,ClusterLeaving>s_cluster_leaving;
std::map<u16,int>s_character_restore,s_actor_character;
bool cluster_ticket_write(const char*,u8,const char*){events+='T';return ticket_ok;}
void cluster_file(const char*,const char*,u8,char* out){std::snprintf(out,260,"ticket");}
void DeleteFileA(const char*){events+='D';}
struct Account {bool has_money=false,touched=false;u32 money=0;};
Account account;bool s_accounts_dirty=false;
Account* account_find(const char*){return &account;}
bool server_client_leaving(xrClientData* client){return s_cluster_leaving.count(client->ID.value())!=0;}
void store_money(xrClientData*);bool accounts_save(){events+='A';return accounts_ok;}
struct CharacterDestination{u16 game_vertex;u32 level_vertex;int position,angles;};
bool character_save_actor(u16,const CharacterDestination* destination){
 events+='S';assert(!s_cluster_leaving.empty());
 assert(destination->game_vertex==2 && destination->level_vertex==23 && destination->position==456 && destination->angles==789);
 if(save_ok) saved_destination=2;
 return save_ok;
}
void cluster_lease_release(const char*){events+='L';}
void script_send_to_actor(u16,const char*,const char*){events+='N';assert(s_actor_character.empty());}
void Msg(const char*,...){}
'''+f'\nstatic const u32 cluster_status_ttl_s = {status_ttl};\n'+status_body+money+r'''
void store_money(xrClientData* client){events+='M';assert(!server_client_leaving(client));captured_store_money(client);}
'''+inventory_fixture+disconnect_fixture+body+r'''
void reset(){events.clear();refusal.clear();saved_destination=0;s_cluster_leaving.clear();s_character_restore.clear();s_actor_character[7]=1;ticket_ok=save_ok=location_ok=accounts_ok=status_ok=true;target_status="100 0 16";}
int main(){
 inventory_fixture::run();
 disconnect_fixture::run();
 xrServer server;Owner owner;xrClientData client;client.owner=&owner;CLevelChanger changer;
 reset();ticket_ok=false;
 assert(!cluster_move(&server,&client,&changer));
 assert(events=="TR" && saved_destination==0 && s_cluster_leaving.empty() && s_actor_character.count(7)==1);
 reset();accounts_ok=false;
 assert(!cluster_move(&server,&client,&changer));
 assert(events=="TMADR" && saved_destination==0 && s_cluster_leaving.empty() && s_actor_character.count(7)==1);
 reset();save_ok=false;
 assert(!cluster_move(&server,&client,&changer));
 assert(events=="TMASDR" && saved_destination==0 && s_cluster_leaving.empty() && s_actor_character.count(7)==1);
 reset();assert(cluster_move(&server,&client,&changer));
 assert(events=="TMASLN" && saved_destination==2 && s_cluster_leaving.count(5)==1 && s_actor_character.empty());
 assert(account.money==100 && account.has_money);
 account.money=20;account.touched=false;s_accounts_dirty=false;
 captured_store_money(&client); // old source disconnect after target spending
 assert(account.money==20 && !account.touched && !s_accounts_dirty);
 reset();s_character_restore[7]=1;assert(!cluster_move(&server,&client,&changer));assert(events=="R");
 reset();location_ok=false;assert(!cluster_move(&server,&client,&changer));assert(events=="R");
 reset();status_ok=false;assert(!cluster_move(&server,&client,&changer));assert(events=="R" && saved_destination==0 && s_cluster_leaving.empty());
 reset();target_status="0 0 16";assert(!cluster_move(&server,&client,&changer));assert(events=="R" && refusal.find("offline")!=std::string::npos);
 reset();target_status="100 15 16";assert(!cluster_move(&server,&client,&changer));assert(events=="R" && refusal.find("full")!=std::string::npos);
 reset();target_status="broken";assert(!cluster_move(&server,&client,&changer));assert(events=="R");
 reset();target_status="100 14 16";assert(cluster_move(&server,&client,&changer));assert(events=="TMASLN");
 reset();changer.open=false;assert(!cluster_move(&server,&client,&changer));assert(events=="R");
 std::cout<<"PASS actual player handoff: ticket failure preserves source, save failure cancels prepare/unfreezes, success freezes/saves/releases/redirects in order\n";
}
'''
with TemporaryDirectory(prefix="player-transfer-") as tmp:
    cpp=Path(tmp)/"check.cpp";exe=Path(tmp)/("check.exe" if os.name=="nt" else "check")
    cpp.write_text(source,encoding="utf-8")
    if os.name=="nt":
        command=["cl","/nologo","/std:c++17","/EHsc","/W4","/WX","/O2",str(cpp),"/Fe:"+str(exe),"/Fo:"+str(Path(tmp)/"check.obj")]
    else:
        command=["g++","-std=c++17","-Wall","-Wextra","-Werror","-O2",str(cpp),"-o",str(exe)]
    subprocess.run(command,check=True,cwd=tmp)
    subprocess.run([str(exe)],check=True,cwd=tmp)
