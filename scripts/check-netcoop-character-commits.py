"""Actual bounded background save admission and Windows commit I/O faults."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
characters = (root/"src/xrGame/netcoop_characters.inc").read_text(encoding="utf-8")
a=characters.index('struct CharacterCommit {')
b=characters.index('static bool character_commit_file(',a)
queue=characters[a:b]
a=b;b=characters.index('static void character_commit_worker(',a)
commit_file=characters[a:b]
worker=characters[b:characters.index('// A synchronous save',b)]
assert 'character_commit_take(commit)' in worker and 'character_commit_finish()' in worker
save=characters[characters.index('static bool character_save(Character&'):characters.index('static Character* character_load(')]
assert save.index('character_commits_flush()') < save.index('character_temp_path(') < save.index('fopen(temp, "wb")')
assert save.index('_ftelli64(f)') < save.index('character_commit_enqueue(commit)') < save.index('character.last_save = real_time_ms()')
assert save.index('character_sync_commit(f, temp, path)') < save.rindex('character.last_save = real_time_ms()')

source=r'''
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <deque>
#include <string>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <iostream>
#include <fstream>
#include <sstream>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
using LONG=int32_t;
#endif
using u32=unsigned int;using u64=uint64_t;using LPCSTR=const char*;
using xr_string=std::string;using string_path=char[260];
template<class T>using xr_deque=std::deque<T>;
struct xrCriticalSection{std::mutex lock;void Enter(){lock.lock();}void Leave(){lock.unlock();}};
std::vector<std::string>deleted;
void record_delete(LPCSTR path){deleted.push_back(path);
#ifdef _WIN32
 ::DeleteFileA(path);
#endif
}
u32 fixture_pid=123;
u32 process_id(){return fixture_pid;}
#ifdef _WIN32
bool fail_flush=false,fail_rename=false;
int checked_commit(int fd){return fail_flush?-1:_commit(fd);}
BOOL checked_move(LPCSTR from,LPCSTR to,DWORD flags){return fail_rename?FALSE:MoveFileExA(from,to,flags);}
#define _commit checked_commit
#define MoveFileExA checked_move
#else
LONG InterlockedExchange(volatile LONG* target,LONG value){const auto old=*target;*target=value;return old;}
#endif
#define DeleteFileA record_delete
#define GetCurrentProcessId process_id
'''+queue+(commit_file if os.name=="nt" else "")+r'''
CharacterCommit entry(const std::string& path,const std::string& temp,u64 bytes){CharacterCommit result;result.path=path;result.temp=temp;result.bytes=bytes;return result;}
void reset(){assert(!s_commit_busy);s_commits.clear();s_commit_bytes=s_commit_active_bytes=0;deleted.clear();}
void drain(){CharacterCommit work;while(character_commit_take(work))character_commit_finish();}
#ifdef _WIN32
std::string read_file(){std::ifstream file("character.bin",std::ios::binary);std::ostringstream out;out<<file.rdbuf();return out.str();}
void io_faults(){
 std::ofstream("character.bin")<<"previous durable snapshot";
 std::ofstream("candidate.tmp")<<"new complete snapshot";
 fail_flush=true;assert(!character_commit_file("candidate.tmp","character.bin"));fail_flush=false;
 assert(read_file()=="previous durable snapshot");
 fail_rename=true;assert(!character_commit_file("candidate.tmp","character.bin"));fail_rename=false;
 assert(read_file()=="previous durable snapshot");
 assert(character_commit_file("candidate.tmp","character.bin"));assert(read_file()=="new complete snapshot");
 // Execute the actual synchronous completion path, including failed temporary
 // file cleanup, while the prior durable snapshot stays intact.
 auto candidate=[](){FILE* file=fopen("sync.tmp","wb");assert(file);assert(fwrite("next",1,4,file)==4);return file;};
 fail_flush=true;assert(!character_sync_commit(candidate(),"sync.tmp","character.bin"));fail_flush=false;
 assert(read_file()=="new complete snapshot" && GetFileAttributesA("sync.tmp")==INVALID_FILE_ATTRIBUTES);
 fail_rename=true;assert(!character_sync_commit(candidate(),"sync.tmp","character.bin"));fail_rename=false;
 assert(read_file()=="new complete snapshot" && GetFileAttributesA("sync.tmp")==INVALID_FILE_ATTRIBUTES);
 assert(character_sync_commit(candidate(),"sync.tmp","character.bin"));
 assert(read_file()=="next" && GetFileAttributesA("sync.tmp")==INVALID_FILE_ATTRIBUTES);
 // A write error must close and remove the failed candidate too.
 std::ofstream("readonly.tmp")<<"read only candidate";FILE* readonly=fopen("readonly.tmp","rb");assert(readonly);
 assert(fwrite("bad",1,3,readonly)!=3 && ferror(readonly));
 assert(!character_sync_commit(readonly,"readonly.tmp","character.bin"));
 assert(read_file()=="next" && GetFileAttributesA("readonly.tmp")==INVALID_FILE_ATTRIBUTES);
}
#endif
int main(){
 (void)s_commit_worker;
 reset();assert(character_commit_enqueue(entry("a","a1",100)));
 assert(character_commit_enqueue(entry("a","a2",200)));
 assert(s_commits.size()==1 && s_commit_bytes==200 && deleted==std::vector<std::string>{"a1"});
 assert(!character_commit_enqueue(entry("a","a2",100)));assert(s_commit_bytes==200);
 CharacterCommit active,second;
 assert(character_commit_take(active));assert(active.temp=="a2" && s_commit_bytes==200 && s_commit_busy);
 assert(!character_commit_take(second));
 assert(character_commit_enqueue(entry("a","a3",300)));
 assert(s_commits.size()==1 && s_commit_bytes==500 && deleted.size()==1);
 character_commit_finish();assert(s_commit_bytes==300);
 assert(character_commit_take(second));assert(second.temp=="a3");character_commit_finish();
 character_commit_finish();assert(s_commit_bytes==0 && s_commits.empty() && !s_commit_busy);
 reset();assert(character_commit_enqueue(entry("a","a1",character_commit_byte_limit)));
 assert(!character_commit_enqueue(entry("b","b1",1)));
 assert(character_commit_take(active));assert(!character_commit_enqueue(entry("b","b1",1)));
 character_commit_finish();assert(character_commit_enqueue(entry("b","b1",1)));drain();
 reset();assert(character_commit_enqueue(entry("a","a1",character_commit_byte_limit-1)));
 assert(character_commit_enqueue(entry("b","b1",1)));
 assert(!character_commit_enqueue(entry("b","b2",2)));assert(s_commit_bytes==character_commit_byte_limit && deleted.empty());
 assert(character_commit_enqueue(entry("a","a2",1)));assert(s_commit_bytes==2);drain();
 assert(!character_commit_enqueue(entry("bad","oversize",character_commit_byte_limit+1)));
 assert(!character_commit_enqueue(entry("bad","empty",0)));
 reset();for(u32 i=0;i<character_commit_count_limit;++i)assert(character_commit_enqueue(entry(std::to_string(i),"old"+std::to_string(i),1)));
 assert(!character_commit_enqueue(entry("overflow","new",1)));
 assert(character_commit_enqueue(entry("0","replacement",2)));assert(s_commits.size()==character_commit_count_limit);
 drain();assert(s_commit_bytes==0);
 string_path first_path,second_path,sync_path,foreign_path;
 assert(character_temp_path("character.bin",true,first_path));assert(character_temp_path("character.bin",true,second_path));
 assert(character_temp_path("character.bin",false,sync_path));fixture_pid=124;
 assert(character_temp_path("character.bin",true,foreign_path));
 assert(std::strcmp(first_path,second_path) && std::strcmp(first_path,sync_path) && std::strcmp(first_path,foreign_path));
 assert(std::string(first_path).find(".123.")!=std::string::npos && std::string(foreign_path).find(".124.")!=std::string::npos);
 assert(!character_temp_path(std::string(260,'x').c_str(),true,first_path));
 // One real producer and consumer exercise replacement/take/finish under
 // contention. Each path must finish with its latest complete snapshot.
 reset();std::atomic<bool> done{false};std::map<std::string,u32> latest;
 std::thread producer([&](){for(u32 i=1;i<=4000;++i)assert(character_commit_enqueue(entry(std::to_string(i%4),std::to_string(i),100)));done=true;});
 std::thread consumer([&](){for(;;){
  CharacterCommit work;
  if(!character_commit_take(work)){
   if(!done){std::this_thread::yield();continue;}
   if(!character_commit_take(work))break; // Recheck after producer's release barrier.
  }
  latest[work.path]=u32(std::stoul(work.temp));character_commit_finish();
 }});
 producer.join();consumer.join();assert(latest.size()==4 && s_commit_bytes==0 && !s_commit_busy);
 for(u32 i=0;i<4;++i)assert(latest[std::to_string(i)]==4000-((4-i)%4));
#ifdef _WIN32
 io_faults();
#endif
 std::cout<<"PASS actual background commits: bounded bytes/count, complete pending replacement, in-flight accounting, no stale takeover, process-unique names, threaded latest snapshots and Windows flush/rename faults\n";
}
'''
with TemporaryDirectory(prefix="character-commits-") as tmp:
    cpp=Path(tmp)/"check.cpp";exe=Path(tmp)/("check.exe" if os.name=="nt" else "check")
    cpp.write_text(source,encoding="utf-8")
    if os.name=="nt":
        command=["cl","/nologo","/std:c++17","/EHsc","/W4","/WX","/O2",str(cpp),"/Fe:"+str(exe),"/Fo:"+str(Path(tmp)/"check.obj")]
    else:
        command=["g++","-std=c++17","-Wall","-Wextra","-Werror","-O2","-pthread",str(cpp),"-o",str(exe)]
    subprocess.run(command,check=True,cwd=tmp)
    subprocess.run([str(exe)],check=True,cwd=tmp,timeout=30)
