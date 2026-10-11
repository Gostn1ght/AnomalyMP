"""Actual ammo imports preserve owner prediction and safely update observers (CI only)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]


def method(path, signature):
    text = (root / path).read_text(encoding="utf-8")
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


source = r'''
#include <cassert>
#include <cstdio>
#include <vector>
#include <algorithm>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;
template<class T>T _min(T a,T b){return std::min(a,b);}
struct Object{};
namespace netcoop{bool owned=false;bool client_owns_hud_item(const Object*){return owned;}}
struct NET_Packet{
 std::vector<u8> bytes;u32 pos=0;
 u32 r_elapsed(){return u32(bytes.size())-pos;}
 u8 r_u8(){assert(r_elapsed());return bytes[pos++];}
 void r_u16(u16& value){value=r_u8();value=u16(value|(u16(r_u8())<<8));}
};
struct Base:Object{static unsigned imports;void net_Import(NET_Packet&){++imports;}};
unsigned Base::imports=0;
struct CWeaponAmmo:Base{
 using inherited=Base;u16 m_boxCurr=7,m_boxSize=30;void net_Import(NET_Packet&);
};
struct CHudItem:Base{Object& object(){return *this;}};
struct Section{const char* c_str(){return "ammo";}};
struct CCartridge{
 u8 m_LocalAmmoType=0;unsigned loaded=0;
 void Load(const char*,u8 type,float){m_LocalAmmoType=type;++loaded;}
};
struct CWeaponShotgun:CHudItem{
 using inherited=Base;std::vector<Section>m_ammoTypes{Section{},Section{}};
 std::vector<CCartridge>m_magazine{CCartridge{},CCartridge{}};float m_APk=1;
 void net_Import(NET_Packet&);
};
'''
source += method("src/xrGame/WeaponAmmo.cpp", "void CWeaponAmmo::net_Import(")
source += method("src/xrGame/WeaponShotgun.cpp", "void CWeaponShotgun::net_Import(")
source += r'''
int main(){
 CWeaponAmmo box;netcoop::owned=true;
 for(unsigned shot=0;shot<7;++shot){
  --box.m_boxCurr;NET_Packet late{{7,0}};box.net_Import(late);
  assert(box.m_boxCurr==6-shot && late.pos==2);
 }
 netcoop::owned=false;NET_Packet remote{{20,0}};box.net_Import(remote);assert(box.m_boxCurr==20);
 NET_Packet invalid_box{{255,255}};box.net_Import(invalid_box);assert(box.m_boxCurr==30);
 CWeaponShotgun gun;gun.m_magazine[0].m_LocalAmmoType=1;netcoop::owned=true;
 NET_Packet late_types{{2,0,1,77}};gun.net_Import(late_types);
 assert(gun.m_magazine[0].m_LocalAmmoType==1 && gun.m_magazine[1].m_LocalAmmoType==0);
 assert(gun.m_magazine[0].loaded==0 && late_types.pos==3 && late_types.r_u8()==77);
 netcoop::owned=false;NET_Packet observed{{2,0,1}};gun.net_Import(observed);
 assert(gun.m_magazine[0].m_LocalAmmoType==0 && gun.m_magazine[1].m_LocalAmmoType==1);
 NET_Packet bad_type{{2,255,0}};gun.net_Import(bad_type);
 assert(gun.m_magazine[0].m_LocalAmmoType==0 && gun.m_magazine[1].m_LocalAmmoType==0);
 NET_Packet too_many{{4,1,0,255,255}};gun.net_Import(too_many);assert(too_many.pos==5);
 auto before=gun.m_magazine[0].loaded;NET_Packet short_types{{2,0}};gun.net_Import(short_types);
 assert(short_types.pos==1 && gun.m_magazine[0].loaded==before);
 NET_Packet empty;gun.net_Import(empty);assert(empty.pos==0);
 gun.m_ammoTypes.clear();NET_Packet no_types{{2,0,255}};gun.net_Import(no_types);
 assert(no_types.pos==3 && gun.m_magazine[0].loaded==before);
 assert(Base::imports==16);
 std::puts("PASS actual ammo imports: delayed boxes, owner mixed cartridges, observer/SP updates, bounded counts/types, short packets and complete cursor consumption");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "ammo.cpp"
    exe = Path(tmp) / ("ammo.exe" if os.name == "nt" else "ammo")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
