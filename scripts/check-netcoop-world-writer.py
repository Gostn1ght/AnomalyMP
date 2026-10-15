"""CI-only native writer transport against the real durable HTTP master."""
from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import json
import base64
import hashlib

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from lostzone import Store, World
from lostzone.http import Credentials, Dispatcher, Server
from lostzone.__main__ import create_config, create_writer_config
from lostzone.native_save import identity
sys.path.insert(0, str(root / "backend/tests"))
from test_native_save import native_fixture

source = r'''
#define NOMINMAX
#include "netcoop_player_checkpoint.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <set>
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
 for(const std::string text:{"","f","fo","foo","foob","fooba","foobar"})
  assert(checkpoint_unbase64(checkpoint_base64(text))==text);
 std::string binary;for(unsigned i=0;i<256;++i) binary+=char(i);
 assert(checkpoint_unbase64(checkpoint_base64(binary))==binary);
 for(const std::string bad:{"Zh==","Zm9=","Zg==AAAA","Zg="," Zg==","Zg??"})
  rejects([&]{checkpoint_unbase64(bad);});
 rejects([&]{checkpoint_unbase64("Zm9v",2);});
 std::cout<<"PASS bounded canonical checkpoint codec: binary bytes, padding bits, malformed input and decode limits\n";
#ifdef _WIN32
 assert(argc==4);
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
 // Real native transport, complete NCH9 bytes, private loopback master.
 const auto fixture=bridge_json(read(argv[3]),1024*1024);
 for(const auto& vector:fixture["identities"])
  assert(checkpoint_player_id(bridge_unsigned(vector,"world"),bridge_unsigned(vector,"seed"),vector["account"].get<std::string>(),
   unsigned(bridge_unsigned(vector,"slot")))==vector["id"]);
 for(const auto& vector:fixture["hashes"])
  assert(checkpoint_sha256(vector["input"].get<std::string>())==vector["sha256"]);
 rejects([&]{checkpoint_player_id(0,0,"alice",1);});
 rejects([&]{checkpoint_player_id(71,0,"../alice",1);});
 rejects([&]{checkpoint_player_id(71,0,"alice",11);});
 rejects([&]{checkpoint_player_id(71,0,"al ice",1);});
 const auto character=fixture["character_id"].get<std::string>();
 assert(command(src,a,"entity_create",{{"entity_id",character},{"kind","CHARACTER"},{"location","cordon"},
  {"fence",sf},{"account","alice"},{"state",{{"position",BridgeJson::array({1,2,3})}}}}));
 auto begin=[&](){return command(src,a,"native_save_begin",{{"character_id",character},{"fence",sf},
  {"session_fence",1},{"entity_version",1},{"base_revision",0},{"slot",1},
  {"byte_count",fixture["bytes"]},{"sha256",fixture["sha256"]}});};
 assert(begin());auto upload=result["upload_id"].get<std::string>();
 assert(command(src,a,"native_save_cancel",{{"character_id",character},{"fence",sf},{"session_fence",1},{"upload_id",upload}}));
 assert(begin());upload=result["upload_id"].get<std::string>();
 assert(!command(src,a,"native_save_finish",{{"character_id",character},{"fence",sf},{"session_fence",1},{"upload_id",upload}}) && status==409);
 assert(!command(src,a,"session_disconnect",{{"character_id",character},{"fence",sf},{"version",1},{"state",BridgeJson::object()}}) && status==409);
 for(const auto& chunk:fixture["chunks"]){
  const auto args=BridgeJson{{"character_id",character},{"fence",sf},{"session_fence",1},{"upload_id",upload},
   {"offset",chunk["offset"]},{"data",chunk["data"]}};
  assert(!command(src,b,"native_save_append",args) && status==409);
  assert(command(src,a,"native_save_append",args));
 }
 const std::string finish(32,'e');
 const auto finish_args=BridgeJson{{"character_id",character},{"fence",sf},{"session_fence",1},{"upload_id",upload}};
 assert(command(src,a,"native_save_finish",finish_args,finish));
 const auto durable=result;assert(result["durable"]==true && result["revision"]==1 && result["sha256"]==fixture["sha256"]);
 assert(command(src,a,"native_save_finish",finish_args,finish) && result==durable);
 auto page_path=[&](std::uint64_t fence,std::uint64_t session,const BridgeJson& offset){
  return "/v1/player-save?character_id="+character+"&fence="+std::to_string(fence)+
   "&session_fence="+std::to_string(session)+"&revision=1&offset="+std::to_string(offset.get<std::uint64_t>());
 };
 for(const auto& chunk:fixture["chunks"]){
  const auto path=page_path(sf,1,chunk["offset"]);
  assert(!writer_request(src,a,0,"GET",path,"",result,status) && status==0);
  assert(writer_request(src,a,epoch,"GET",path,"",result,status));
  assert(result["data"]==chunk["data"] && result["sha256"]==fixture["sha256"] && result["bytes"]==fixture["bytes"]);
 }
 // Logout/reconnect increments the session fence without losing the save.
 assert(command(src,a,"session_disconnect",{{"character_id",character},{"fence",sf},{"version",2},{"state",{{"position",BridgeJson::array({4,5,6})}}}}));
 assert(!writer_request(src,a,epoch,"GET",page_path(sf,1,0),"",result,status) && status==409);
 assert(command(src,a,"session_resume",{{"character_id",character},{"location","cordon"},{"fence",sf},{"version",3}}));
 assert(result["session_fence"]==3 && result["version"]==4);
 assert(command(src,a,"transfer_prepare",{{"entity_id",character},{"source","cordon"},{"source_fence",sf},{"target","garbage"},{"entity_version",4}}));
 const auto character_transfer=result["transfer_id"].get<std::string>(),character_token=result["token"].get<std::string>();
 assert(!writer_request(src,a,epoch,"GET",page_path(sf,3,0),"",result,status) && status==409);
 assert(command(dst,c,"transfer_claim",{{"token",character_token},{"target_fence",tf}}));
 const auto frozen_session=bridge_unsigned(result,"session_fence");
 assert(!writer_request(dst,c,epoch,"GET",page_path(tf,frozen_session,0),"",result,status) && status==403);
 for(const auto& chunk:fixture["chunks"]){
  assert(writer_request(dst,c,epoch,"GET",page_path(tf,frozen_session,chunk["offset"])+"&transfer_id="+character_transfer,"",result,status));
  assert(result["data"]==chunk["data"] && result["sha256"]==fixture["sha256"]);
 }
 assert(command(dst,c,"transfer_commit",{{"transfer_id",character_transfer},{"target_fence",tf}}));
 assert(!writer_request(src,a,epoch,"GET",page_path(sf,3,0),"",result,status) && status==403);
 assert(writer_request(dst,c,epoch,"GET",page_path(tf,frozen_session+1,0),"",result,status));
 assert(result["data"]==fixture["chunks"][0]["data"]);
 // The native client state machine owns encoding, command identity and ack
 // validation. Simulate lost successful replies from the real HTTP master.
 std::string raw;for(const auto& chunk:fixture["chunks"]) raw+=checkpoint_unbase64(chunk["data"].get<std::string>());
 const std::string transaction(32,'d');
 auto make_upload=[&]{return std::make_unique<CheckpointUpload>(raw,character,tf,frozen_session+1,6,1,1,transaction);};
 auto upload_client=make_upload();rejects([&]{upload_client->durable();});
 std::set<std::string> dropped;
 auto actual=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  return writer_request(dst,c,epoch,method,path,payload,out,code);
 };
 auto unreliable=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  const bool ok=actual(method,path,payload,out,code);
  const auto op=bridge_json(payload,65536)["operation"].get<std::string>();
  if(ok && dropped.insert(op).second){out=BridgeJson();code=0;return false;}
  return ok;
 };
 bool uploaded=false,resumed=false;
 for(unsigned tries=0;tries<30 && !uploaded;++tries){
  const auto step=upload_client->step(unreliable);assert(step!=CheckpointStep::Rejected);
  if(step==CheckpointStep::Retry && dropped.count("native_save_append") && !resumed){
   auto cursor=bridge_json(upload_client->cursor().dump(),4096);auto restored=make_upload();
   auto tampered=cursor;tampered["binding"]=std::string(64,'0');rejects([&]{restored->restore_cursor(tampered);});
   tampered=cursor;tampered["offset"]=1;rejects([&]{restored->restore_cursor(tampered);});
   restored->restore_cursor(cursor);upload_client=std::move(restored);resumed=true;
  }
  uploaded=step==CheckpointStep::Complete;
 }
 assert(uploaded && resumed && dropped.size()==3 && upload_client->durable()["revision"]==2);
 auto restored=make_upload();restored->restore_cursor(upload_client->cursor());
 rejects([&]{restored->durable();}); // a saved cursor never proves commit
 auto bad_ack=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  const bool ok=actual(method,path,payload,out,code);if(ok) out["bytes"]=raw.size()+1;return ok;
 };
 assert(restored->step(bad_ack)==CheckpointStep::Rejected);rejects([&]{restored->durable();});
 assert(restored->step(actual)==CheckpointStep::Complete && restored->durable()==upload_client->durable());
 auto wrong_snapshot=std::make_unique<CheckpointUpload>(raw,character,tf,frozen_session+1,6,1,2,transaction);
 rejects([&]{wrong_snapshot->restore_cursor(upload_client->cursor());});
 const auto sha=fixture["sha256"].get<std::string>();
 const auto count=std::size_t(bridge_unsigned(fixture,"bytes"));
 CheckpointDownload download(character,tf,frozen_session+1,2,sha,count);
 rejects([&]{download.bytes();});
 auto lost_read=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  assert(actual(method,path,payload,out,code));out=BridgeJson();code=0;return false;
 };
 assert(download.step(lost_read)==CheckpointStep::Retry);
 auto bad_metadata=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  const bool ok=actual(method,path,payload,out,code);if(ok) out["sha256"]=std::string(64,'0');return ok;
 };
 assert(download.step(bad_metadata)==CheckpointStep::Rejected);rejects([&]{download.bytes();});
 bool downloaded=false;
 for(unsigned tries=0;tries<10 && !downloaded;++tries){
  const auto step=download.step(actual);assert(step!=CheckpointStep::Rejected);downloaded=step==CheckpointStep::Complete;
 }
 assert(downloaded && download.bytes()==raw);
 CheckpointDownload corrupt(character,tf,frozen_session+1,2,sha,count);
 auto corrupt_last=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  const bool ok=actual(method,path,payload,out,code);
  if(ok && bridge_unsigned(out,"next_offset")==count){auto bytes=checkpoint_unbase64(out["data"].get<std::string>());bytes[0]=char(static_cast<unsigned char>(bytes[0])^1U);out["data"]=checkpoint_base64(bytes);}
  return ok;
 };
 bool refused=false;
 for(unsigned tries=0;tries<10 && !refused;++tries) refused=corrupt.step(corrupt_last)==CheckpointStep::Rejected;
 assert(refused && corrupt.step(actual)==CheckpointStep::Rejected);rejects([&]{corrupt.bytes();});
 rejects([&]{CheckpointDownload invalid(character,tf,1,2,sha,checkpoint_limit+1);});
 assert(checkpoint_failure(409)==CheckpointStep::Rejected && checkpoint_failure(429)==CheckpointStep::Retry);
 CheckpointUpload stale(raw,character,sf,1,7,2,1,std::string(32,'b'));
 auto old_source=[&](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& out,unsigned& code){
  return writer_request(src,a,epoch,method,path,payload,out,code);
 };
 assert(stale.step(old_source)==CheckpointStep::Rejected && stale.cursor()["phase"]==0);
 std::cout<<"PASS native checkpoint client: Python-compatible UUID5/SHA256, lost begin/append/finish replies, bound cursor recovery, commit replay, exact binary download, unexposed corrupt/partial reads\n";
 std::cout<<"PASS actual WinHTTP NCH9 chunks: cancel, stale writer, durable replay, exact read, disconnect/resume, fenced handoff read before activation\n";
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
            raw = native_fixture(9, progress=b"quest/info/behavior"*4000)
            native = folder / "native-fixture.json"
            identities=[(71,0,"ALIce",1),(71,0,"alice",2),(72,0,"alice",1),(71,1,"alice",1),
                        (2**64-1,2**64-1,"Ab_.-09",10)]
            native.write_text(json.dumps({"character_id":identity(71,0,"alice",1),"bytes":len(raw),
                "identities":[dict(world=w,seed=s,account=a,slot=n,id=identity(w,s,a,n)) for w,s,a,n in identities],
                "hashes":[dict(input=text,sha256=hashlib.sha256(text.encode()).hexdigest()) for text in ("","abc","binary\\0data")],
                "sha256":hashlib.sha256(raw).hexdigest(),"chunks":[
                    {"offset":offset,"data":base64.b64encode(raw[offset:offset+30720]).decode("ascii")}
                    for offset in range(0,len(raw),30720)]}), encoding="utf-8")
            subprocess.run([str(exe), *paths, str(native)], cwd=tmp, check=True)
            assert store.db.execute("SELECT COUNT(*) FROM entity WHERE location='garbage'").fetchone()[0] == 4
            assert store.db.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 1
            assert store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='TransferCommitted'").fetchone()[0] == 2
            payload = store.db.execute("SELECT payload_base64 FROM native_player_save").fetchone()[0]
            assert base64.b64decode(payload) == raw
            assert store.db.execute("SELECT COUNT(*) FROM native_player_save").fetchone()[0] == 2
            assert store.db.execute("SELECT COUNT(*) FROM world_event WHERE type='NativePlayerSaveCommitted'").fetchone()[0] == 2
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            store.close()
