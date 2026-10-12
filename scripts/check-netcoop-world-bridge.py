"""Compile actual read-only bridge; Windows calls the real local HTTP service."""
from pathlib import Path
import os
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"backend"))
from lostzone import Store, World
from lostzone.http import Credentials, Dispatcher, Server
from lostzone.timelines import Timelines
import uuid

source = r'''
#define NOMINMAX
#include "netcoop_world_bridge.h"
#include "netcoop_world_bridge_worker.h"
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <iterator>
#include <thread>
using namespace netcoop_world;
template<class F> void rejects(F f) {
 bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);
}
int main(int argc,char** argv) {
 (void)argc;(void)argv;
 const std::string text=R"({"result":{"schema":1,"world_seed":18446744073709551615,"state_revision":2,"states":{},"clock":{"schema":1,"seed":18446744073709551615,"revision":2,"world_id":123,"authority_epoch":1,"sequence":1,"world_ms":1000,"time_scale":10}}})";
 auto state=parse_bridge_bootstrap(text);
 assert(state.clock.world_id==123 && state.world_seed==UINT64_MAX);
 rejects([&]{parse_bridge_bootstrap("{}");});
 rejects([&]{parse_bridge_bootstrap(std::string(65537,' '));});
 rejects([&]{bridge_json(std::string(65,'[')+std::string(65,']'),65536);});
 const std::string escaped=R"json({"text":"[\"{}]"})json";
 assert(bridge_json(escaped,100).is_object()); // escaped quotes/brackets
 auto body=BridgeJson::parse(text);
 body["result"]["clock"]["sequence"]=-1;rejects([&]{parse_bridge_bootstrap(body.dump());});
 body=BridgeJson::parse(text);body["result"]["clock"]["schema"]=2;
 rejects([&]{parse_bridge_bootstrap(body.dump());});
 body=BridgeJson::parse(text);body["result"]["clock"]["time_scale"]=true;
 rejects([&]{parse_bridge_bootstrap(body.dump());});
 body=BridgeJson::parse(text);body["result"]["clock"]["seed"]=7;
 rejects([&]{parse_bridge_bootstrap(body.dump());});
 body=BridgeJson::parse(text);body["result"]["clock"]["revision"]=1;
 rejects([&]{parse_bridge_bootstrap(body.dump());});
 // Actual backend envelopes, including persisted phase lag during catch-up.
 body=BridgeJson::parse(text);body["result"]["event_watermark"]=9;
 body["result"]["states"]["weather"]={{"version",1},{"state",{
  {"timeline_id",std::string(32,'a')},{"phase","SCHEDULED"},
  {"times",{{"TRANSITION",1000},{"SETTLED",2000}}},
  {"parameters",{{"source","clear"},{"target","rain"},{"seed",UINT64_MAX}}}}}};
 body["result"]["states"]["emission"]={{"version",1},{"state",{
  {"timeline_id",std::string(32,'b')},{"phase","SCHEDULED"},
  {"times",{{"WARNING",1100},{"ACTIVE",1200},{"PEAK",1400},{"ENDED",1800}}},
  {"parameters",{{"intensity",.8},{"seed",0}}}}}};
 auto global=parse_bridge_globals(body.dump());
 assert(global.world.clock.world_id==123 && global.event_watermark==9);
 assert(global.weather.source=="clear" && global.weather.target=="rain" && global.weather.seed==UINT64_MAX);
 assert(global.emission.seed==0 && global.emission.intensity==.8);
 assert(bridge_weather_phase(global.weather,999)==1 && bridge_weather_blend(global.weather,999)==0);
 assert(bridge_weather_phase(global.weather,1000)==2 && bridge_weather_blend(global.weather,1500)==.5);
 assert(bridge_weather_phase(global.weather,2000)==3 && bridge_weather_blend(global.weather,2001)==1);
 for(unsigned i=0;i<5;++i) {
  const double times[]={1099,1100,1200,1400,1800};
  assert(bridge_emission_phase(global.emission,times[i])==i+1);
 }
 auto empty=BridgeJson::parse(text);empty["result"]["event_watermark"]=0;
 auto absent=parse_bridge_globals(empty.dump());
 assert(!absent.weather.present && !absent.emission.present);
 assert(bridge_weather_phase(absent.weather,1500)==0 && bridge_emission_phase(absent.emission,1500)==0);
 rejects([&]{parse_bridge_globals(text);}); // Watermark is mandatory.
 auto broken=body;broken["result"]["event_watermark"]=-1;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["weather"]["version"]=0;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["weather"]["state"]["timeline_id"]="not-a-persistent-id";
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["weather"]["state"]["times"]["SETTLED"]=1000;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["emission"]["state"]["times"]["PEAK"]=true;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["emission"]["state"]["times"]["ENDED"]=max_world_ms+1;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["emission"]["state"]["parameters"]["intensity"]=0;
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["weather"]["state"]["parameters"]["source"]="secret\ntext";
 rejects([&]{parse_bridge_globals(broken.dump());});
 broken=body;broken["result"]["states"]["emission"]["state"]["phase"]="BOGUS";
 rejects([&]{parse_bridge_globals(broken.dump());});
 BridgeObserver global_observer(123,UINT64_MAX);
 assert(global_observer.receive(global,100,200)==SyncResult::applied);
 assert(global_observer.globals().weather.id==std::string(32,'a'));
 assert(bridge_weather_blend(global_observer.globals().weather,global_observer.estimate(200))==.5);
 auto changed=global;changed.world.clock.sequence=2;changed.weather.target="fog";
 assert(global_observer.receive(changed,200,300)==SyncResult::invalid); // Same version cannot change the schedule.
 changed=global;changed.world.clock.sequence=2;changed.weather.present=false;
 assert(global_observer.receive(changed,200,300)==SyncResult::invalid);
 changed=global;changed.world.clock.sequence=2;changed.weather.version=2;changed.weather.ended=3000;
 assert(global_observer.receive(changed,200,300)==SyncResult::invalid); // Same ID stays immutable across phase versions.
 changed=global;changed.world.clock.sequence=2;changed.event_watermark=8;
 assert(global_observer.receive(changed,200,300)==SyncResult::invalid);
 changed=global;changed.world.clock.sequence=2;changed.world.state_revision=1;
 assert(global_observer.receive(changed,200,300)==SyncResult::invalid);
 changed=global;changed.world.clock.sequence=2;changed.world.state_revision=3;
 changed.weather.version=2;changed.weather.id=std::string(32,'c');changed.weather.target="fog";
 assert(global_observer.receive(changed,200,300)==SyncResult::applied);
 assert(global_observer.globals().weather.target=="fog");
 assert(global_observer.receive(global,300,400)!=SyncResult::applied);
 changed.world.clock.authority_epoch=2;changed.world.clock.sequence=1;
 assert(global_observer.receive(changed,400,500)==SyncResult::applied);
 auto replay=changed;replay.world.clock.authority_epoch=1;replay.world.clock.sequence=999;
 assert(global_observer.receive(replay,500,600)==SyncResult::stale);
 assert(!global_observer.ready(100000));
 BridgeObserver observer(123,UINT64_MAX);
 assert(observer.receive(state,100,200)==SyncResult::applied);
 assert(observer.ready(200) && observer.estimate(200)==1500);
 assert(observer.receive(state,100,200)==SyncResult::stale);
 auto foreign=state;foreign.world_seed=1;
 assert(observer.receive(foreign,200,300)==SyncResult::invalid);
 foreign=state;foreign.clock.world_id=124;
 assert(observer.receive(foreign,200,300)==SyncResult::invalid);
 assert(!observer.ready(100000)); // holdover never grants authority
 state.clock.authority_epoch=2;state.clock.sequence=1;state.clock.world_ms=1000;
 assert(observer.receive(state,100000,100100)==SyncResult::applied);
 assert(observer.ready(100100));
 state.clock.authority_epoch=1;state.clock.sequence=100;
 assert(observer.receive(state,100100,100200)==SyncResult::stale);
 BridgeJson config={{"schema",1},{"mode","shadow"},{"host","127.0.0.1"},{"port",38477},{"token",std::string(48,'t')}};
 assert(BridgeConfig::parse(config.dump()).port==38477);
 auto bad=config;bad["host"]="example.com";rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=config;bad["mode"]="authoritative";rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=config;bad["token"]="x\r\nHost:example.com";rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=config;bad["port"]=65536;rejects([&]{BridgeConfig::parse(bad.dump());});
 auto binding=config;binding["schema"]=2;
 binding["master_world_id"]=123;binding["master_world_seed"]=UINT64_MAX;
 binding["local_world_id"]=900;binding["local_world_seed"]=0;binding["location"]="cordon";
 const auto bound=BridgeConfig::parse(binding.dump());
 auto local_scope=state;local_scope.clock.world_id=900;local_scope.world_seed=0;
 assert(bound.bound && bound.matches_local(local_scope,"cordon"));
 assert(!bound.matches_local(local_scope,"garbage") && !bound.matches_local(local_scope));
 auto wrong_scope=local_scope;wrong_scope.clock.world_id=901;
 assert(!bound.matches_local(wrong_scope,"cordon"));
 wrong_scope=local_scope;wrong_scope.world_seed=1;
 assert(!bound.matches_local(wrong_scope,"cordon"));
 bad=binding;bad.erase("master_world_seed");rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=binding;bad["master_world_id"]=0;rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=binding;bad["local_world_seed"]=false;rejects([&]{BridgeConfig::parse(bad.dump());});
 bad=binding;bad["location"]="bad\nmap";rejects([&]{BridgeConfig::parse(bad.dump());});
 WorldBridgeWorker isolated;
 MasterProjection projection{};projection.event_watermark=999;
 assert(!isolated.read_projection(state,projection) && projection.event_watermark==0);
 assert(!isolated.tick(state).ready);
 assert(isolated.start("does-not-exist.json",state)==0);
 {std::ofstream file("invalid.json");file<<"{}";}
 assert(isolated.start("invalid.json",state)==-1);
 assert(!isolated.tick(state).ready);
 {std::ofstream file("oversize.json");file<<std::string(4097,' ');}
 assert(isolated.start("oversize.json",state)==-1);
 {std::ofstream file("bound.json");file<<binding.dump();}
 assert(isolated.start("bound.json",local_scope,"garbage")==-1);
 assert(isolated.start("bound.json",wrong_scope,"cordon")==-1);
 isolated.stop();isolated.stop();
 assert(argc>=2);
 std::ifstream persisted_file(argv[1]);
 const std::string persisted((std::istreambuf_iterator<char>(persisted_file)),std::istreambuf_iterator<char>());
 auto persisted_global=parse_bridge_globals(persisted);
 assert(persisted_global.world.clock.world_ms==1500 && persisted_global.world.world_seed==UINT64_MAX);
 assert(persisted_global.weather.seed==UINT64_MAX && persisted_global.emission.seed==0);
 assert(bridge_weather_phase(persisted_global.weather,1500)==2 && bridge_weather_blend(persisted_global.weather,1500)==.5);
 assert(bridge_emission_phase(persisted_global.emission,1500)==4);
 assert(persisted_global.weather.version==2 && persisted_global.emission.version==4);
 std::cout<<"PASS: actual SQLite/World/Timelines bootstrap decoded by native parser on GCC/MSVC\n";
 // Genuine backend checkpoints across a Store/World restart, delivered with
 // deterministic asymmetric delay, duplicates, reorder and a long outage.
 const auto recovery=BridgeJson::parse(persisted).at("recovery");
 const auto before_restart=parse_bridge_globals(recovery.at(0).dump());
 const auto after_restart=parse_bridge_globals(recovery.at(1).dump());
 const auto after_catchup=parse_bridge_globals(recovery.at(2).dump());
 BridgeObserver recovering(123,UINT64_MAX);
 assert(recovering.receive(persisted_global,100,140)==SyncResult::applied);
 const double presented=recovering.estimate(140);
 assert(recovering.receive(before_restart,160,220)==SyncResult::applied);
 assert(recovering.estimate(220)>=presented);
 assert(recovering.receive(before_restart,220,220)==SyncResult::stale);
 assert(recovering.receive(persisted_global,220,220)==SyncResult::stale);
 auto too_late=before_restart;++too_late.world.clock.sequence;
 assert(recovering.receive(too_late,220,2220)==SyncResult::invalid);
 assert(recovering.globals().world.clock.sequence==before_restart.world.clock.sequence);
 assert(!recovering.ready(32000));
 assert(after_restart.world.clock.authority_epoch>before_restart.world.clock.authority_epoch);
 assert(after_restart.world.clock.world_ms==before_restart.world.clock.world_ms); // Downtime frozen.
 assert(recovering.receive(after_restart,40000,40080)==SyncResult::applied && recovering.ready(40080));
 assert(recovering.globals().weather.id==before_restart.weather.id && recovering.globals().emission.id==before_restart.emission.id);
 auto old_epoch=before_restart;old_epoch.world.clock.sequence=999;
 assert(recovering.receive(old_epoch,40080,40080)!=SyncResult::applied);
 assert(recovering.globals().world.clock.authority_epoch==after_restart.world.clock.authority_epoch);
 assert(recovering.receive(after_catchup,40300,40320)==SyncResult::applied);
 assert(recovering.globals().emission.version==5 && bridge_emission_phase(recovering.globals().emission,after_catchup.world.clock.world_ms)==5);
 assert(recovering.globals().event_watermark>after_restart.event_watermark);
 std::cout<<"PASS: real durable backend restart -> native observer; asymmetric delivery, duplicates/reorder, loss/holdover, epoch fencing and phase catchup\n";
#ifdef _WIN32
 assert(argc==3);
 config["port"]=unsigned(std::strtoul(argv[2],nullptr,10));
 auto connection=BridgeConfig::parse(config.dump());
 BridgeBootstrap actual{};
 assert(bridge_fetch(connection,actual));
 assert(actual.world.clock.world_id==123 && actual.world.world_seed==UINT64_MAX);
 assert(actual.weather.present && actual.weather.target=="rain" && actual.emission.present);
 {std::ofstream file("observer.json");file<<config.dump();}
 assert(isolated.start("observer.json",actual.world)==1);
 bool accepted=false;
 for (int i=0;i<100 && !accepted;++i) {
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  auto diagnostic=isolated.tick(actual.world);accepted=diagnostic.accepted;
  if(accepted)assert(diagnostic.ready && diagnostic.fetched && !diagnostic.master_binding && diagnostic.weather_phase==2 &&
                    diagnostic.weather_blend>0 && diagnostic.weather_blend<1 && diagnostic.emission_phase==4);
 }
 assert(accepted);
 auto stopped=std::chrono::steady_clock::now();isolated.stop();
 assert(std::chrono::steady_clock::now()-stopped<std::chrono::seconds(3));
 assert(!isolated.tick(actual.world).ready);
 // Two independently persisted ALife identities observe the same global
 // master without rewriting either checkpoint or weakening remote identity.
 for(unsigned map_index=0;map_index<2;++map_index) {
  const char* map=map_index==0 ? "cordon":"garbage";
  auto scoped=config;scoped["schema"]=2;scoped["location"]=map;
  scoped["master_world_id"]=123;scoped["master_world_seed"]=UINT64_MAX;
  scoped["local_world_id"]=900+map_index;scoped["local_world_seed"]=17+map_index;
  auto checkpoint=actual.world;checkpoint.clock.world_id=900+map_index;checkpoint.world_seed=17+map_index;
  checkpoint.clock.authority_epoch=89+map_index; // Independent local checkpoint writer.
  {std::ofstream file("bound.json");file<<scoped.dump();}
  assert(isolated.start("bound.json",checkpoint,map)==1);
  projection.event_watermark=999;
  assert(!isolated.read_projection(checkpoint,projection) && projection.event_watermark==0); // tick must accept first.
  accepted=false;
  for(int i=0;i<100 && !accepted;++i) {
   std::this_thread::sleep_for(std::chrono::milliseconds(20));
   const auto diagnostic=isolated.tick(checkpoint);accepted=diagnostic.accepted;
   if(accepted)assert(diagnostic.ready && diagnostic.master_binding && diagnostic.weather_phase==2 && diagnostic.emission_phase==4);
  }
  assert(accepted && checkpoint.clock.world_id==900+map_index && checkpoint.world_seed==17+map_index);
  assert(isolated.read_projection(checkpoint,projection));
  assert(projection.world.clock.world_id==123 && projection.world.world_seed==UINT64_MAX);
  assert(projection.world.clock.authority_epoch==actual.world.clock.authority_epoch);
  assert(projection.local_world==900+map_index && projection.local_seed==17+map_index && projection.local_epoch==89+map_index);
  assert(projection.master_binding && std::string(projection.location)==map && projection.event_watermark>0);
  assert(projection.weather.present && projection.weather.version==actual.weather.version && projection.weather.seed==UINT64_MAX);
  assert(std::string(projection.weather.id)==actual.weather.id && std::string(projection.weather.source)=="clear" &&
         std::string(projection.weather.target)=="rain" && projection.weather.ended==100000);
  assert(projection.emission.present && projection.emission.seed==0 && projection.emission.intensity==.8 &&
         projection.emission.peak==300 && projection.emission.ended==100000);
  assert(projection.estimated_world_ms>=projection.world.clock.world_ms && projection.weather_phase==2 && projection.emission_phase==4);
  auto foreign_checkpoint=checkpoint;foreign_checkpoint.clock.world_id=902;
  assert(!isolated.tick(foreign_checkpoint).ready);
  assert(!isolated.read_projection(foreign_checkpoint,projection) && projection.local_world==0 && !projection.weather.present);
  foreign_checkpoint=checkpoint;foreign_checkpoint.world_seed=999;
  assert(!isolated.read_projection(foreign_checkpoint,projection) && projection.event_watermark==0);
  foreign_checkpoint=checkpoint;++foreign_checkpoint.clock.authority_epoch;
  assert(!isolated.tick(foreign_checkpoint).ready);
  assert(!isolated.read_projection(foreign_checkpoint,projection) && projection.local_epoch==0);
  assert(isolated.read_projection(checkpoint,projection));
  isolated.stop();
  assert(!isolated.read_projection(checkpoint,projection) && !projection.weather.present && projection.event_watermark==0);
 }
 std::cout<<"PASS: coherent typed projection retains independent local/master epochs and clears stale output on scope change or stop\n";
 std::cout<<"PASS: two distinct local checkpoint scopes bind one master; wrong map/world/seed rejected without identity mutation\n";
 auto mismatched=actual.world;mismatched.world_seed=1;
 assert(isolated.start("observer.json",mismatched)==1);
 for (int i=0;i<20;++i) {
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  auto diagnostic=isolated.tick(mismatched);assert(!diagnostic.ready && !diagnostic.accepted);
 }
 isolated.stop();
 connection.token=std::string(48,'x');assert(!bridge_fetch(connection,actual));
 connection.port=0;assert(!bridge_fetch(connection,actual));
 std::cout<<"PASS: real WinHTTP->authenticated backend clock/weather/emission bootstrap, worker playback, u64 seed and failed auth\n";
#endif
 std::cout<<"PASS: bounded JSON/wire schema, world/seed fencing, stale samples, epoch recovery, holdover, loopback/shadow-only config\n";
 std::cout<<"PASS: coherent global timelines, analytic phase boundaries, immutable versions, watermark/revision fencing and malformed schedules\n";
}
'''
with TemporaryDirectory(prefix="world-bridge-") as tmp:
    cpp = Path(tmp)/"check.cpp"
    exe = Path(tmp)/("check.exe" if os.name=="nt" else "check")
    cpp.write_text(source,encoding="utf-8")
    include=str(root/"src/xrGame")
    if os.name=="nt":
        command=["cl","/nologo","/std:c++17","/EHsc","/W4","/WX","/O2","/I"+include,
                 str(cpp),str(root/"src/xrGame/netcoop_world_bridge_worker.cpp"),
                 "/Fe:"+str(exe),"/Fo:"+tmp+os.sep,"/link","winhttp.lib"]
    else:
        command=["g++","-std=c++17","-Wall","-Wextra","-Werror","-O2","-pthread","-I",include,str(cpp),
                 str(root/"src/xrGame/netcoop_world_bridge_worker.cpp"),"-o",str(exe)]
    subprocess.run(command,check=True,cwd=tmp)
    fixture_store=Store(Path(tmp)/"bootstrap.db")
    try:
        fixture_ns=[0]
        fixture_world=World(fixture_store,world_id=123,seed=2**64-1,initial_ms=1500,scale=1,monotonic=lambda:fixture_ns[0])
        fixture_timelines=Timelines(fixture_world)
        fixture_timelines.schedule("admin",uuid.uuid4().hex,"weather",uuid.uuid4().hex,0,
                                  {"TRANSITION":1000,"SETTLED":2000},
                                  {"source":"clear","target":"rain","seed":2**64-1})
        # Background catch-up first: a mutation resolves earlier due events only
        # within a 5 ms real-time budget and refuses otherwise (slow CI runners).
        fixture_timelines.scheduler.run_due(limit=64,budget_ms=1000)
        fixture_timelines.schedule("admin",uuid.uuid4().hex,"emission",uuid.uuid4().hex,0,
                                  {"WARNING":1100,"ACTIVE":1200,"PEAK":1400,"ENDED":1800},
                                  {"intensity":.8,"seed":0})
        fixture_timelines.scheduler.run_due(limit=64,budget_ms=1000)
        fixture_path=Path(tmp)/"bootstrap.json"
        fixture_world.set_state("admin",uuid.uuid4().hex,"unrelated",0,{"private":"x"*100000})
        initial=fixture_world.engine_bootstrap_snapshot()
        fixture_ns[0]=50_000_000
        before_restart=fixture_world.engine_bootstrap_snapshot()
        fixture_store.close()
        fixture_ns[0]=1_000_000_000_000
        fixture_store=Store(Path(tmp)/"bootstrap.db")
        fixture_world=World(fixture_store,world_id=123,seed=2**64-1,monotonic=lambda:fixture_ns[0])
        after_restart=fixture_world.engine_bootstrap_snapshot()
        fixture_ns[0]+=300_000_000
        Timelines(fixture_world).scheduler.run_due(limit=64,budget_ms=1000)
        after_catchup=fixture_world.engine_bootstrap_snapshot()
        fixture_path.write_text(json.dumps({"result":initial,"recovery":[{"result":sample} for sample in
                                (before_restart,after_restart,after_catchup)]}),encoding="utf-8")
    finally:
        fixture_store.close()
    if os.name=="nt":
        store=Store(Path(tmp)/"world.db")
        world=World(store,world_id=123,seed=2**64-1,initial_ms=1000,scale=1)
        timelines=Timelines(world)
        timelines.schedule("admin",uuid.uuid4().hex,"weather",uuid.uuid4().hex,0,
                           {"TRANSITION":0,"SETTLED":100000},
                           {"source":"clear","target":"rain","seed":2**64-1})
        timelines.schedule("admin",uuid.uuid4().hex,"emission",uuid.uuid4().hex,0,
                           {"WARNING":100,"ACTIVE":200,"PEAK":300,"ENDED":100000},
                           {"intensity":.8,"seed":0})
        timelines.scheduler.run_due(limit=64,budget_ms=1000)
        world.set_state("admin",uuid.uuid4().hex,"unrelated",0,{"private":"x"*100000})
        credentials=Credentials({"observer":{"role":"observer","token":"t"*48}})
        server=Server(("127.0.0.1",0),Dispatcher(world,b"k"*32),credentials)
        worker=threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            subprocess.run([str(exe),str(fixture_path),str(server.server_address[1])],check=True,cwd=tmp)
        finally:
            server.shutdown();server.server_close();worker.join();store.close()
    else:
        subprocess.run([str(exe),str(fixture_path)],check=True,cwd=tmp)
