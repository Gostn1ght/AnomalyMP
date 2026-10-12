"""CI-only actual joinable workers, interruptible shutdown and closed logger."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.name != 'nt':
    raise SystemExit('Windows native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
math = (root/'src/xrCore/_math.cpp').read_text(encoding='latin-1')
threads = math[math.index('struct THREAD_STARTUP'):math.index('//void spline1')]
device = (root/'src/xrEngine/device.cpp').read_text(encoding='latin-1')
workers = device[device.index('CTimer FreezeTimer;'):device.index('void CRenderDevice::on_idle()')]
workers += device[device.index('void mt_DiscordThread(void*)'):device.index('void CRenderDevice::Run()')]
assert device.index('stop_maintenance_workers();', device.index('void CRenderDevice::Run()')) < device.index('seqAppEnd.Process(rp_AppEnd);', device.index('void CRenderDevice::Run()'))
log = (root/'src/xrCore/log.cpp').read_text(encoding='latin-1')
flush = log[log.index('void FlushLog()'):log.index('void LogLock(')]
add = log[log.index('void AddOne(const char* split)'):log.index('void Log(const char* s)')]
init = log[log.index('void InitLog()'):log.index('void CreateLog(')]
close = log[log.index('void CloseLog(void)'):log.index('xr_string FormatString(')]
source = r'''
#define NOMINMAX
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <process.h>
#include <cassert>
#include <atomic>
#include <cstdio>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
using LPCSTR=const char*;using xr_string=std::string;using u32=unsigned;
using thread_t=void(void*);
std::atomic<unsigned> startup_allocations{0},cpu_initialized{0};
template<class T>T* xr_new(){++startup_allocations;return new T;}
template<class T>void xr_delete(T*& p){if(p){delete p;p=nullptr;--startup_allocations;}}
struct{void _initialize(bool){}}Debug;
void thread_name(const char*){}
void _initialize_cpu_thread(){++cpu_initialized;}
#define PROF_THREAD(name) ((void)(name))
#define PROF_EVENT(...) ((void)0)
#define START_PROFILE(name) ((void)(name))
#define STOP_PROFILE ((void)0)
''' + threads + r'''
bool pool_alive=true;
unsigned pool_reads=0,callbacks=0;
struct shared_str {
 std::string value;
 shared_str()=default;
 shared_str(const char* p):value(p){assert(pool_alive);++pool_reads;}
 const char* c_str()const{return value.c_str();}
 bool equal(const shared_str& rhs)const{return value==rhs.value;}
};
struct {std::recursive_mutex lock;void Enter(){lock.lock();}void Leave(){lock.unlock();}}logCS;
std::vector<xr_string> LogFile;
volatile LONG log_closed=0;
shared_str log_last_str;
int log_repeat_count=0;
size_t log_flushed_lines=0;
BOOL no_log=FALSE,logTimestamps=FALSE,LogExecCB=TRUE;
using LogCallback=void(*)(const char*);
void callback(const char*){++callbacks;}
LogCallback LogCB=callback;
const char* logFName="fixture.log";
enum Console_mark{plain};
bool is_console_mark(Console_mark){return false;}
std::string timeInHMSMMM(){return "fixture";}
struct IWriter{void w_string(const char*){assert(pool_alive);}};
struct {IWriter* w_open(const char*){assert(pool_alive);return new IWriter;}void w_close(IWriter* p){delete p;}}FS;
void FlushLog();
''' + flush + add + init + close + r'''
struct CTimer{float GetElapsed_sec()const{return 10;}};
std::vector<int> g_loading_events;
bool use_discord=false;
float discord_update_rate=60;
constexpr unsigned rsDiscord=1;
struct {bool test(unsigned)const{return true;}}psDeviceFlags2;
int application=1;
int* pApp=&application;
std::atomic<unsigned> rpc_calls{0},presence_calls{0};
struct Discord {void RunCallbacks(){assert(pApp);++rpc_calls;Sleep(20);}}discord;
Discord* discord_core=&discord;
void updateDiscordPresence(){assert(pApp);++presence_calls;}
''' + workers + r'''
int main(){
 InitLog();AddOne("");assert(LogFile.size()==1);CloseLog();InitLog();no_log=FALSE;LogCB=callback;callbacks=0;
 AddOne("a");AddOne("a");assert(LogFile.size()==1 && LogFile[0]=="a [2]");
 AddOne("b");FlushLog();assert(callbacks==3 && log_flushed_lines==2);
 for(bool enabled:{false,true}){
  use_discord=enabled;
  maintenance_stop=CreateEvent(nullptr,TRUE,FALSE,nullptr);assert(maintenance_stop);
  freeze_worker=thread_spawn_joinable(mt_FreezeThread,"Freeze detecting thread",0,nullptr);
  discord_worker=thread_spawn_joinable(mt_DiscordThread,"X-RAY Discord thread",0,nullptr);
  assert(freeze_worker && discord_worker);
  Sleep(50);
  const auto before=GetTickCount64();stop_maintenance_workers();
  assert(GetTickCount64()-before<1000 && !maintenance_stop && !freeze_worker && !discord_worker);
  assert(startup_allocations.load()==0);
 }
 assert(cpu_initialized.load()==4 && rpc_calls.load()>0 && presence_calls.load()>0);
 // Closing waits for an in-progress writer before releasing its string pool.
 std::atomic<bool> started{false};
 std::thread late([&]{started=true;for(unsigned i=0;i<1000;++i)AddOne("worker");});
 while(!started.load())std::this_thread::yield();
 CloseLog();late.join();assert(LogFile.empty() && log_last_str.value.empty() && !LogCB);
 const unsigned reads=pool_reads,old_callbacks=callbacks;
 pool_alive=false;pApp=nullptr;
 AddOne("pApp destroyed");FlushLog();FlushLogAppend();CloseLog();
 assert(pool_reads==reads && callbacks==old_callbacks && LogFile.empty());
 // A subsequent Core init has an empty repeat cache and a new live pool.
 pool_alive=true;InitLog();no_log=FALSE;LogCB=callback;
 AddOne("a");assert(LogFile.size()==1 && LogFile[0]=="a");CloseLog();
 std::cout<<"PASS actual workers/logger: joinable CPU setup, immediate stop through long sleeps, callbacks finish before teardown, late logging never touches destroyed string pool, safe reinit\n";
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'background.cpp';exe=Path(tmp)/'background.exe'
    cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=tmp,check=True)
    subprocess.run([str(exe)],cwd=tmp,check=True,timeout=20)
