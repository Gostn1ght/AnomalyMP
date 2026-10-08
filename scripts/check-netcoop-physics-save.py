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
fragment = (root / "src/xrGame/PhysicsSkeletonObject.cpp").read_text(encoding="utf-8")
start = fragment.index("bool CPhysicsSkeletonObject::netcoop_capture_saved_physics(")
fragment_capture = fragment[start:fragment.index("void CPhysicsSkeletonObject::net_Save(", start)]
start = fragment.index("BOOL CPhysicsSkeletonObject::net_Spawn(")
fragment_spawn = fragment[start:fragment.index("void CPhysicsSkeletonObject::SpawnInitPhysics(", start)]
start = engine.index("static bool world_store_capture_physics_props()")
select = engine[start:engine.index('#include "netcoop_world_store.inc"', start)]
matrix = (root / "src/xrCore/_matrix.h").read_text(encoding="utf-8")
start = matrix.index("ICF SelfRef setHPB(T h, T p, T b)")
matrix_methods = matrix[start:matrix.index("IC void getXYZi(T&", start)]
spawn = (root / "src/xrGame/GameObject.cpp").read_text(encoding="utf-8")
assert "XFORM().setXYZ(E->o_Angle);" in spawn
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
#include <limits>
using u8=std::uint8_t;using u16=std::uint16_t;using u32=std::uint32_t;
template<class T>using xr_vector=std::vector<T>;
using BOOL=bool;constexpr bool TRUE=true,FALSE=false;constexpr u32 NET_PacketSizeLimit=16384;
template<class T,class P>T smart_cast(P* p){return dynamic_cast<T>(p);}
void Msg(const char*,...){}
struct Fvector {float x=0,y=0,z=0;void set(float a,float b,float c){x=a;y=b;z=c;}bool operator==(const Fvector& v)const{return x==v.x&&y==v.y&&z==v.z;}};
bool _valid(const Fvector& v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
float _sin(float v){return std::sin(v);}float _cos(float v){return std::cos(v);}float _sqrt(float v){return std::sqrt(v);}
#define IC inline
#define ICF inline
#define type_epsilon(type) std::numeric_limits<type>::epsilon()
struct Matrix {using T=float;using Tvector=Fvector;using SelfRef=Matrix&;Fvector i,j,k,c;float _14_=0,_24_=0,_34_=0,_44_=1;
 Matrix(){setXYZ(0.2f,1.570796327f,0.4f);}
''' + matrix_methods + r'''
};
bool same_rotation(const Matrix& a,const Matrix& b){
 for(auto pair:{std::pair<Fvector,Fvector>{a.i,b.i},{a.j,b.j},{a.k,b.k}})
  if(std::fabs(pair.first.x-pair.second.x)>0.00001f || std::fabs(pair.first.y-pair.second.y)>0.00001f || std::fabs(pair.first.z-pair.second.z)>0.00001f)return false;
 return true;
}
struct Flags {u8 value=0;void assign(u8 f){value=f;}void set(u8 f,bool b){value=b?u8(value|f):u8(value&~f);}};
struct NET_Packet {
 struct {u32 count=99;} B;
 u32 read=999;u8 flags=0;std::uint64_t mask=0;u16 root_bone=0;std::vector<int> bodies;std::vector<u8> prefix;
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
 std::uint64_t bones_mask=0;u16 root_bone=0;std::vector<int> bones;
 void net_Load(NET_Packet& p){
  assert(p.read==(p.has_chunk?3u+u32(p.prefix.size()):1u));if(throw_decode)throw std::runtime_error("decode fault");
  bones_mask=p.mask;root_bone=p.root_bone;bones=p.bodies;if(bad_count)bones.pop_back();p.read=p.B.count-(bad_eof?1u:0u);
 }
};
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=7,parent=55;std::string section="prop",name="original";std::vector<u8> client_data{90,91};};
struct CSE_PHSkeleton {
 virtual ~CSE_PHSkeleton()=default;
 enum:u8 {flActive=1,flSpawnCopy=2,flSavedData=4,flNotSave=8};
 Flags _flags;SPHBonesData saved_bones;u16 source_id=123;std::string startup="door";
 bool need_save()const{return !(_flags.value&flNotSave);}
};
struct CSE_ALifeObjectPhysic:CSE_Abstract,CSE_PHSkeleton {Fvector o_Position,o_Angle;};
struct CSE_ALifePHSkeletonObject:CSE_Abstract,CSE_PHSkeleton {Fvector o_Position,o_Angle;};
struct CSE_ALifeObjectBreakable:CSE_Abstract {float m_health=1.f;};
struct Object {virtual ~Object()=default;};
struct CBreakableObject:Object {
 u16 id=9;bool destroyed=false,parented=false,fail=false;int captures=0;
 u16 ID()const{return id;}bool getDestroy()const{return destroyed;}bool H_Parent()const{return parented;}
 bool netcoop_capture_saved_health(CSE_Abstract* entity){
  ++captures;auto* target=smart_cast<CSE_ALifeObjectBreakable*>(entity);
  if(fail || !target || target->ID!=id)return false;
  target->m_health=0.61f;return true;
 }
};
struct CPHSkeleton {
 std::vector<int> bodies{10,20};int save_calls=0;u8 simulated_flags=1;std::uint64_t mask=0x52;u16 root_bone=4;
 int spawn_calls=0;bool Spawn(CSE_Abstract*){++spawn_calls;return false;} // stock false means ordinary, non-copy spawn
 void SaveNetState(NET_Packet& p){++save_calls;p.flags=simulated_flags;p.mask=mask;p.root_bone=root_bone;p.bodies=bodies;p.B.count+=37+8*u32(bodies.size());}
};
struct CScriptBinderObject {
 int saves=0;bool fail=false,empty=false,oversize=false;std::vector<u8> data{11,12,13};
 void save(NET_Packet* p){++saves;if(fail)throw std::runtime_error("door binder save fault");if(oversize){for(u32 i=0;i<16360;++i)p->w_u8(0);return;}if(!empty)for(u8 b:data)p->w_u8(b);}
};
struct CScriptBinder {CScriptBinderObject* attached_binder=nullptr;CScriptBinderObject* object(){return attached_binder;}};
struct CPhysicsShellHolder {void save(NET_Packet& p){p.w_u8(42);}};
struct CPhysicObject:Object,CPHSkeleton,CScriptBinder,CPhysicsShellHolder {
 u16 id=7,simulated_count=2;bool destroyed=false,parented=false,shell=true;
 Fvector position{1,2,3};Matrix matrix;
 u16 ID()const{return id;}u16 PHGetSyncItemsNumber()const{return simulated_count;}
 bool getDestroy()const{return destroyed;}bool H_Parent()const{return parented;}
 bool PPhysicsShell()const{return shell;}
 const Fvector& Position()const{return position;}const Matrix& XFORM()const{return matrix;}
 void net_Save(NET_Packet&){throw std::runtime_error("whole object save must not run");}
 bool netcoop_capture_saved_physics(CSE_Abstract*,bool=false);
};
template<class T>void xr_delete(T*& p){delete p;p=nullptr;}
template<class T,class P>T* xr_new(P p){return new T(p);}
struct CCF_Skeleton {template<class T>explicit CCF_Skeleton(T*){}};
struct FragmentShell {bool breakable=true;bool isBreakable()const{return breakable;}};
struct FragmentHolder:Object {
 struct {CCF_Skeleton* model=nullptr;} collidable;
 bool spawn_ok=true,destroyed=false,parented=false,visible=false,enabled=false,shell=true;
 int unregistrations=0;u16 id=10,simulated_count=2;Fvector position{2,3,4};Matrix matrix;FragmentShell physics;
 virtual ~FragmentHolder(){xr_delete(collidable.model);}
 BOOL net_Spawn(CSE_Abstract*){return spawn_ok;}
 u16 ID()const{return id;}u16 PHGetSyncItemsNumber()const{return simulated_count;}
 bool getDestroy()const{return destroyed;}bool H_Parent()const{return parented;}
 FragmentShell* PPhysicsShell(){return shell?&physics:nullptr;}
 const Fvector& Position()const{return position;}const Matrix& XFORM()const{return matrix;}
 void setVisible(bool v){visible=v;}void setEnabled(bool v){enabled=v;}
 void SheduleUnregister(){++unregistrations;}
};
struct CPhysicsSkeletonObject:FragmentHolder,CPHSkeleton {
 using inherited=FragmentHolder;
 BOOL net_Spawn(CSE_Abstract*);
 bool netcoop_capture_saved_physics(CSE_Abstract*);
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
''' + capture + fragment_capture + fragment_spawn + select + r'''
int main(){
 CPhysicObject prop;CSE_ALifeObjectPhysic entity;
 entity.saved_bones.bones={99};
 assert(prop.netcoop_capture_saved_physics(&entity));
 assert(entity.saved_bones.bones==prop.bodies && entity._flags.value==5);
 Fvector expected_angles;prop.matrix.getXYZ(expected_angles);
 assert(entity.o_Position==prop.position && entity.o_Angle==expected_angles);
 Matrix spawned;spawned.setXYZ(entity.o_Angle);assert(same_rotation(spawned,prop.matrix));
 // Actual xrCore Euler routines + actual adapter, including yaw90, coupled
 // rotations, negative angles and the gimbal branch. Using getHPB here fails.
 for(Fvector xyz:{Fvector{0,0,0},Fvector{0,1.570796327f,0},Fvector{0.3f,-1.2f,0.6f},Fvector{-0.8f,2.1f,-0.5f},Fvector{1.570796327f,0.4f,0.2f}}){
  CPhysicObject rotated;CSE_ALifeObjectPhysic saved;
  rotated.matrix.setXYZ(xyz);assert(rotated.netcoop_capture_saved_physics(&saved));
  Matrix recovered;recovered.setXYZ(saved.o_Angle);assert(same_rotation(rotated.matrix,recovered));
 }
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
 const float valid_kx=prop.matrix.k.x;prop.matrix.k.x=std::numeric_limits<float>::quiet_NaN();assert(!prop.netcoop_capture_saved_physics(&entity));prop.matrix.k.x=valid_kx;
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
 // Actual traversal must include intact/damaged breakables without a dynamic
 // physics shell, skip pending deletion/attachments, and fail closed.
 CBreakableObject glass,removed_glass,attached_glass;
 removed_glass.destroyed=true;attached_glass.parented=true;
 CSE_ALifeObjectBreakable glass_entity;glass_entity.ID=9;game.entities[9]=&glass_entity;
 level.Objects.objects={&actor,&glass,&removed_glass,&attached_glass};
 assert(world_store_capture_physics_props());assert(glass.captures==1 && glass_entity.m_health==0.61f);
 assert(removed_glass.captures==0 && attached_glass.captures==0);
 game.entities.erase(9);assert(!world_store_capture_physics_props());
 game.entities[9]=&wrong;assert(!world_store_capture_physics_props());
 game.entities[9]=&glass_entity;glass.fail=true;assert(!world_store_capture_physics_props());
 // Separate stock fracture-object class: capture cannot accidentally use the
 // prop adapter, recreate its binder data, or retain an unresolved split.
 CPhysicsSkeletonObject fragment;CSE_ALifePHSkeletonObject fragment_entity;fragment_entity.ID=10;
 fragment_entity.saved_bones.bones={81};
 assert(fragment.netcoop_capture_saved_physics(&fragment_entity));
 assert(fragment_entity.saved_bones.bones==fragment.bodies && fragment_entity._flags.value==5);
 assert(fragment_entity.saved_bones.bones_mask==fragment.mask && fragment_entity.saved_bones.root_bone==4);
 assert(fragment_entity.o_Position==fragment.position);
 Matrix recovered_fragment;recovered_fragment.setXYZ(fragment_entity.o_Angle);assert(same_rotation(fragment.matrix,recovered_fragment));
 assert(fragment_entity.ID==10 && fragment_entity.parent==55 && fragment_entity.name=="original" && fragment_entity.section=="prop");
 assert(fragment_entity.source_id==123 && fragment_entity.startup=="door" && (fragment_entity.client_data==std::vector<u8>{90,91}));
 auto fragment_unchanged=[&]{assert(fragment_entity.saved_bones.bones==fragment.bodies && fragment_entity._flags.value==5);assert(fragment_entity.o_Position==fragment.position);};
 bad_count=true;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));bad_count=false;fragment_unchanged();
 bad_eof=true;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));bad_eof=false;fragment_unchanged();
 throw_decode=true;threw=false;try{fragment.netcoop_capture_saved_physics(&fragment_entity);}catch(const std::exception&){threw=true;}assert(threw);throw_decode=false;fragment_unchanged();
 fragment.simulated_flags=CSE_PHSkeleton::flSpawnCopy;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.simulated_flags=1;fragment_unchanged();
 const int fragment_calls=fragment.save_calls;
 assert(!fragment.netcoop_capture_saved_physics(nullptr));assert(!fragment.netcoop_capture_saved_physics(&wrong));assert(!fragment.netcoop_capture_saved_physics(&entity));
 fragment_entity.ID=11;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment_entity.ID=10;
 fragment.destroyed=true;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.destroyed=false;
 fragment.parented=true;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.parented=false;
 fragment.shell=false;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.shell=true;
 fragment.simulated_count=0;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.simulated_count=2044;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.simulated_count=2;
 fragment.position.x=INFINITY;assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.position.x=2;
 const float fragment_kx=fragment.matrix.k.x;fragment.matrix.k.x=std::numeric_limits<float>::quiet_NaN();assert(!fragment.netcoop_capture_saved_physics(&fragment_entity));fragment.matrix.k.x=fragment_kx;
 assert(fragment.save_calls==fragment_calls);fragment_unchanged();
 CPhysicsSkeletonObject refused;refused.spawn_ok=false;refused.collidable.model=new CCF_Skeleton(&refused);auto* old_model=refused.collidable.model;
 assert(!refused.net_Spawn(&fragment_entity));assert(refused.collidable.model==old_model && refused.spawn_calls==0 && !refused.visible && !refused.enabled && refused.unregistrations==0);
 CPhysicsSkeletonObject spawned;assert(spawned.net_Spawn(&fragment_entity));assert(spawned.spawn_calls==1 && spawned.collidable.model && spawned.visible && spawned.enabled && spawned.unregistrations==0);
 CPhysicsSkeletonObject rigid;rigid.physics.breakable=false;assert(rigid.net_Spawn(&fragment_entity));assert(rigid.unregistrations==1);
 CPhysicsSkeletonObject empty;empty.shell=false;assert(empty.net_Spawn(&fragment_entity));assert(empty.unregistrations==1);
 // Actual traversal visits fragments independently and honours temporary
 // debris's stock no-save flag. Capture failure must reject the checkpoint.
 CPhysicsSkeletonObject gone_fragment,attached_fragment,no_fragment_shell,no_fragment_bodies,excluded_fragment;
 gone_fragment.destroyed=true;attached_fragment.parented=true;no_fragment_shell.shell=false;no_fragment_bodies.simulated_count=0;excluded_fragment.id=11;
 CSE_ALifePHSkeletonObject excluded_fragment_entity;excluded_fragment_entity.ID=11;excluded_fragment_entity._flags.value=CSE_PHSkeleton::flNotSave;
 game.entities[10]=&fragment_entity;game.entities[11]=&excluded_fragment_entity;
 level.Objects.objects={&actor,&fragment,&gone_fragment,&attached_fragment,&no_fragment_shell,&no_fragment_bodies,&excluded_fragment};
 assert(world_store_capture_physics_props());assert(fragment.save_calls==fragment_calls+1);
 assert(gone_fragment.save_calls==0 && attached_fragment.save_calls==0 && no_fragment_shell.save_calls==0 && no_fragment_bodies.save_calls==0 && excluded_fragment.save_calls==0);
 game.entities.erase(10);assert(!world_store_capture_physics_props());game.entities[10]=&entity;assert(!world_store_capture_physics_props());game.entities[10]=&fragment_entity;
 fragment.simulated_flags=CSE_PHSkeleton::flNotSave;assert(world_store_capture_physics_props());assert(!fragment_entity.need_save());
 const int temporary_calls=fragment.save_calls;assert(world_store_capture_physics_props());assert(fragment.save_calls==temporary_calls); // excluded on next checkpoint
 std::cout<<"PASS: actual physics/door/fragment capture; scoped binder, strict exceptions/no deletion, atomic decode, bounds, metadata, selection, unresolved splits, no-save debris and refused spawn\n";
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
