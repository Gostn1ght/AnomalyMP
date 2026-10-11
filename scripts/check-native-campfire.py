"""Actual campfire authority, fuel deadlines, replication and session reset (CI only)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
# Also verify that the tested reset is wired after transport/object teardown.
stop = (root / "src/xrGame/Level_network.cpp").read_text()
assert stop.index("netcoop::campfires_reset();") > stop.index("Server->Disconnect();")
source = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <vector>
#include <string>
#include <cmath>
#include <utility>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;using u64=unsigned long long;
using LPCSTR=const char*;
template<class K,class V>using xr_map=std::map<K,V>;
template<class T>using xr_vector=std::vector<T>;
template<class T,class U>T smart_cast(U* p){return dynamic_cast<T>(p);}
int xr_strcmp(const char* a,const char* b){return std::strcmp(a,b);}
template<class...T>void Msg(const char*,T...){}
constexpr bool TRUE=true;constexpr unsigned M_NETCOOP_CAMPFIRE=21;
unsigned net_flags(bool,bool){return 0;}
struct NET_Packet{
 std::vector<u8> bytes;unsigned pos=0;
 u32 r_elapsed(){return u32(bytes.size())-pos;}
 u8 r_u8(){assert(r_elapsed());return bytes[pos++];}
 u16 r_u16(){u16 v=r_u8();return u16(v|(u16(r_u8())<<8));}
 void w_u8(u8 v){bytes.push_back(v);}void w_u16(u16 v){w_u8(u8(v));w_u8(u8(v>>8));}
 void w_begin(unsigned v){bytes.clear();pos=0;w_u16(u16(v));}
};
struct Vec{float x=0;float distance_to(const Vec& p) const{return std::fabs(x-p.x);}};
struct Object{
 virtual ~Object()=default;u16 id=0;bool destroyed=false;Vec p;const char* section="matches";
 u16 ID(){return id;}Vec& Position(){return p;}const char* cNameSect(){return section;}
 bool getDestroy(){return destroyed;}void DestroyObject(){destroyed=true;}
};
struct Item:Object{Object& object(){return *this;}};using PIItem=Item*;
struct CEatableItem:Item{u8 uses=2;u8 GetRemainingUses(){return uses;}void SetRemainingUses(u8 v){uses=v;}};
struct CActor:Object{bool alive=true;struct{std::vector<PIItem>m_all;}inv;
 bool g_Alive(){return alive;}auto& inventory(){return inv;}};
namespace netcoop{void server_campfire_changed(u16,bool);bool client=false;bool pure_client(){return client;}}
struct CZoneCampfire:Object{
 bool on=false;unsigned applied=0;
 bool is_on(){return on;}void turn_on_script(){on=true;netcoop::server_campfire_changed(id,true);}
 void turn_off_script(){on=false;netcoop::server_campfire_changed(id,false);}
 void netcoop_apply(bool v){on=v;++applied;}
};
struct IClient{virtual ~IClient()=default;};
struct ClientID{u32 n=1;u32 value(){return n;}ClientID& operator=(u32 v){n=v;return *this;}};
struct Owner{u16 ID=1;}owner;
struct xrClientData:IClient{ClientID ID;struct{bool bConnected=true;}flags;
 bool gamma_snapshot_ready=true;Owner* owner=&::owner;std::string netcoop_login="test";};
struct xrServer{
 xrClientData local;std::vector<xrClientData*>clients;std::vector<NET_Packet>sent;
 xrClientData* GetServerClient(){return &local;}
 template<class F>void ForEachClientDo(F& f){for(auto* c:clients)f(c);}
 void SendTo(ClientID,NET_Packet& p,unsigned){sent.push_back(p);}
};
struct GameLevel{
 xrServer* Server=nullptr;struct{std::map<u16,Object*>all;Object* net_Find(u16 id){auto i=all.find(id);return i==all.end()?nullptr:i->second;}}Objects;
 u64 game_time=1000;u64 GetGameTime(){return game_time;}std::vector<NET_Packet>sent;
 void Send(NET_Packet& p,unsigned){sent.push_back(p);}
}level;
GameLevel* g_pGameLevel=&level;GameLevel& Level(){return level;}
struct{u32 dwTimeGlobal=1;}Device;
unsigned touches=0;void server_item_touch(u16){++touches;}
namespace netcoop{
'''
source += (root / "src/xrGame/netcoop_campfire.inc").read_text(encoding="utf-8")
source += r'''
}
int main(){using namespace netcoop;
 xrServer server;level.Server=&server;xrClientData cl;server.clients.push_back(&cl);
 CActor actor;actor.id=1;CZoneCampfire fire;fire.id=7;
 level.Objects.all={{u16(1),&actor},{u16(7),&fire}};
 CEatableItem empty;empty.id=3;empty.uses=0;CEatableItem matches;matches.id=4;
 actor.inv.m_all={&empty,&matches};
 auto request=[&](u8 on){NET_Packet p{{7,0,on}};server_on_campfire(&server,&cl,p);};
 request(2);assert(!fire.on && matches.uses==2);
 matches.destroyed=true;request(1);assert(!fire.on);matches.destroyed=false;
 actor.p.x=4;request(1);assert(!fire.on);actor.p.x=0;
 actor.alive=false;request(1);assert(!fire.on);actor.alive=true;
 request(1);assert(fire.on && matches.uses==1 && touches==1 && !empty.destroyed);
 const u64 deadline=s_campfire_fuel_end.at(7);assert(deadline==1000+campfire_fuel_ms);
 request(1);assert(matches.uses==1 && s_campfire_fuel_end.at(7)==deadline);
 // A late join gets the same current burning state, once.
 server.sent.clear();server_campfires_update(&server);assert(server.sent.size()==1);
 server_campfires_update(&server);assert(server.sent.size()==1);
 Device.dwTimeGlobal=2001;level.game_time=deadline-1;server_campfires_update(&server);assert(fire.on);
 Device.dwTimeGlobal=4001;level.game_time=deadline;server_campfires_update(&server);
 assert(!fire.on && s_campfire_fuel_end.empty());
 request(1);assert(fire.on && matches.destroyed);request(0);assert(!fire.on && s_campfire_fuel_end.empty());
 request(1);assert(!fire.on);
 NET_Packet short_request{{7,0}};server_on_campfire(&server,&cl,short_request);assert(!fire.on);
 // Replication before spawn is deferred; malformed list is rejected atomically.
 client=true;NET_Packet pending{{1,0,8,0,1}};client_on_campfire(pending);
 CZoneCampfire later;later.id=8;client_campfire_spawned(&later);assert(later.on && later.applied==1);
 NET_Packet bad{{2,0,7,0,1}};client_on_campfire(bad);assert(!fire.on);
 NET_Packet direct{{1,0,7,0,1}};client_on_campfire(direct);assert(fire.on);
 // Stale ids and deadlines cannot survive level/reconnect teardown.
 s_campfire_pending[9]=true;campfires_reset();
 assert(s_campfires.empty() && s_campfire_synced.empty() && s_campfire_pending.empty() && s_campfire_fuel_end.empty() && s_campfire_fuel_next==0);
 CZoneCampfire reused;reused.id=9;client_campfire_spawned(&reused);assert(!reused.on && reused.applied==0);
 client=false;fire.on=false;level.game_time=5;Device.dwTimeGlobal=1;matches.destroyed=false;matches.uses=2;
 request(1);assert(s_campfire_fuel_end.at(7)==5+campfire_fuel_ms);
 server.sent.clear();server_campfires_update(&server);assert(server.sent.size()==1);
 // GAMMA extinguishes and later relights its own fire without inheriting fuel.
 fire.turn_off_script();assert(s_campfire_fuel_end.empty());fire.turn_on_script();
 level.game_time+=campfire_fuel_ms;Device.dwTimeGlobal+=4000;server_campfires_update(&server);assert(fire.on);
 std::puts("PASS actual campfires: authority/reach/alive, usable matches once, game-time fuel, late join, malformed packets, pending spawn and session reset");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "campfire.cpp"
    exe = Path(tmp) / ("campfire.exe" if os.name == "nt" else "campfire")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/wd4100", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
