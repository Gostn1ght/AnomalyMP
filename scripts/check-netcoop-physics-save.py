"""Run actual prop capture and checkpoint selection code with engine API doubles."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
prop = (root / "src/xrGame/PhysicObject.cpp").read_text(encoding="utf-8")
engine = (root / "src/xrGame/netcoop.cpp").read_text(encoding="utf-8")
start = prop.index("bool CPhysicObject::netcoop_capture_saved_physics(")
capture = prop[start:prop.index("void CPhysicObject::net_Save(", start)]
start = engine.index("static bool world_store_capture_physics_props()")
select = engine[start:engine.index('#include "netcoop_world_store.inc"', start)]
source = r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include <map>
#include <string>
#include <iostream>
#include <stdexcept>
#include <cmath>
#include <algorithm>
#include <cstring>
using u8=std::uint8_t;using u16=std::uint16_t;using u32=std::uint32_t;
template<class T>using xr_vector=std::vector<T>;
constexpr bool TRUE=true;constexpr u32 NET_PacketSizeLimit=16384;
template<class T,class P>T smart_cast(P* p){return dynamic_cast<T>(p);}
void Msg(const char*,...){}
struct Fvector {float x=0,y=0,z=0;bool operator==(const Fvector& v)const{return x==v.x&&y==v.y&&z==v.z;}};
bool _valid(const Fvector& v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
struct Matrix {Fvector angles;void getHPB(Fvector& out)const{out=angles;}};
struct Flags {u8 value=0;void assign(u8 f){value=f;}void set(u8 f,bool b){value=b?u8(value|f):u8(value&~f);}};
struct NET_Packet {
 struct {u32 count=99;} B;
 u32 read=999;u8 flags=0;std::vector<int> bodies;std::vector<u8> prefix;
 bool has_chunk=false;u16 chunk_bytes=0;
 void w_chunk_open16(u32& p){assert(B.count==0);p=0;B.count=2;has_chunk=true;}
 void w_chunk_close16(u32 p){assert(p==0);chunk_bytes=u16(prefix.size());}
 void w_u8(u8 v){prefix.push_back(v);++B.count;}
 void r_seek(u32 p){read=p;}
 u16 r_u16(){assert(read==0 && has_chunk);read=2;return chunk_bytes;}
 u32 r_elapsed()const{return B.count-read;}
 void r(void* out,u32 bytes){assert(read==2 && bytes==prefix.size());std::memcpy(out,prefix.data(),bytes);read+=bytes;}
 u8 r_u8(){assert(read==(has_chunk?2u+u32(prefix.size()):0u));++read;return flags;}
 bool r_eof()const{return read==B.count;}
};
bool bad_count=false,bad_eof=false,throw_decode=false;
struct SPHBonesData {
 std::vector<int> bones;
 void net_Load(NET_Packet& p){
  assert(p.read==(p.has_chunk?3u+u32(p.prefix.size()):1u));if(throw_decode)throw std::runtime_error("decode fault");
  bones=p.bodies;if(bad_count)bones.pop_back();p.read=p.B.count-(bad_eof?1u:0u);
 }
};
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=7,parent=55;std::string section="prop",name="original";std::vector<u8> client_data{90,91};};
struct CSE_PHSkeleton {
 virtual ~CSE_PHSkeleton()=default;
 enum:u8 {flActive=1,flSavedData=4,flNotSave=8};
 Flags _flags;SPHBonesData saved_bones;u16 source_id=123;std::string startup="door";
 bool need_save()const{return !(_flags.value&flNotSave);}
};
struct CSE_ALifeObjectPhysic:CSE_Abstract,CSE_PHSkeleton {Fvector o_Position,o_Angle;};
struct Object {virtual ~Object()=default;};
struct CPHSkeleton {
 std::vector<int> bodies{10,20};int save_calls=0;u8 simulated_flags=1;
 void SaveNetState(NET_Packet& p){++save_calls;p.flags=simulated_flags;p.bodies=bodies;p.B.count+=37+8*u32(bodies.size());}
};
struct CScriptBinderObject {
 int saves=0;bool fail=false,empty=false,oversize=false;std::vector<u8> data{11,12,13};
 void save(NET_Packet* p){++saves;if(fail)throw std::runtime_error("door binder save fault");if(oversize){for(u32 i=0;i<16360;++i)p->w_u8(0);return;}if(!empty)for(u8 b:data)p->w_u8(b);}
};
struct CScriptBinder {CScriptBinderObject* attached_binder=nullptr;CScriptBinderObject* object(){return attached_binder;}};
struct CPhysicsShellHolder {void save(NET_Packet& p){p.w_u8(42);}};
struct CPhysicObject:Object,CPHSkeleton,CScriptBinder,CPhysicsShellHolder {
 u16 id=7,simulated_count=2;bool destroyed=false,parented=false,shell=true;
 Fvector position{1,2,3};Matrix matrix{{4,5,6}};
 u16 ID()const{return id;}u16 PHGetSyncItemsNumber()const{return simulated_count;}
 bool getDestroy()const{return destroyed;}bool H_Parent()const{return parented;}
 bool PPhysicsShell()const{return shell;}
 const Fvector& Position()const{return position;}const Matrix& XFORM()const{return matrix;}
 void net_Save(NET_Packet&){throw std::runtime_error("whole object save must not run");}
 bool netcoop_capture_saved_physics(CSE_Abstract*,bool=false);
};
struct Game {std::map<u16,CSE_Abstract*> entities;CSE_Abstract* get_entity_from_eid(u16 id){auto f=entities.find(id);return f==entities.end()?nullptr:f->second;}};
struct ServerType {Game* game=nullptr;};
struct ObjectList {std::vector<Object*> objects;u32 o_count()const{return u32(objects.size());}Object* o_get_by_iterator(u32 n){return objects.at(n);}};
struct LevelType {ServerType* Server=nullptr;ObjectList Objects;} level;
LevelType& Level(){return level;}
bool classifier_available=true;std::vector<u16> ready_doors;
namespace luabind {template<class R>struct functor {R operator()(u16 id)const{return std::find(ready_doors.begin(),ready_doors.end(),id)!=ready_doors.end();}};}
struct ScriptEngine {template<class F>bool functor(const char* name,F&){assert(std::string(name)=="zz_netcoop_world_rules.physics_door_binder_ready");return classifier_available;}};
struct AI {ScriptEngine engine;ScriptEngine& script_engine(){return engine;}};
AI& ai(){static AI instance;return instance;}
''' + capture + select + r'''
int main(){
 CPhysicObject prop;CSE_ALifeObjectPhysic entity;
 entity.saved_bones.bones={99};
 assert(prop.netcoop_capture_saved_physics(&entity));
 assert(entity.saved_bones.bones==prop.bodies && entity._flags.value==5);
 assert(entity.o_Position==prop.position && entity.o_Angle==prop.matrix.angles);
 assert(entity.ID==7 && entity.parent==55 && entity.section=="prop" && entity.name=="original");
 assert(entity.source_id==123 && entity.startup=="door");
 prop.bodies={30,40};assert(prop.netcoop_capture_saved_physics(&entity));
 assert((entity.saved_bones.bones==std::vector<int>{30,40}));
 // Invalid capture leaves the previous decoded state intact.
 auto unchanged=[&]{assert((entity.saved_bones.bones==std::vector<int>{30,40}));assert(entity._flags.value==5);};
 bad_count=true;assert(!prop.netcoop_capture_saved_physics(&entity));unchanged();bad_count=false;
 bad_eof=true;assert(!prop.netcoop_capture_saved_physics(&entity));unchanged();bad_eof=false;
 throw_decode=true;bool threw=false;try{prop.netcoop_capture_saved_physics(&entity);}catch(const std::exception&){threw=true;}
 assert(threw);unchanged();throw_decode=false;
 const int calls=prop.save_calls;
 CSE_Abstract wrong;assert(!prop.netcoop_capture_saved_physics(&wrong));assert(!prop.netcoop_capture_saved_physics(nullptr));
 entity.ID=8;assert(!prop.netcoop_capture_saved_physics(&entity));entity.ID=7;
 prop.destroyed=true;assert(!prop.netcoop_capture_saved_physics(&entity));prop.destroyed=false;
 prop.parented=true;assert(!prop.netcoop_capture_saved_physics(&entity));prop.parented=false;
 prop.shell=false;assert(!prop.netcoop_capture_saved_physics(&entity));prop.shell=true;
 prop.simulated_count=0;assert(!prop.netcoop_capture_saved_physics(&entity));
 prop.simulated_count=2044;assert(!prop.netcoop_capture_saved_physics(&entity));prop.simulated_count=2;
 prop.position.x=INFINITY;assert(!prop.netcoop_capture_saved_physics(&entity));prop.position.x=1;
 prop.matrix.angles.x=INFINITY;assert(!prop.netcoop_capture_saved_physics(&entity));prop.matrix.angles.x=4;
 assert(prop.save_calls==calls);unchanged();
 assert((entity.client_data==std::vector<u8>{90,91})); // furniture keeps prior game data
 CPhysicObject door;CScriptBinderObject binder;CSE_ALifeObjectPhysic door_entity;
 assert(!door.netcoop_capture_saved_physics(&door_entity,true));
 door.attached_binder=&binder;
 assert(door.netcoop_capture_saved_physics(&door_entity,true));
 assert((door_entity.client_data==std::vector<u8>{42,11,12,13}));
 binder.data={21,22};assert(door.netcoop_capture_saved_physics(&door_entity,true));
 assert((door_entity.client_data==std::vector<u8>{42,21,22}));
 const auto committed_data=door_entity.client_data;const auto committed_bones=door_entity.saved_bones.bones;
 auto door_unchanged=[&]{assert(door_entity.client_data==committed_data && door_entity.saved_bones.bones==committed_bones);assert(door.attached_binder==&binder);};
 binder.fail=true;threw=false;try{door.netcoop_capture_saved_physics(&door_entity,true);}catch(const std::exception&){threw=true;}assert(threw);door_unchanged();binder.fail=false;
 binder.empty=true;assert(!door.netcoop_capture_saved_physics(&door_entity,true));door_unchanged();binder.empty=false;
 binder.oversize=true;const int before_overflow=door.save_calls;assert(!door.netcoop_capture_saved_physics(&door_entity,true));assert(door.save_calls==before_overflow);door_unchanged();binder.oversize=false;
 bad_count=true;assert(!door.netcoop_capture_saved_physics(&door_entity,true));door_unchanged();bad_count=false;
 bad_eof=true;assert(!door.netcoop_capture_saved_physics(&door_entity,true));door_unchanged();bad_eof=false;
 // Check actual checkpoint traversal against unrelated/removed/attached props.
 assert(!world_store_capture_physics_props());
 ServerType server;level.Server=&server;assert(!world_store_capture_physics_props());
 Game game;server.game=&game;Object actor,item,corpse;
 CPhysicObject destroyed,attached,no_shell,no_bodies,not_saved;
 destroyed.destroyed=true;attached.parented=true;no_shell.shell=false;no_bodies.simulated_count=0;not_saved.id=8;
 CSE_ALifeObjectPhysic excluded;excluded.ID=8;excluded._flags.value=CSE_PHSkeleton::flNotSave;
 game.entities={{u16(7),&entity},{u16(8),&excluded}};
 level.Objects.objects={&actor,&item,&corpse,&destroyed,&attached,&no_shell,&no_bodies,&not_saved,&prop};
 assert(world_store_capture_physics_props());assert(prop.save_calls==calls+1);
 assert(destroyed.save_calls==0 && attached.save_calls==0 && no_shell.save_calls==0 && no_bodies.save_calls==0 && not_saved.save_calls==0);
 game.entities.erase(7);assert(!world_store_capture_physics_props());assert(prop.save_calls==calls+1);
 game.entities[7]=&wrong;assert(!world_store_capture_physics_props());
 game.entities[7]=&door_entity;level.Objects.objects={&actor,&item,&corpse,&door};ready_doors={7};
 const int previous_saves=binder.saves;assert(world_store_capture_physics_props());assert(binder.saves==previous_saves+1);
 ready_doors.clear();assert(world_store_capture_physics_props());assert(binder.saves==previous_saves+1);
 ready_doors={7};classifier_available=false;assert(world_store_capture_physics_props());assert(binder.saves==previous_saves+1);
 std::cout<<"PASS: actual physics/door capture; scoped binder, strict exceptions/no deletion, atomic decode, bounds, metadata, selection and legacy classifier fallback\n";
}
'''
with TemporaryDirectory(prefix="physics-save-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True, cwd=tmp)
