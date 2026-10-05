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
'''+body+r'''
void reset(){events.clear();refusal.clear();saved_destination=0;s_cluster_leaving.clear();s_character_restore.clear();s_actor_character[7]=1;ticket_ok=save_ok=location_ok=accounts_ok=status_ok=true;target_status="100 0 16";}
int main(){
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
