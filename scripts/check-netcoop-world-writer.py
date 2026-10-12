"""CI-only native writer transport against the real durable HTTP master."""
from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import json

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from lostzone import Store, World
from lostzone.http import Credentials, Dispatcher, Server
from lostzone.__main__ import create_config, create_writer_config

source = r'''
#define NOMINMAX
#include "netcoop_world_writer.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
using namespace netcoop_world;
template<class F>void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
int main(int argc,char** argv){
 (void)argc;(void)argv;
 BridgeJson body={{"schema",1},{"mode","writer"},{"host","127.0.0.1"},{"port",12345},
  {"token",std::string(48,'s')},{"actor","location:cordon"},{"location","cordon"},
  {"master_world_id",71},{"master_world_seed",0}};
 auto config=WriterConfig::parse(body.dump(),"cordon");assert(config.world==71 && config.seed==0);
 for(const char* key:{"host","mode","actor","location","token"}){
  auto invalid=body;invalid[key]="bad";rejects([&]{WriterConfig::parse(invalid.dump(),"cordon");});
 }
 rejects([&]{WriterConfig::parse(body.dump(),"garbage");});
 for(auto value:{BridgeJson(0),BridgeJson(-1),BridgeJson(65536),BridgeJson(true),BridgeJson(1.5)}){
  auto invalid=body;invalid["port"]=value;rejects([&]{WriterConfig::parse(invalid.dump(),"cordon");});
 }
 auto extra=body;extra["admin"]=true;rejects([&]{WriterConfig::parse(extra.dump(),"cordon");});
 assert(writer_instance_valid(std::string(32,'a')) && !writer_instance_valid(std::string(32,'A')));
#ifdef _WIN32
 assert(argc==3);
 auto read=[](const char* filename){std::ifstream in(filename,std::ios::binary);return std::string(std::istreambuf_iterator<char>(in),{});};
 auto src=WriterConfig::parse(read(argv[1]),"cordon"),dst=WriterConfig::parse(read(argv[2]),"garbage");
 const std::string a(32,'a'),b(32,'b'),c(32,'c');
 BridgeJson result;unsigned status=0,seq=0;
 assert(writer_request(src,a,0,"GET","/v1/clock","",result,status));
 assert(result["world_id"]==71 && result["seed"]==0);auto epoch=bridge_unsigned(result,"authority_epoch");
 auto command=[&](const WriterConfig& cfg,const std::string& instance,const std::string& operation,
                  const BridgeJson& args,std::string id=""){
  if(id.empty()){char token[33];std::snprintf(token,sizeof(token),"%032x",++seq);id=token;}
  return writer_request(cfg,instance,epoch,"POST","/v1/command",
   BridgeJson{{"command_id",id},{"operation",operation},{"arguments",args}}.dump(),result,status);
 };
 assert(command(src,a,"location_claim",{{"location","cordon"}}));auto sf=bridge_unsigned(result,"fence");
 assert(!command(src,b,"location_claim",{{"location","cordon"}}) && status==409 && result.is_null());
 assert(!command(src,b,"location_renew",{{"location","cordon"},{"fence",sf}}) && status==409);
 assert(command(dst,c,"location_claim",{{"location","garbage"}}));auto tf=bridge_unsigned(result,"fence");
 assert(!command(src,a,"location_claim",{{"location","garbage"}}) && status==403);
 auto wrong=src;wrong.seed=1;
 assert(!command(wrong,a,"location_renew",{{"location","cordon"},{"fence",sf}}) && status==409);
 ++epoch;assert(!command(src,a,"location_renew",{{"location","cordon"},{"fence",sf}}) && status==409);--epoch;
 const std::string npc(32,'1'),group(32,'2'),mutant(32,'3'),item(32,'4');
 assert(command(src,a,"entity_create",{{"entity_id",npc},{"kind","NPC"},{"location","cordon"},{"fence",sf},
  {"state",{{"health",0.72},{"engine_state","saved NPC state"}}}}));
 assert(command(src,a,"entity_create",{{"entity_id",mutant},{"kind","MUTANT"},{"location","cordon"},{"fence",sf},
  {"state",{{"health",0.41}}}}));
 assert(command(src,a,"entity_create",{{"entity_id",group},{"kind","GROUP"},{"location","cordon"},{"fence",sf},
  {"state",{{"member_ids",BridgeJson::array({npc,mutant})}}}}));
 assert(command(src,a,"item_create",{{"item_id",item},{"section","wpn_ak74"},{"location","cordon"},{"fence",sf},
  {"kind","NPC"},{"holder",npc},{"state",{{"condition",0.53},{"rounds",17}}}}));
 assert(command(src,a,"transfer_prepare",{{"entity_id",group},{"source","cordon"},{"source_fence",sf},
  {"target","garbage"},{"entity_version",1}}));
 const auto transfer=result["transfer_id"].get<std::string>(),token=result["token"].get<std::string>();
 assert(!command(src,a,"entity_update",{{"entity_id",npc},{"fence",sf},{"version",1},{"state",{{"health",1}}}}) && status==409);
 assert(command(dst,c,"transfer_claim",{{"token",token},{"target_fence",tf}}));
 assert(result["checkpoint"]["entities"].size()==3 && result["checkpoint"]["items"].size()==1);
 assert(result["checkpoint"]["items"][0]["id"]==item);
 const std::string commit(32,'f');
 assert(command(dst,c,"transfer_commit",{{"transfer_id",transfer},{"target_fence",tf}},commit));
 assert(result["state"]=="COMMITTED");auto committed=result;
 assert(command(dst,c,"transfer_commit",{{"transfer_id",transfer},{"target_fence",tf}},commit) && result==committed);
 assert(writer_request(dst,c,epoch,"GET","/v1/location?id=garbage&fence="+std::to_string(tf),"",result,status));
 assert(result["entities"].size()==3 && result["items"].size()==1);
 assert(writer_request(src,a,epoch,"GET","/v1/transfer?id="+transfer,"",result,status) && result["state"]=="COMMITTED");
 assert(!command(src,a,"world_scale",{{"value",100}}) && status==0);
 auto admin=src;admin.token=std::string(48,'a');
 assert(!command(admin,b,"location_claim",{{"location","cordon"}}) && status==403);
 std::cout<<"PASS actual WinHTTP master: separate runtime leases, scope/world/epoch checks, frozen source, group NPC+mutant+inventory transferred with the same IDs, idempotent commit\n";
#endif
 std::cout<<"PASS writer config: exact schema, loopback-only endpoint, map identity, bounded credential and persistent instance\n";
}
'''
with TemporaryDirectory(prefix="world-writer-") as tmp:
    folder = Path(tmp)
    cpp = folder / "writer.cpp"
    exe = folder / ("writer.exe" if os.name == "nt" else "writer")
    cpp.write_text(source, encoding="utf-8")
    include = str(root / "src/xrGame")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2", "/I"+include,
                str(cpp), "/Fe:"+str(exe), "/link", "winhttp.lib"] if os.name == "nt" else
               ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2", "-I", include, str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    if os.name != "nt":
        subprocess.run([str(exe)], cwd=tmp, check=True)
    else:
        store = Store(folder / "world.db")
        world = World(store, world_id=71, seed=0)
        credentials = {"location:cordon":{"role":"location","locations":["cordon"],"token":"s"*48},
                       "location:garbage":{"role":"location","locations":["garbage"],"token":"d"*48},
                       "admin":{"role":"admin","token":"a"*48}}
        server = Server(("127.0.0.1", 0), Dispatcher(world, b"k"*32), Credentials(credentials))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            config = folder / "private.json"
            create_config(config, ["cordon", "garbage"], world_id=71, seed=0)
            data = json.loads(config.read_bytes())
            data["credentials"] = credentials
            data["port"] = server.server_address[1]
            config.write_text(json.dumps(data))
            paths = []
            for location in ("cordon", "garbage"):
                dest = folder / ("netcoop_world_writer_"+location+".json")
                create_writer_config(config, dest, location)
                paths.append(str(dest))
            subprocess.run([str(exe), *paths], cwd=tmp, check=True)
            assert store.db.execute("SELECT COUNT(*) FROM entity WHERE location='garbage'").fetchone()[0] == 3
            assert store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 1
            assert store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='TransferCommitted'").fetchone()[0] == 1
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            store.close()
