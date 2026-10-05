"""Exercise actual ALife time-manager methods and local durable authority in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
game = root / "src/xrGame"
header = (game / "alife_time_manager.h").read_text()
implementation = (game / "alife_time_manager.cpp").read_text()
source = r'''
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#include "netcoop_alife_clock.h"
#include <cassert>
#include <cstring>
#include <fstream>
#include <iostream>
#include <thread>
#include <vector>
#include <memory>
#include <atomic>
#include <limits>
using u32=std::uint32_t;using u64=std::uint64_t;using LPCSTR=const char*;
namespace ALife {using _TIME_ID=u64;}
#define IC inline
#define GAME_TIME_CHUNK_DATA 5
#define CHECK_OR_EXIT(condition,message) do{if(!(condition))throw std::runtime_error(message);}while(false)
struct {u32 dwTimeGlobal=100;} Device;
void Msg(const char*,...) {}
struct Settings {
 const char* r_string(const char*,const char* key){return std::strcmp(key,"start_time")==0?"12:00:00":"01.01.2012";}
 float r_float(const char*,const char*){return 10;}
} settings;
Settings* pSettings=&settings;
u64 generate_time(u32,u32,u32,u32,u32,u32){return 63461016000000ULL;}
struct IWriter {
 std::vector<unsigned char> bytes;
 void open_chunk(u32) {bytes.clear();}void close_chunk() {}
 void w(const void* value,std::size_t size) {
  const auto* data=static_cast<const unsigned char*>(value);bytes.insert(bytes.end(),data,data+size);
 }
 void w_float(float value){w(&value,sizeof(value));}
 void w_u32(u32 value){w(&value,sizeof(value));}void w_u64(u64 value){w(&value,sizeof(value));}
};
struct IReader {
 std::vector<unsigned char> bytes;std::size_t pos=0;
 explicit IReader(const IWriter& writer):bytes(writer.bytes) {}
 u32 find_chunk(u32){pos=0;return static_cast<u32>(bytes.size());}
 void r(void* value,std::size_t size){if(pos+size>bytes.size())throw std::runtime_error("short read");std::memcpy(value,bytes.data()+pos,size);pos+=size;}
 float r_float(){float v;r(&v,sizeof(v));return v;}
 u32 r_u32(){u32 v;r(&v,sizeof(v));return v;}u64 r_u64(){u64 v;r(&v,sizeof(v));return v;}
};
'''
# Execute production methods with only engine I/O/config/device boundaries stubbed.
source += header[header.index("class CALifeTimeManager"):header.index('#include "alife_time_manager_inline.h"')]
source += (game / "alife_time_manager_inline.h").read_text().replace("#pragma once", "")
source += implementation[implementation.index("CALifeTimeManager::CALifeTimeManager"):]
source += r'''
template<class F>void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
using namespace netcoop_world;
int main(int argc,char** argv) {
 // Separate-process contention tests the OS lock, not only an in-process mutex.
 if(argc>1){WorldAuthorityStore competing;rejects([&]{competing.open(argv[1],"zone");});return 0;}
 assert(world_option("-netcoop -netcoop_world=zone\t-start") == "zone");
 assert(world_option("-netcoop").empty());
 rejects([]{world_option("-netcoop_world=../escape");});
 rejects([]{world_option("x-netcoop_world=zone");});
 rejects([]{world_option("-netcoop_world=one -netcoop_world=two");});
 CALifeTimeManager legacy("alife");assert(!legacy.has_world_clock());
 Device.dwTimeGlobal=200;assert(legacy.game_time()==63461016001000ULL);
 IWriter old_save;legacy.save(old_save);assert(old_save.bytes.size()==16);
 legacy.change_game_time(1000);assert(legacy.game_time()==63461016002000ULL);
 auto& owner=local_world_authority();owner.open(".","zone");
 auto first=owner.identity();assert(first.epoch==1 && first.world_id);
 WorldAuthorityStore second;rejects([&]{second.open(".","zone");});
 std::cout<<"AUTHORITY_READY"<<std::endl;
 // Parent runs a second process during this barrier, then closes our stdin.
 std::string signal;std::getline(std::cin,signal);
 CALifeTimeManager clock("alife");assert(clock.has_world_clock());
 IReader old(old_save);clock.load(old); // one-time legacy migration
 const auto before=clock.game_time();
 Device.dwTimeGlobal=UINT32_MAX; // engine timer wrap/reset does not drive this clock
 assert(clock.game_time()>=before && clock.game_time()-before<100000);
 clock.set_time_factor(2);assert(clock.time_factor()==2);
 clock.set_time_factor(0);assert(clock.time_factor()==2); // no calendar-only pause
 clock.set_time_factor(-1);assert(clock.time_factor()==2);
 clock.set_time_factor(std::numeric_limits<float>::quiet_NaN());assert(clock.time_factor()==2);
 clock.change_game_time(86400000);assert(clock.game_time()-before<100000); // no player sleep jump
 std::atomic<bool> failed{false};
 auto read=[&]{try{u64 previous=0;for(int i=0;i<10000;++i){auto t=clock.game_time();if(t<previous)failed=true;previous=t;}}catch(...){failed=true;}};
 std::thread a(read),b(read);for(int i=0;i<100;++i)clock.set_time_factor(i%2?2.f:10.f);
 a.join();b.join();assert(!failed);
 IWriter saved;clock.save(saved);assert(saved.bytes.size()==64);
 u64 saved_time=0;std::memcpy(&saved_time,saved.bytes.data(),sizeof(saved_time));
 owner.close();owner.open(".","zone");auto restarted=owner.identity();
 assert(restarted.world_id==first.world_id && restarted.seed==first.seed && restarted.epoch==2);
 CALifeTimeManager restored("alife");IReader snapshot(saved);restored.load(snapshot);
 assert(restored.game_time()>=saved_time && restored.game_time()-saved_time<100000);
 IWriter saved_again;restored.save(saved_again);
 IReader same_epoch(saved_again);rejects([&]{restored.load(same_epoch);});
 auto changed=saved;u64 wrong=first.world_id^1;
 std::memcpy(changed.bytes.data()+24,&wrong,sizeof(wrong));
 IReader foreign(changed);rejects([&]{restored.load(foreign);});
 changed=saved;changed.bytes.resize(63);IReader truncated(changed);rejects([&]{restored.load(truncated);});
 owner.close();
 // Failure after durable epoch reservation burns that epoch, never reuses it.
 owner.open(".","zone");assert(owner.identity().epoch==3);owner.close();
 owner.open(".","zone");assert(owner.identity().epoch==4);owner.close();
 owner.open(".","zone");owner.complete_bootstrap();assert(owner.ready());
 rejects([&]{restored.init("alife");});
 IReader rollback(saved);rejects([&]{restored.load(rollback);});
 owner.close();assert(!owner.ready());
 std::ofstream("native-snapshot",std::ios::binary)<<"complete";
 require_snapshot_size("native-snapshot",8);
 rejects([]{require_snapshot_size("native-snapshot",9);});
 rejects([]{require_snapshot_size("missing-native-snapshot",8);});
 std::fstream record("zone.authority",std::ios::in|std::ios::out|std::ios::binary);
 record.seekg(10);const char byte=static_cast<char>(record.get());
 record.seekp(10);record.put(static_cast<char>(static_cast<unsigned char>(byte)^0xff));record.close();
 rejects([&]{owner.open(".","zone");});assert(!owner.active());
 std::cout<<"PASS: actual ALife calendar save/load, legacy adoption, timer wrap independence, time-scale continuity, concurrent reads, restart/fence, corrupt/foreign/truncated state and exclusive process ownership\n";
}
'''
with TemporaryDirectory(prefix="alife-clock-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   "/I"+str(game), str(cpp), "/Fe:"+str(exe), "/Fo:"+str(Path(tmp)/"check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread", "-O2",
                   "-I"+str(game), str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    process = subprocess.Popen([str(exe)], cwd=tmp, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        ready = process.stdout.readline().strip()
        if ready != "AUTHORITY_READY":
            raise RuntimeError(f"Clock fixture failed before authority barrier: {ready}")
        subprocess.run([str(exe), tmp], check=True, cwd=tmp, timeout=20)
        output, _ = process.communicate("continue\n", timeout=30)
        print(output, end="")
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, [str(exe)])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
