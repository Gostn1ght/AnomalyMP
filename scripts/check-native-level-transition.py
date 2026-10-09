"""Actual changer invitation and live-added cluster route, compiled only in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
changer = (root/'src/xrGame/level_changer.cpp').read_text(encoding='latin-1')
enter = changer[changer.index('void CLevelChanger::feel_touch_new('):changer.index('bool CLevelChanger::get_reject_pos(')]
guard = changer[changer.index('void CLevelChanger::netcoop_update_arrival_guard()'):changer.index('void CLevelChanger::feel_touch_new(')]
assert 'netcoop_update_arrival_guard();' in changer[changer.index('void CLevelChanger::shedule_Update('):changer.index('#include "patrol_path.h"')]
invite = changer[changer.index('void CLevelChanger::update_actor_invitation('):changer.index('void CLevelChanger::save(')]
cluster = (root/'src/xrGame/netcoop_cluster.inc').read_text(encoding='latin-1')
admission=cluster[cluster.index('void server_on_change_level('):cluster.index('// The player goes through the changer')]
assert 'candidate->feel_touch_contact(actor)' in admission and 'Radius() + 10.f' not in admission
routes = cluster[cluster.index('static bool cluster_config_path('):cluster.index('// ---- server status')]
source = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cctype>
#include <cstdlib>
#include <string>
#include <vector>
#include <initializer_list>
using LPCSTR=const char*;using u32=unsigned;using string_path=char[512];using xr_string=std::string;
constexpr bool TRUE=true,FALSE=false;constexpr u32 INVALID_FILE_ATTRIBUTES=~0u;
bool physical=false,indexed=false,rescan_succeeds=true;unsigned rescans=0,ini_reads=0;
u32 GetFileAttributesA(LPCSTR){return physical?0:INVALID_FILE_ATTRIBUTES;}
struct Path{LPCSTR m_Path="appdata\\";} appdata;
struct FileSystem{
 void update_path(string_path& out,LPCSTR alias,LPCSTR file){assert(!std::strcmp(alias,"$app_data_root$"));std::snprintf(out,sizeof(out),"appdata\\%s",file);}
 const int* exist(LPCSTR){static int entry;return indexed?&entry:nullptr;}
 Path* get_path(LPCSTR alias){assert(!std::strcmp(alias,"$app_data_root$"));return &appdata;}
 void rescan_path(LPCSTR dir,bool recurse){assert(!std::strcmp(dir,appdata.m_Path)&&!recurse);++rescans;if(rescan_succeeds)indexed=physical;}
} FS;
std::string address="127.0.0.1:1487";
struct CInifile{
 CInifile(LPCSTR,bool,bool,bool){assert(indexed);++ini_reads;}
 bool line_exist(LPCSTR sec,LPCSTR key){return !std::strcmp(sec,"locations")&&!std::strcmp(key,"l02_garbage");}
 LPCSTR r_string(LPCSTR,LPCSTR){return address.c_str();}
};
template<class T>using xr_vector=std::vector<T>;
struct Fvector{float x=0,y=0,z=0;};
struct CObject{virtual ~CObject()=default;};
struct CActor:CObject{unsigned fixture_id=7;unsigned ID(){return fixture_id;}bool alive=true;bool g_Alive()const{return alive;}};
template<class T,class U>T smart_cast(U* o){return dynamic_cast<T>(o);}
CActor owner,remote;CActor* Actor(){return &owner;}
namespace netcoop{bool active=true,client=true;bool enabled(){return active;}bool pure_client(){return active&&client;}}
struct NET_Packet{unsigned writes=0;void w_begin(int){++writes;}void w(const void*,size_t){++writes;}void w_vec3(const Fvector&){++writes;}};
constexpr int M_CHANGE_LEVEL=42;int net_flags(bool){return 0;}
struct GameUI{virtual ~GameUI()=default;};
struct CUIGameSP:GameUI{
 unsigned calls=0;bool last_enabled=false;
 void ChangeLevel(unsigned,unsigned,const Fvector&,const Fvector&,const Fvector&,const Fvector&,bool,LPCSTR,bool enabled){++calls;last_enabled=enabled;}
} ui;
GameUI* CurrentGameUI(){return &ui;}
struct LevelState{unsigned sends=0;void Send(NET_Packet& p,int){assert(p.writes==5);++sends;}} fixture_level;
LevelState& Level(){return fixture_level;}
struct{float fTimeGlobal=10;}Device;
#define VERIFY(x) assert(x)
struct CLevelChanger{
 unsigned m_netcoop_actor_id=0xffff;bool m_netcoop_arrival_block=false,fixture_inside=false;
 bool m_bSilentMode=true,m_b_enabled=true;unsigned m_game_vertex_id=7,m_level_vertex_id=9;
 Fvector m_position,m_angles;LPCSTR m_invite_str="change_level";float m_entrance_time=0;
 xr_vector<CObject*> feel_touch;
 bool get_reject_pos(Fvector&,Fvector&){return false;}
 bool feel_touch_contact(CObject*){return fixture_inside;}
 void netcoop_update_arrival_guard();void feel_touch_new(CObject*);void update_actor_invitation();
 static CLevelChanger* s_netcoop_inviter;static void netcoop_declined();
};
'''+routes+guard+enter+invite+r'''
int main(){
 xr_string host;u32 port=0;
 assert(!cluster_location(nullptr,host,port)&&!cluster_location("",host,port));
 assert(!cluster_config_present()&&rescans==0&&ini_reads==0);
 physical=true;rescan_succeeds=false;
 assert(!cluster_location("l02_garbage",host,port)&&rescans==1&&ini_reads==0);
 rescan_succeeds=true;
 assert(cluster_location("l02_garbage",host,port)&&host=="127.0.0.1"&&port==1487&&rescans==2);
 for(unsigned i=0;i<100;++i)assert(cluster_config_present()&&cluster_location("l02_garbage",host,port));
 assert(rescans==2);
 assert(!cluster_location("unserved",host,port));
 for(const char* bad:{"127.0.0.1:0","127.0.0.1:65536","bad/host:1487","missing-port"}){
  address=bad;assert(!cluster_location("l02_garbage",host,port));
 }
 for(bool silent:{false,true}){
  CLevelChanger c;c.m_bSilentMode=silent;c.feel_touch={&owner,&remote};
  unsigned calls=ui.calls,sends=fixture_level.sends;
  netcoop::active=true;netcoop::client=true;
  c.feel_touch_new(&remote);assert(ui.calls==calls&&fixture_level.sends==sends);
  owner.alive=false;c.feel_touch_new(&owner);assert(ui.calls==calls);owner.alive=true;
  c.feel_touch_new(&owner);assert(ui.calls==calls+1&&fixture_level.sends==sends&&ui.last_enabled);
  c.update_actor_invitation();assert(ui.calls==calls+1);
  Device.fTimeGlobal+=6;c.update_actor_invitation();assert(ui.calls==calls+2&&fixture_level.sends==sends);
  netcoop::client=false;c.feel_touch_new(&owner);Device.fTimeGlobal+=6;c.update_actor_invitation();
  assert(ui.calls==calls+2&&fixture_level.sends==sends);
  netcoop::active=false;c.feel_touch_new(&owner);
  assert(ui.calls==calls+2+unsigned(!silent)&&fixture_level.sends==sends+unsigned(silent));
 }
 netcoop::active=true;netcoop::client=true;
 CLevelChanger arrival;arrival.feel_touch={&owner};arrival.fixture_inside=true;
 unsigned prior_calls=ui.calls;arrival.netcoop_update_arrival_guard();
 arrival.feel_touch_new(&owner);Device.fTimeGlobal+=6;arrival.update_actor_invitation();
 assert(arrival.m_netcoop_arrival_block&&ui.calls==prior_calls);
 arrival.fixture_inside=false;arrival.netcoop_update_arrival_guard();assert(!arrival.m_netcoop_arrival_block);
 arrival.fixture_inside=true;arrival.netcoop_update_arrival_guard();arrival.feel_touch_new(&owner);assert(ui.calls==prior_calls+1);
 owner.fixture_id=8;arrival.netcoop_update_arrival_guard();assert(arrival.m_netcoop_arrival_block);
 arrival.feel_touch_new(&owner);assert(ui.calls==prior_calls+1);
 // "No": no client-side reject move; the changer stays quiet until the player leaves its shape.
 netcoop::active=true;CLevelChanger declined;declined.feel_touch={&owner};declined.fixture_inside=true;owner.fixture_id=9;
 declined.netcoop_update_arrival_guard();declined.fixture_inside=false;declined.netcoop_update_arrival_guard();declined.fixture_inside=true;
 unsigned before=ui.calls;declined.feel_touch_new(&owner);assert(ui.calls==before+1&&CLevelChanger::s_netcoop_inviter==&declined);
 CLevelChanger::netcoop_declined();assert(CLevelChanger::s_netcoop_inviter==nullptr&&declined.m_netcoop_arrival_block);
 Device.fTimeGlobal+=6;declined.update_actor_invitation();declined.netcoop_update_arrival_guard();assert(ui.calls==before+1);
 declined.fixture_inside=false;declined.netcoop_update_arrival_guard();assert(!declined.m_netcoop_arrival_block);
 declined.fixture_inside=true;declined.feel_touch_new(&owner);assert(ui.calls==before+2);
 netcoop::active=false;arrival.feel_touch_new(&owner);assert(fixture_level.sends>0);
 std::puts("PASS actual changer: own alive MP client always confirms, repeats after 5s; No stays quiet until the shape is left; remote/server denied; SP silent retained. Actual cluster route: missing catalog entry rescanned once, malformed/unserved refused.");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'transition.cpp';exe=Path(tmp)/('transition.exe' if os.name=='nt' else 'transition')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True)
    subprocess.run([str(exe)],cwd=tmp,check=True)
