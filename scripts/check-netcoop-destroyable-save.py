"""Exercise actual destroyable checkpoint/spawn and portable existing-INI codec."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
text = (root / 'src/xrGame/DestroyablePhysicsObject.cpp').read_text(encoding='utf-8')
start = text.index('BOOL CDestroyablePhysicsObject::net_Spawn(')
methods = text[start:text.index('//void CDestroyablePhysicsObject::Hit', start)]
source = r'''
#include "netcoop_destroyable_state.h"
#include <cassert>
#include <iostream>
#include <vector>
using u16=std::uint16_t;using BOOL=bool;constexpr bool TRUE=true,FALSE=false;
constexpr std::size_t NET_PacketSizeLimit=16384;
template<class T,class P>T smart_cast(P* p){return dynamic_cast<T>(p);}
namespace netcoop {bool cooperative=true;bool enabled(){return cooperative;}}
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=7;};
struct CSE_ALifeObjectPhysic:CSE_Abstract {
 std::string m_ini_string,s_name="physic_destroyable_object",replacement="box",visual="box.ogf",startup_animation,fixed_bones;
 std::vector<unsigned char> client_data{1,2,3};
 const char* name_replace(){return replacement.c_str();}const char* get_visual(){return visual.c_str();}
};
struct CInifile {bool section_exist(const char*){return true;}const char* r_string(const char*,const char*){return "stock";}};
struct IKinematics {CInifile ini;bool has_ini=true;CInifile* LL_UserData(){return has_ini?&ini:nullptr;}};
struct CPhysicObject {
 bool spawn_ok=true,destroyed=false,parented=false,shell=true;u16 id=7,count=2;int spawn_calls=0,startup_calls=0;
 IKinematics visual;
 BOOL net_Spawn(CSE_Abstract*){++spawn_calls;return spawn_ok;}
 IKinematics* Visual(){return &visual;}void RunStartupAnim(CSE_Abstract*){++startup_calls;}
 bool getDestroy(){return destroyed;}bool H_Parent(){return parented;}bool PPhysicsShell(){return shell;}
 u16 ID(){return id;}u16 PHGetSyncItemsNumber(){return count;}
};
struct CPHDestroyable {int initializations=0;void Init(){++initializations;}void Load(CInifile*,const char*){}};
struct CDamageManager {void reload(const char*,CInifile*){}};
struct CHitImmunity {void LoadImmunities(const char*,CInifile*){}};
struct CPHCollisionDamageReceiver {void Init(){}};
struct CParticlesPlayer {void LoadParticles(IKinematics*){}};
constexpr int st_Effect=0,sg_SourceType=0;
struct Sound {void create(const char*,int,int){}};
struct CDestroyablePhysicsObject:CPhysicObject,CPHDestroyable,CDamageManager,CHitImmunity,CPHCollisionDamageReceiver,CParticlesPlayer {
 using inherited=CPhysicObject;float m_fHealth=1.f;Sound m_destroy_sound;std::string m_destroy_particles;
 BOOL net_Spawn(CSE_Abstract*);bool netcoop_capture_saved_health(CSE_Abstract*);
};
''' + methods + r'''
std::uint32_t bits(float f){std::uint32_t b;std::memcpy(&b,&f,sizeof(b));return b;}
int main(){
 namespace codec=netcoop_destroyable_state;
 const std::string original="[logic]\r\nactive = nil\r\n\r\n[drop_box]\nitems = grenade_rgd5,1\n; keep comments \xff";
 float value=19.f;assert(codec::read(original,value)==codec::Status::absent && value==19.f);
 assert(codec::view(nullptr).empty());
 std::string saved;assert(codec::write(original,0.6f,16383,saved));
 assert(saved.substr(0,original.size())==original && saved.size()==original.size()+codec::footer_size);
 assert(codec::read(saved,value)==codec::Status::valid && bits(value)==bits(0.6f));
 for(int n=0;n<200;++n){assert(codec::write(saved,0.3f,16383,saved));assert(saved.size()==original.size()+codec::footer_size);}
 assert(saved.substr(0,original.size())==original);
 for(std::uint32_t b : {0u,0x80000000u,0x00000001u,0x7f7fffffu,0xff7fffffu,0xbf800000u,0x41480000u}){
  float f;std::memcpy(&f,&b,sizeof(f));assert(codec::write(original,f,16383,saved));
  assert(codec::read(saved,value)==codec::Status::valid && bits(value)==b);
 }
 std::uint32_t random=77;
 for(int n=0;n<10000;++n){random=random*1664525u+1013904223u;float f;std::memcpy(&f,&random,sizeof(f));
  if(!std::isfinite(f))continue;
  assert(codec::write(original,f,16383,saved));
  assert(codec::read(saved,value)==codec::Status::valid && bits(value)==random);
 }
 assert(codec::write(original,0.6f,16383,saved));
 for(const std::string& bad : {saved+"x",saved.substr(0,saved.size()-1),saved+saved,
       std::string("[LZ_PH_DAMAGE_V1]\nx=1"),std::string("; lost-zone-damage-v1-begin"),std::string("x\0y",3),
       original+std::string(codec::begin)+"7f800000"+std::string(codec::end),
       original+std::string(codec::begin)+"7fc00000"+std::string(codec::end),
       original+std::string(codec::begin)+"gggggggg"+std::string(codec::end)}){
  value=17.f;assert(codec::read(bad,value)==codec::Status::invalid && value==17.f);
  std::string out="unchanged";assert(!codec::write(bad,0.2f,16383,out) && out=="unchanged");
 }
 std::string out="unchanged";
 assert(!codec::write(original,0.5f,original.size()+codec::footer_size-1,out) && out=="unchanged");
 assert(codec::write(original,0.5f,original.size()+codec::footer_size,out));
 for(float bad:{std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}){
  out="unchanged";assert(!codec::write(original,bad,16383,out) && out=="unchanged");
 }
 CSE_ALifeObjectPhysic entity;entity.m_ini_string=original;CDestroyablePhysicsObject live;
 live.m_fHealth=0.6f;assert(live.netcoop_capture_saved_health(&entity));
 const auto captured=entity.m_ini_string;const auto client=entity.client_data;
 assert(codec::read(captured,value)==codec::Status::valid && bits(value)==bits(0.6f));
 auto unchanged=[&]{assert(entity.m_ini_string==captured && entity.client_data==client && entity.ID==7);};
 CSE_Abstract wrong;assert(!live.netcoop_capture_saved_health(&wrong));assert(!live.netcoop_capture_saved_health(nullptr));unchanged();
 entity.ID=8;assert(!live.netcoop_capture_saved_health(&entity));entity.ID=7;unchanged();
 live.destroyed=true;assert(!live.netcoop_capture_saved_health(&entity));live.destroyed=false;unchanged();
 live.parented=true;assert(!live.netcoop_capture_saved_health(&entity));live.parented=false;unchanged();
 live.shell=false;assert(!live.netcoop_capture_saved_health(&entity));live.shell=true;unchanged();
 live.count=0;assert(!live.netcoop_capture_saved_health(&entity));live.count=65535;assert(!live.netcoop_capture_saved_health(&entity));live.count=2;unchanged();
 live.m_fHealth=INFINITY;assert(!live.netcoop_capture_saved_health(&entity));live.m_fHealth=0.6f;unchanged();
 entity.client_data.resize(16380);assert(!live.netcoop_capture_saved_health(&entity));entity.client_data=client;unchanged();
 entity.fixed_bones.assign(16380,'x');assert(!live.netcoop_capture_saved_health(&entity));entity.fixed_bones.clear();unchanged();
 entity.m_ini_string="[lz_ph_damage_v1]";assert(!live.netcoop_capture_saved_health(&entity));assert(entity.m_ini_string=="[lz_ph_damage_v1]");entity.m_ini_string=captured;
 CDestroyablePhysicsObject restored;assert(restored.net_Spawn(&entity));
 assert(bits(restored.m_fHealth)==bits(0.6f) && restored.spawn_calls==1 && restored.initializations==1 && restored.startup_calls==1);
 CDestroyablePhysicsObject legacy;entity.m_ini_string=original;legacy.m_fHealth=0.2f;assert(legacy.net_Spawn(&entity));assert(legacy.m_fHealth==1.f);
 CDestroyablePhysicsObject refused;entity.m_ini_string=captured;refused.spawn_ok=false;assert(!refused.net_Spawn(&entity));assert(refused.m_fHealth==1.f && refused.initializations==0 && refused.startup_calls==0);
 CDestroyablePhysicsObject invalid;entity.m_ini_string="[LZ_PH_DAMAGE_V1]";assert(!invalid.net_Spawn(&entity));assert(invalid.spawn_calls==0 && invalid.initializations==0);
 assert(!invalid.net_Spawn(&wrong) && !invalid.net_Spawn(nullptr) && invalid.spawn_calls==0);
 netcoop::cooperative=false;CDestroyablePhysicsObject freeplay;assert(freeplay.net_Spawn(&entity));assert(freeplay.m_fHealth==1.f);
 netcoop::cooperative=true;entity.m_ini_string=captured;CDestroyablePhysicsObject no_userdata;no_userdata.visual.has_ini=false;assert(no_userdata.net_Spawn(&entity));assert(bits(no_userdata.m_fHealth)==bits(0.6f));
 std::cout<<"PASS: actual destroyable capture/spawn, binary32 portability, legacy/freeplay, exact INI prefix and binder retention, bounded idempotence, malformed/finite/type/identity/packet guards\n";
}
'''
with TemporaryDirectory(prefix='destroyable-save-') as tmp:
    cpp=Path(tmp)/'check.cpp';exe=Path(tmp)/('check.exe' if os.name=='nt' else 'check')
    cpp.write_text(source,encoding='utf-8')
    if os.name=='nt':
        command=['cl','/nologo','/std:c++17','/EHsc','/W4','/WX','/O2','/I'+str(root/'src/xrGame'),str(cpp),'/Fe:'+str(exe),'/Fo:'+str(Path(tmp)/'check.obj')]
    else:
        command=['g++','-std=c++17','-Wall','-Wextra','-Werror','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'src/xrGame'),str(cpp),'-o',str(exe)]
    subprocess.run(command,check=True,cwd=tmp)
    subprocess.run([str(exe)],check=True,cwd=tmp)
