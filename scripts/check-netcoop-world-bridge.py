"""Compile actual read-only bridge; Windows calls the real local HTTP service."""
from pathlib import Path
import os
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

source = r'''
#define NOMINMAX
#include "netcoop_world_bridge.h"
#include "netcoop_world_bridge_worker.h"
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <fstream>
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
 WorldBridgeWorker isolated;
 assert(!isolated.tick(state).ready);
 assert(isolated.start("does-not-exist.json",state)==0);
 {std::ofstream file("invalid.json");file<<"{}";}
 assert(isolated.start("invalid.json",state)==-1);
 assert(!isolated.tick(state).ready);
 {std::ofstream file("oversize.json");file<<std::string(4097,' ');}
 assert(isolated.start("oversize.json",state)==-1);
 isolated.stop();isolated.stop();
#ifdef _WIN32
 assert(argc==2);
 config["port"]=unsigned(std::strtoul(argv[1],nullptr,10));
 auto connection=BridgeConfig::parse(config.dump());
 WorldStateSnapshot actual{};
 assert(bridge_fetch(connection,actual));
 assert(actual.clock.world_id==123 && actual.world_seed==UINT64_MAX);
 {std::ofstream file("observer.json");file<<config.dump();}
 assert(isolated.start("observer.json",actual)==1);
 bool accepted=false;
 for (int i=0;i<100 && !accepted;++i) {
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  auto diagnostic=isolated.tick(actual);accepted=diagnostic.accepted;
  if(accepted)assert(diagnostic.ready && diagnostic.fetched);
 }
 assert(accepted);
 auto stopped=std::chrono::steady_clock::now();isolated.stop();
 assert(std::chrono::steady_clock::now()-stopped<std::chrono::seconds(3));
 assert(!isolated.tick(actual).ready);
 auto mismatched=actual;mismatched.world_seed=1;
 assert(isolated.start("observer.json",mismatched)==1);
 for (int i=0;i<20;++i) {
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  auto diagnostic=isolated.tick(mismatched);assert(!diagnostic.ready && !diagnostic.accepted);
 }
 isolated.stop();
 connection.token=std::string(48,'x');assert(!bridge_fetch(connection,actual));
 connection.port=0;assert(!bridge_fetch(connection,actual));
 std::cout<<"PASS: real WinHTTP->authenticated backend bootstrap, u64 seed and failed auth\n";
#endif
 std::cout<<"PASS: bounded JSON/wire schema, world/seed fencing, stale samples, epoch recovery, holdover, loopback/shadow-only config\n";
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
    if os.name=="nt":
        store=Store(Path(tmp)/"world.db")
        world=World(store,world_id=123,seed=2**64-1)
        credentials=Credentials({"observer":{"role":"observer","token":"t"*48}})
        server=Server(("127.0.0.1",0),Dispatcher(world,b"k"*32),credentials)
        worker=threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            subprocess.run([str(exe),str(server.server_address[1])],check=True,cwd=tmp)
        finally:
            server.shutdown();server.server_close();worker.join();store.close()
    else:
        subprocess.run([str(exe)],check=True,cwd=tmp)
