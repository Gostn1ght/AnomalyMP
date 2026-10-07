"""Compile actual engine/IX-Ray schedulers with deterministic host services, CI only."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]

host = r'''
#pragma once
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <functional>
#include <iostream>
#include <memory>
#include <new>
#include <random>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
using u32=std::uint32_t;using u64=std::uint64_t;using BOOL=int;using LPCSTR=const char*;
#define TRUE 1
#define FALSE 0
#define ENGINE_API
#define IC inline
#ifdef DEBUG
#define VERIFY(x) assert(x)
#define VERIFY2(x,...) assert(x)
#else
#define VERIFY(...) ((void)0)
#define VERIFY2(...) ((void)0)
#endif
#define R_ASSERT(x) assert(x)
#define PROF_EVENT(...)
#define DEBUG_INFO "fixture", 0, "fixture"
struct DebugService{void fatal(const char*,int,const char*,const char*,...){std::abort();}};
inline DebugService Debug;
using string1024=char[1024];
template<class T> using xr_vector=std::vector<T>;
template<class K,class V> using xr_unordered_map=std::unordered_map<K,V>;
struct shared_str {
 std::string value;shared_str()=default;shared_str(const char* s):value(s){}shared_str(std::string s):value(std::move(s)){}
 const char* c_str() const{return value.c_str();}const char* operator*()const{return c_str();}
};
template<class T> T _max(T a,T b){return std::max(a,b);}
template<class T> void clamp(T& v,T low,T high){v=std::max(low,std::min(v,high));}
template<class T> T clampr(T v,T low,T high){clamp(v,low,high);return v;}
inline int iFloor(float x){return int(std::floor(x));}inline int iCeil(float x){return int(std::ceil(x));}
inline void Msg(const char*,...){}
inline const char* make_string(const char*,...){return "fixture";}
struct CTimer{void Start(){}};
inline u64 fixture_cycles=0;
namespace CPU{inline u64 qpc_freq=1000;inline u64 QPC(){return fixture_cycles;}}
struct Counter{void Begin(){}void End(){}};
struct Stats{Counter Sheduler;float fShedulerLoad=0;};
struct DeviceState{u32 dwTimeGlobal=0,dwFrame=0,dwPrecacheFrame=0;Stats* Statistic;};
inline Stats fixture_stats;inline DeviceState Device{0,0,0,&fixture_stats};
#include "xrSheduler.h"
struct EngineState{CSheduler Sheduler;};extern EngineState Engine;
class CObject:public ISheduled{public:virtual shared_str cName()const{return "fixture";}};
template<class To,class From> To fast_dynamic_cast(From from){return dynamic_cast<To>(from);}
'''

cases = r'''
#include "stdafx.h"
#include "ixray_reference_scheduler.h"
#include "xrSchedulerRegistration.h"
#include <chrono>
EngineState Engine;
extern float psShedulerCurrent,psShedulerTarget;
extern float ixray_psShedulerCurrent,ixray_psShedulerTarget;
struct Event{u32 id,at,dt;bool operator==(const Event& b)const{return id==b.id&&at==b.at&&dt==b.dt;}};
std::vector<Event> trace;
struct Object final:ISheduled {
 u32 id,cost=0;bool needed=true;float scale=0;
 std::function<void(Object&)> update_hook,needed_hook,scale_hook;
 std::function<void(ISheduled*)> unregister;
 explicit Object(u32 value):id(value){}
 ~Object()override{if(unregister)unregister(this);}
 float shedule_Scale()override{float result=scale;auto fn=scale_hook;if(fn)fn(*this);return result;}
 bool shedule_Needed()override{bool result=needed;auto fn=needed_hook;if(fn)fn(*this);return result;}
 shared_str shedule_Name()const override{return shared_str("object-"+std::to_string(id));}
 void shedule_Update(u32 dt)override{
  ISheduled::shedule_Update(dt);trace.push_back(Event{id,Device.dwTimeGlobal,dt});fixture_cycles+=cost;
  auto fn=update_hook;if(fn)fn(*this);
 }
};
void reset(){Engine.Sheduler.Initialize();Device.dwTimeGlobal=0;Device.dwFrame=10;fixture_cycles=0;
 psShedulerCurrent=psShedulerTarget=ixray_psShedulerCurrent=ixray_psShedulerTarget=10.f;trace.clear();}
void tick(u32 delta=50){Device.dwTimeGlobal+=delta;++Device.dwFrame;Engine.Sheduler.Update();}
std::vector<u32> ids(){std::vector<u32> out;for(const auto& e:trace)out.push_back(e.id);return out;}
void clear(){Engine.Sheduler.Update();Engine.Sheduler.Destroy();trace.clear();}

template<class Scheduler> std::pair<std::vector<Event>,float> cadence(Scheduler& scheduler,float& budget){
 scheduler.Initialize();Device.dwTimeGlobal=0;Device.dwFrame=10;fixture_cycles=0;trace.clear();
 std::vector<std::unique_ptr<Object>> objects;
 for(u32 i=0;i<192;++i){objects.emplace_back(new Object(i));auto& o=*objects.back();
  o.shedule.t_min=20+(i%5)*10;o.shedule.t_max=100+(i%9)*50;o.scale=float(i%7)/6.f;o.cost=i%3;
  if(i%7==0)o.scale_hook=[](Object& self){self.shedule.t_max=1100+(Device.dwFrame%4)*500;};
  o.unregister=[&scheduler](ISheduled* p){scheduler.Unregister(p);};scheduler.Register(&o,i<64);}
 for(u32 frame=0;frame<500;++frame){
  Device.dwTimeGlobal+=(frame%23==0?1400:10+(frame%11)*7);++Device.dwFrame;
  objects[frame%64]->needed=(frame%13)!=0;
  if(frame%29==0){auto* o=objects[64+frame%128].get();scheduler.Unregister(o);scheduler.Register(o,FALSE);}
  scheduler.Update();
 }
 auto out=std::make_pair(trace,budget);objects.clear();scheduler.Update();scheduler.Destroy();return out;
}
void differential(){
 reset();IXRayReferenceScheduler reference;auto old=cadence(reference,ixray_psShedulerCurrent);
 Engine.Sheduler.Destroy();reset();auto current=cadence(Engine.Sheduler,psShedulerCurrent);
 assert(old.first==current.first);assert(old.second==current.second);
 std::cout<<"PASS IX-Ray differential: 64 realtime + 128 normal, 500 variable ticks, dt/order/budget/cadence identical ("<<current.first.size()<<" callbacks)\n";
}
void realtime_lifetime(){
 reset();Object* a=new Object(1);Object* b=new Object(2);Object* c=new Object(3);
 for(auto* o:{a,b,c}){o->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};Engine.Sheduler.Register(o,TRUE);}
 a->update_hook=[&](Object&){delete b;b=nullptr;delete a;a=nullptr;};tick();assert((ids()==std::vector<u32>{1,3}));
 trace.clear();tick();assert((ids()==std::vector<u32>{3}));delete c;clear();
 // Cancellation in shedule_Needed must not invoke a stale pointer.
 reset();a=new Object(4);a->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};
 a->needed_hook=[&](Object&){delete a;a=nullptr;};Engine.Sheduler.Register(a,TRUE);tick();assert(trace.empty());clear();
}
void normal_lifetime(){
 reset();auto* a=new Object(10);a->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};
 a->scale_hook=[&](Object&){delete a;a=nullptr;};Engine.Sheduler.Register(a);tick();assert(trace.empty());clear();
 reset();a=new Object(11);a->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};
 a->needed_hook=[&](Object&){delete a;a=nullptr;};Engine.Sheduler.Register(a);tick();assert(trace.empty());clear();
 reset();a=new Object(12);a->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};
 a->update_hook=[&](Object&){delete a;a=nullptr;};Engine.Sheduler.Register(a);tick();trace.clear();tick();assert(trace.empty());clear();
}
void reused_address(){
 // Old normal heap entry survives unregister; placement-new proves generations,
 // not merely a pointer set, prevent an early/duplicate callback.
 reset();alignas(Object) unsigned char space[sizeof(Object)];Object* old=new(space)Object(20);
 old->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};Engine.Sheduler.Register(old);tick();
 old->~Object();auto* fresh=new(space)Object(21);fresh->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};
 Engine.Sheduler.Register(fresh);trace.clear();tick(1);assert(trace.empty());tick(1);assert((ids()==std::vector<u32>{21}));
 fresh->~Object();clear();
 reset();Object* a=new Object(30);old=new(space)Object(31);fresh=nullptr;
 a->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};old->unregister=a->unregister;
 Engine.Sheduler.Register(a,TRUE);Engine.Sheduler.Register(old,TRUE);
 a->update_hook=[&](Object& self){self.update_hook={};old->~Object();fresh=new(space)Object(32);
  fresh->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};Engine.Sheduler.Register(fresh,TRUE);};
 tick();assert((ids()==std::vector<u32>{30}));trace.clear();tick();assert((ids()==std::vector<u32>{30,32}));
 delete a;fresh->~Object();clear();
}
void ordering(){
 reset();Object a(40),b(41),c(42);
 for(auto* o:{&a,&b,&c}){o->unregister=[](ISheduled* p){Engine.Sheduler.Unregister(p);};Engine.Sheduler.Register(o,TRUE);}
 a.update_hook=[&](Object& self){self.update_hook={};Engine.Sheduler.EnsureOrder(&a,&b);};
 tick();assert((ids()==std::vector<u32>{40,41,42}));trace.clear();tick();assert((ids()==std::vector<u32>{40,42,41}));
 for(auto* o:{&a,&b,&c}){Engine.Sheduler.Unregister(o);o->unregister={};}clear();
}
struct Request{BOOL OP,RT;void* Object;std::size_t index;};
std::vector<unsigned char> legacy_pairs(std::vector<Request> work){
 std::vector<unsigned char> out(work.size(),0);
 for(std::size_t i=0;i<work.size();++i)if(work[i].OP)
  for(std::size_t j=i+1;j<work.size();++j)if(!work[j].OP&&work[j].Object==work[i].Object){
   out[work[i].index]=out[work[j].index]=1;work.erase(work.begin()+j);break;}
 return out;
}
void pairing(){
 std::mt19937 random(71);int objects[8]={};
 for(u32 run=0;run<10000;++run){std::vector<Request> records;std::size_t count=random()%80;
  for(std::size_t i=0;i<count;++i)records.push_back(Request{BOOL(random()%2),BOOL(random()%2),&objects[random()%8],i});
  assert(xr_scheduler::registration_pairs(records)==legacy_pairs(records));}
 std::vector<Request> large;large.reserve(100000);std::vector<int> population(50000);
 for(std::size_t i=0;i<population.size();++i)large.push_back(Request{TRUE,FALSE,&population[i],i});
 for(std::size_t i=0;i<population.size();++i)large.push_back(Request{FALSE,FALSE,&population[i],population.size()+i});
 auto skipped=xr_scheduler::registration_pairs(large);assert(skipped.size()==100000);
 assert(std::all_of(skipped.begin(),skipped.end(),[](unsigned char x){return x==1;}));
 std::cout<<"PASS registration: 10000 differential batches + 50000 cancelled objects, earliest-pair semantics preserved\n";
}
int main(){pairing();differential();realtime_lifetime();normal_lifetime();reused_address();ordering();
 std::cout<<"PASS actual scheduler: self/other destruction, needed/scale cancellation, address reuse, stable realtime order; no cadence reduction\n";}
'''

with TemporaryDirectory(prefix="actual-scheduler-") as tmp:
    folder = Path(tmp)
    (folder/"stdafx.h").write_text(host, encoding="utf-8")
    (folder/"xr_object.h").write_text('#include "stdafx.h"\n', encoding="utf-8")
    for name in ("xrSheduler.cpp", "xrSheduler.h", "ISheduled.cpp", "ISheduled.h", "xrSchedulerRegistration.h"):
        (folder/name).write_text((root/"src/xrEngine"/name).read_text(encoding="utf-8"), encoding="utf-8")
    reference = root/"scripts/fixtures/ixray-scheduler"
    old_header = (reference/"xrSheduler.h").read_text(encoding="utf-8").replace("CSheduler", "IXRayReferenceScheduler").replace("XRSHEDULER_H_INCLUDED", "IXRAY_REFERENCE_SHEDULER_H")
    old_cpp = (reference/"xrSheduler.cpp").read_text(encoding="utf-8").replace('"xrSheduler.h"', '"ixray_reference_scheduler.h"').replace("CSheduler", "IXRayReferenceScheduler")
    old_cpp = old_cpp.replace("1000i64", "1000LL")  # same integer constant, GCC spelling
    for symbol in ("psShedulerCurrent", "psShedulerTarget", "psShedulerReaction", "g_bSheduleInProgress"):
        old_cpp = old_cpp.replace(symbol, "ixray_"+symbol)
    (folder/"ixray_reference_scheduler.h").write_text(old_header, encoding="utf-8")
    (folder/"ixray_reference_scheduler.cpp").write_text(old_cpp, encoding="utf-8")
    (folder/"cases.cpp").write_text(cases, encoding="utf-8")
    sources = [str(folder/name) for name in ("cases.cpp", "xrSheduler.cpp", "ISheduled.cpp", "ixray_reference_scheduler.cpp")]
    for debug in (False, True):
        exe = folder/("debug" if debug else "release")
        if os.name == "nt":
            exe = exe.with_suffix(".exe")
            command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/O2", *(["/DDEBUG"] if debug else []), *sources, "/Fe:"+str(exe)]
        else:
            command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-variable",
                       "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", *(["-DDEBUG"] if debug else []), *sources, "-o", str(exe)]
        subprocess.run(command, check=True, cwd=folder)
        subprocess.run([str(exe)], check=True, cwd=folder, timeout=120)
