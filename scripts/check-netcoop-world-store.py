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
#define _CRT_SECURE_NO_WARNINGS
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <cstdint>
#define CHECK_OR_EXIT(condition, message) do { if(!(condition)) throw std::runtime_error(message); } while(false)
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#define MOVEFILE_REPLACE_EXISTING 1
#define MOVEFILE_WRITE_THROUGH 2
#define INVALID_FILE_ATTRIBUTES 0xffffffffUL
unsigned long GetFileAttributesA(const char* path) { return std::ifstream(path) ? 0UL : INVALID_FILE_ATTRIBUTES; }
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
using u32=unsigned int; using u64=std::uint64_t; using LPCSTR=const char*;using LPSTR=char*;
using string64=char[64];using string128=char[128];using string256=char[256];using string_path=char[260];
const char* SAVE_EXTENSION=".sav";
template <size_t N> void xr_sprintf(char (&s)[N],const char* f,...) {
 va_list args;va_start(args,f);
 int length=std::vsnprintf(s,N,f,args);va_end(args);
 if(length<0 || size_t(length)>=N) throw std::runtime_error("format buffer overflow");
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
 bool exist(const char* file) {return bool(std::ifstream(file));}
} FS;
bool fail_save=false,fail_script=false;int revision=0;std::string last_slot;
bool script_matches=true;
namespace luabind { template<class R>struct functor { R operator()(const char*) {return script_matches;} }; }
struct ScriptEngine {template<class T>bool functor(const char*,T&){return true;}};
struct CALifeSimulator {
 void save(const char* name,bool) {
  last_slot=name;
  if(!fail_script) std::ofstream(name+std::string(".scoc")) << (fail_save ? "partial" : std::to_string(revision));
  std::ofstream(name+std::string(".sav")) << (fail_save ? "partial" : std::to_string(revision));
  if(fail_save) throw std::runtime_error("injected interrupted engine save");
 }
} simulator;
struct AI {
 const CALifeSimulator* get_alife() {return &simulator;}
 ScriptEngine& script_engine() {static ScriptEngine engine;return engine;}
};
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
template<class F> void rejects(F f) {bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
int main() {
 assert(world_save_period_ms==300000);
 assert(world_save_retry_ms==15000);
 string64 load,mode;
 assert(!world_store_choose_start(load,64,mode,64)); // genuinely new world
 revision=1; assert(world_store_save_now("first"));
 assert(contents("zone.current")=="zone_a" && contents("zone_a.sav")=="1");
 revision=2; assert(world_store_save_now("second"));
 assert(contents("zone.current")=="zone_b" && contents("zone_b.sav")=="2");
 // Restart selection reads the committed pointer, not a new counter at zero.
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
 assert(contents("zone_a.scoc")=="3");
 fail_script=true;revision=6;assert(!world_store_save_now("script callback failed"));
 assert(contents("zone.current")=="zone_b" && contents("zone_b.scoc")=="5");
 assert(contents("zone_a.scoc").empty()); // stale sidecar cannot be reused
 fail_script=false;
 script_matches=false;assert(!world_store_save_now("partial script write"));
 assert(contents("zone.current")=="zone_b" && contents("zone_b.scoc")=="5");
 script_matches=true;
 // New manifests detect byte corruption, truncation and missing snapshots.
 WorldSnapshotDigest digest;
 assert(world_store_read_pointer("zone",load,&digest) && digest.recorded && digest.bytes==1);
 std::ofstream("zone_b.sav")<<"6"; // same size, different bytes
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::ofstream("zone_b.sav")<<"";
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::remove("zone_b.sav");
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::ofstream("zone_b.sav")<<"5";
 assert(world_store_choose_start(load,64,mode,64));
 std::ofstream("zone_b.scoc")<<"6";
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::remove("zone_b.scoc");
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::ofstream("zone_b.scoc")<<"5";
 assert(world_store_choose_start(load,64,mode,64));
 std::remove("zone.current");
 assert(!world_store_save_now("lost committed pointer"));
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::ofstream("zone.current")<<"foreign_a";
 assert(!world_store_read_pointer("zone",load));
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 assert(!world_store_save_now("corrupt pointer"));
 std::ofstream("zone.current")<<"../other_world";
 assert(!world_store_read_pointer("zone",load));
 std::ofstream("zone.current")<<"zone_b\nLZW2 1 123\ntrailing";
 assert(!world_store_read_pointer("zone",load));
 std::ofstream("zone.current")<<"zone_b\rgarbage";
 assert(!world_store_read_pointer("zone",load));
 std::ofstream("zone.current")<<"zone_b\n";
 assert(world_store_read_pointer("zone",load));
 std::remove("zone_b.scoc");
 rejects([&]{world_store_choose_start(load,64,mode,64);});
 std::ofstream("zone_b.scoc")<<"5";
 assert(world_store_choose_start(load,64,mode,64)); // explicit legacy migration
 assert(world_store_save_now("upgrade legacy"));
 assert(world_store_read_pointer("zone",load,&digest) && digest.recorded);
 Core.Params="-netcoop_world=../escape";assert(!world_store_name(load));
 Core.Params="-netcoop_world=abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnop";
 assert(!world_store_name(load));
 std::cout<<"PASS: actual W1 save code; restart, interrupted save, manifest failure, ALife/script checksums, silent script failure/stale sidecar, missing snapshot/pointer, legacy upgrade, fail-closed recovery\n";
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
