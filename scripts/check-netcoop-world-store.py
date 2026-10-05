"""Exercise actual W1 pointer/slot functions with injected engine-save faults."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
store = (root/"src/xrGame/netcoop_world_store.inc").read_text()
source = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <fstream>
#include <stdexcept>
#include <iostream>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#define MOVEFILE_REPLACE_EXISTING 1
#define MOVEFILE_WRITE_THROUGH 2
int _commit(int fd) { return fsync(fd); }
int _fileno(FILE* f) { return fileno(f); }
#endif
bool fail_pointer=false;
bool checked_move(const char* from,const char* to,unsigned long flags) {
 if(fail_pointer) return false;
#ifdef _WIN32
 return MoveFileExA(from,to,flags)!=0;
#else
 (void)flags; return std::rename(from,to)==0;
#endif
}
#define MoveFileExA checked_move
using u32=unsigned int; using LPCSTR=const char*;using LPSTR=char*;
using string64=char[64];using string128=char[128];using string_path=char[260];
const char* SAVE_EXTENSION=".sav";
template <size_t N,class... Args> void xr_sprintf(char (&s)[N],const char* f,Args... args) {
 std::snprintf(s,N,f,args...);
}
size_t xr_strlen(const char* s) { return std::strlen(s); }
int xr_strcmp(const char* a,const char* b) { return std::strcmp(a,b); }
void xr_strcpy(char* out,u32 n,const char* in) { std::snprintf(out,n,"%s",in); }
void Msg(const char*,...) {}
bool enabled() {return true;} bool pure_client() {return false;}
struct {const char* Params="-netcoop -netcoop_world=zone";} Core;
struct Files {
 void update_path(char* out,const char*,const char* file) {std::snprintf(out,260,"%s",file);}
 bool exist(const char*,const char* file) {return bool(std::ifstream(file));}
} FS;
bool fail_save=false;int revision=0;std::string last_slot;
struct CALifeSimulator {
 void save(const char* name,bool) {
  last_slot=name;
  std::ofstream(name+std::string(".sav")) << (fail_save ? "partial" : std::to_string(revision));
  if(fail_save) throw std::runtime_error("injected interrupted engine save");
 }
} simulator;
struct AI {const CALifeSimulator* get_alife() {return &simulator;}};
AI& ai() {static AI a;return a;}
struct EngineLevel {void ClientSend() {} void ClientSave() {}};
EngineLevel engine_level;
EngineLevel* g_pGameLevel=&engine_level;
EngineLevel& Level() {return *g_pGameLevel;}
u32 real_time_ms() {return 777;}
struct CTimer {void Start() {} u32 GetElapsed_ms() {return 1;}};
'''
source += store[store.index("static const u32 world_save_period_ms"):store.index("// CALifeSimulator constructor")]
source += store[store.index("bool world_store_choose_start"):store.index("// Living player Actors")]
source += store[store.index("bool world_store_save_now"):store.index("// Every server_update")]
source += r'''
std::string contents(const char* file) {std::string s;std::ifstream(file)>>s;return s;}
int main() {
 assert(world_save_period_ms==300000);
 revision=1; assert(world_store_save_now("first"));
 assert(contents("zone.current")=="zone_a" && contents("zone_a.sav")=="1");
 revision=2; assert(world_store_save_now("second"));
 assert(contents("zone.current")=="zone_b" && contents("zone_b.sav")=="2");
 // Restart selection reads the committed pointer, not a new counter at zero.
 string64 load,mode;
 assert(world_store_choose_start(load,64,mode,64));
 assert(std::string(load)=="zone_b" && std::string(mode)=="load");
 assert(s_world_loaded && s_world_cleanup_pending);
 fail_save=true;revision=3;assert(!world_store_save_now("interrupted"));
 assert(last_slot=="zone_a" && contents("zone.current")=="zone_b");
 assert(contents("zone_b.sav")=="2"); // last committed world survives
 fail_save=false;assert(world_store_save_now("retry"));
 assert(contents("zone.current")=="zone_a" && contents("zone_a.sav")=="3");
 revision=4;fail_pointer=true;assert(!world_store_save_now("pointer failure"));
 assert(contents("zone.current")=="zone_a" && contents("zone_a.sav")=="3");
 revision=5;fail_pointer=false;assert(world_store_save_now("retry pointer"));
 assert(last_slot=="zone_b" && contents("zone_b.sav")=="5");
 assert(contents("zone_a.sav")=="3");
 std::ofstream("zone.current")<<"foreign_a";
 assert(!world_store_read_pointer("zone",load));
 std::ofstream("zone.current")<<"../other_world";
 assert(!world_store_read_pointer("zone",load));
 std::ofstream("zone.current")<<"zone_b\n";
 assert(world_store_read_pointer("zone",load));
 Core.Params="-netcoop_world=../escape";assert(!world_store_name(load));
 Core.Params="-netcoop_world=abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnop";
 assert(!world_store_name(load));
 std::cout<<"PASS: actual W1 save slot/pointer code; restart, interrupted save, failed manifest replacement, retry, foreign/corrupt pointer\n";
}
'''
with TemporaryDirectory(prefix="world-store-") as tmp:
    cpp = Path(tmp)/"check.cpp"
    exe = Path(tmp)/("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:"+str(exe), "/Fo:"+str(Path(tmp)/"check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2",
                   str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True, cwd=tmp)
