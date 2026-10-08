"""Exercise actual failed-start and input-release methods with engine API doubles."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/Level_start.cpp").read_text()
begin = text.index("bool CLevel::net_start6()")
method = text[begin:text.index("void CLevel::InitializeClientGame(", begin)]
text = (root / "src/xrEngine/Xr_input.cpp").read_text()
begin = text.index("void CInput::iRelease(")
release = text[begin:text.index("void CInput::OnAppActivate(", begin)]
assert method.count("IR_Release();") == 1
control = method.replace("CLevel::net_start6()", "CLevel::net_start6_baseline()")
control = control.replace("\t\tIR_Release();", "")
source = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using u32=unsigned;using LPCSTR=const char*;using string256=char[256];
template<class T>using xr_vector=std::vector<T>;
struct Receiver {int activated=0,deactivated=0;virtual ~Receiver()=default;
 virtual void IR_OnActivate(){++activated;}virtual void IR_OnDeactivate(){++deactivated;}};
struct CInput {xr_vector<Receiver*> cbStack;void iRelease(Receiver*);
 bool contains(Receiver* r)const{return std::find(cbStack.begin(),cbStack.end(),r)!=cbStack.end();}};
CInput input;Receiver dummy,overlay;
struct Shared:std::string {using std::string::string;explicit operator bool()const{return !empty();}};
struct CStringTable {Shared translate(LPCSTR)const{return Shared("translated");}};
// Concatenation contents do not affect the input-lifetime oracle.
template<class...T>LPCSTR join(T...){return "fixture map description";}
#define STRCONCAT(name,...) name=join(__VA_ARGS__)
template<class...T>void strconcat(unsigned size,char* out,T...){assert(size>0);out[0]=0;}
template<class...T>void Msg(LPCSTR,T...){}
constexpr bool FALSE=false;
bool psNET_direct_connect=false,g_dedicated_server=false;
namespace xrServer {enum {ErrConnect=7};}
struct CoreType {const char* Params="";} Core;
struct ConsoleType {int calls=0;void Execute(LPCSTR){++calls;}} console;
ConsoleType* Console=&console;
struct Application {int ended=0;void LoadEnd(){++ended;}} app;
Application* pApp=&app;
struct Menu {int switched=0,downloaded=0;void SwitchToMultiplayerMenu(){++switched;}
 void Show_DownloadMPMap(LPCSTR,LPCSTR){++downloaded;}} menu;
Menu* MainMenu(){return &menu;}
struct UI {int connected=0;void OnConnected(){++connected;}} ui;
UI* CurrentGameUI(){return &ui;}
struct CLevel:Receiver {
 struct Bullet {int cleared=0,loaded=0;void Clear(){++cleared;}void Load(){++loaded;}} bullet;
 Bullet& BulletManager(){return bullet;}
 struct Map {bool m_map_loaded=true,invalid=false;Shared m_name="cordon",m_map_download_url="url",m_map_version="1";
  bool IsInvalidClientChecksum()const{return invalid;}} map_data;
 bool net_start_result_total=false,m_bConnectResult=true,deleted=false;
 int m_connect_server_err=0,stopped=0,released=0;
 void IR_Release(){++released;input.iRelease(this);}
 void net_Stop(){++stopped;IR_Release();}
 bool net_start6();bool net_start6_baseline();
};
CLevel* g_pGameLevel=nullptr;
int deletions=0,unsafe_deletions=0;
void delete_instance(CLevel*& level){assert(level);++deletions;if(input.contains(level))++unsafe_deletions;level->deleted=true;level=nullptr;}
#define DEL_INSTANCE(level) delete_instance(level)
''' + release + method + control + r'''
void reset(CLevel& level,bool captured,bool covered=false){
 input.cbStack={&dummy};if(captured)input.cbStack.push_back(&level);if(covered)input.cbStack.push_back(&overlay);
 dummy.activated=0;dummy.deactivated=0;overlay.activated=0;overlay.deactivated=0;
 g_pGameLevel=&level;deletions=0;unsafe_deletions=0;console={};menu={};ui={};app={};
 psNET_direct_connect=false;g_dedicated_server=false;
}
int main(){
 // Qualified pre-fix control: a loaded level rejected during admission remains captured at deletion.
 {CLevel level;reset(level,true);assert(level.net_start6_baseline());assert(unsafe_deletions==1 && input.contains(&level));}
 for(int branch=0;branch<4;++branch)for(bool captured:{false,true})for(bool covered:{false,true}){
  CLevel level;reset(level,captured,covered);
  if(branch==0)level.m_connect_server_err=xrServer::ErrConnect;
  if(branch==1)level.map_data.m_map_loaded=false;
  if(branch==2)level.map_data.invalid=true;
  assert(level.net_start6());
  assert(level.deleted && !g_pGameLevel && deletions==1 && unsafe_deletions==0);
  assert(!input.contains(&level));assert(input.cbStack.front()==&dummy);
  assert(input.cbStack.back()==(covered?&overlay:&dummy));
  assert(level.stopped==(branch==2?1:0));assert(level.released==(branch==2?2:1));
  assert(menu.switched==(branch<3?1:0));assert(menu.downloaded==((branch==1||branch==2)?1:0));
  assert(ui.connected==0 && app.ended==1 && level.bullet.cleared==1 && level.bullet.loaded==1);
  if(captured && !covered)assert(dummy.activated==1 && level.deactivated==1);
  else assert(dummy.activated==0 && overlay.activated==0);
 }
 {CLevel level;reset(level,false);g_dedicated_server=true;assert(level.net_start6());assert(!unsafe_deletions && !menu.switched);}
 {CLevel level;reset(level,true);psNET_direct_connect=true;level.m_connect_server_err=xrServer::ErrConnect;assert(level.net_start6());assert(!unsafe_deletions && !menu.switched);}
 // Successful admission keeps the level and input ownership and runs OnConnected.
 {CLevel level;reset(level,true);level.net_start_result_total=true;assert(level.net_start6());assert(!level.deleted && !level.released && input.contains(&level) && ui.connected==1);}
 std::cout<<"PASS: actual failed-start and iRelease; qualified stale-input control, 16 failure branches, covered/uncaptured receivers, checksum stop, dedicated/direct and unchanged successful admission\n";
}
'''
with TemporaryDirectory(prefix="failed-start-input-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True, cwd=tmp)
