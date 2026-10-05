"""Execute actual native ground-item TTL and armed missile fuse paths in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
game = root / "src/xrGame"
def method(file, start, end):
    text = (game / file).read_text(encoding="utf-8")
    return text[text.index(start):text.index(end, text.index(start))]

methods = "\n".join([
    method("inventory_item.cpp", "bool CInventoryItem::NeedToDestroyObject() const", "ALife::_TIME_ID CInventoryItem::TimePassedAfterIndependant"),
    method("Weapon.cpp", "bool CWeapon::NeedToDestroyObject() const", "ALife::_TIME_ID CWeapon::TimePassedAfterIndependant"),
    method("Grenade.cpp", "bool CGrenade::NeedToDestroyObject() const", "ALife::_TIME_ID CGrenade::TimePassedAfterIndependant"),
    method("Missile.cpp", "void CMissile::shedule_Update(u32 dt)", "void CMissile::State("),
])
source = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <initializer_list>
using u32=std::uint32_t;
#define VERIFY(x) assert(x)
constexpr int eGameIDSingle=1,eGameIDCaptureTheArtefact=2;
constexpr u32 ITEM_REMOVE_TIME=100;
namespace netcoop {bool active=true;bool enabled(){return active;}}
struct Object {bool remote=false;bool Remote()const{return remote;}};
struct CInventoryItem {
 int mode=3;u32 age=100000;Object instance;
 int GameID()const{return mode;}
 const Object& object()const{return instance;}
 u32 TimePassedAfterIndependant()const{return age;}
 bool NeedToDestroyObject()const;
};
int g_iWeaponRemove=1;
struct CWeapon {
 int mode=3;bool remote=false,parent=false;u32 age=100000,m_dwWeaponRemoveTime=100;
 int GameID()const{return mode;}bool Remote()const{return remote;}bool H_Parent()const{return parent;}
 u32 TimePassedAfterIndependant()const{return age;}
 bool NeedToDestroyObject()const;
};
struct CGrenade {
 bool single=false,remote=false;u32 age=100000,m_dwGrenadeRemoveTime=100;
 bool IsGameTypeSingle()const{return single;}bool Remote()const{return remote;}
 u32 TimePassedAfterIndependant()const{return age;}
 bool NeedToDestroyObject()const;
};
struct FixtureLevel {u32 now=1000;u32 timeServer()const{return now;}} fixture_level;
FixtureLevel& Level(){return fixture_level;}
struct MissileBase {void shedule_Update(u32) {}};
struct CMissile:MissileBase {
 using inherited=MissileBase;
 bool parent=false,visible=true;void* m_pPhysicsShell=this;void* m_pInventory=nullptr;
 u32 m_dwDestroyTime=0xffffffff;int detonated=0;
 bool H_Parent()const{return parent;}bool getVisible()const{return visible;}
 void Destroy(){++detonated;}void shedule_Update(u32);
};
''' + methods + r'''
int main() {
 CInventoryItem item;CWeapon weapon;CGrenade grenade;
 for(int remove:{-1,0,1}) {
  g_iWeaponRemove=remove;
  for(u32 age:{0u,101u,0xffffffffu}) {
   item.age=weapon.age=grenade.age=age;
   assert(!item.NeedToDestroyObject() && !weapon.NeedToDestroyObject() && !grenade.NeedToDestroyObject());
  }
 }
 CMissile armed;armed.m_dwDestroyTime=999;armed.shedule_Update(1);
 assert(armed.detonated==1 && armed.m_dwDestroyTime==0xffffffff);
 armed.shedule_Update(1);assert(armed.detonated==1);
 CMissile future;future.m_dwDestroyTime=1001;future.shedule_Update(1);assert(future.detonated==0);
 fixture_level.now=1001;future.shedule_Update(1);assert(future.detonated==1);
 CMissile dropped;dropped.shedule_Update(1);assert(dropped.detonated==0);
 netcoop::active=false;g_iWeaponRemove=1;
 assert(item.NeedToDestroyObject() && weapon.NeedToDestroyObject() && grenade.NeedToDestroyObject());
 item.mode=eGameIDSingle;weapon.mode=eGameIDSingle;grenade.single=true;
 assert(!item.NeedToDestroyObject() && !weapon.NeedToDestroyObject() && !grenade.NeedToDestroyObject());
 item.mode=weapon.mode=3;grenade.single=false;
 item.instance.remote=weapon.remote=grenade.remote=true;
 assert(!item.NeedToDestroyObject() && !weapon.NeedToDestroyObject() && !grenade.NeedToDestroyObject());
 std::cout<<"PASS: actual native ground TTL disabled only in co-op; armed fuse still detonates once; vanilla policy retained\n";
}
'''
with TemporaryDirectory(prefix="item-lifetime-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2", str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
