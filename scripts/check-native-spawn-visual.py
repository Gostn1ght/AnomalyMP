"""Actual spawn visual resolver: map boxes without an override use their section."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/GameObject.cpp").read_text(encoding="latin-1")
start = text.index("LPCSTR CGameObject::visual_name(CSE_Abstract* server_entity)")
method = text[start:text.index("\nbool CGameObject::animation_movement_controlled", start)]
source = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
using LPCSTR=const char*;
struct CSE_Abstract { virtual ~CSE_Abstract()=default; };
struct CSE_Visual:CSE_Abstract { LPCSTR name=nullptr; LPCSTR get_visual() const{return name;} };
template<class T>T smart_cast(CSE_Abstract* obj){return dynamic_cast<T>(obj);}
#define VERIFY assert
struct Settings {
 bool has=true; unsigned reads=0;
 bool line_exist(LPCSTR section,LPCSTR field) {assert(!std::strcmp(section,"inventory_box")); assert(!std::strcmp(field,"visual")); return has;}
 LPCSTR r_string(LPCSTR,LPCSTR) {++reads; return "equipment_box_01_case.ogf";}
}settings;
Settings* pSettings=&settings;
struct CGameObject {LPCSTR cNameSect(){return "inventory_box";} LPCSTR visual_name(CSE_Abstract*);};
''' + method + r'''
int main(){
 CGameObject object; CSE_Visual spawn;
 assert(!std::strcmp(object.visual_name(&spawn),"equipment_box_01_case.ogf"));
 spawn.name=""; assert(!std::strcmp(object.visual_name(&spawn),"equipment_box_01_case.ogf"));
 assert(settings.reads==2);
 spawn.name="explicit.ogf"; assert(object.visual_name(&spawn)==spawn.name);
 spawn.name="missing.ogf"; assert(object.visual_name(&spawn)==spawn.name);
 assert(settings.reads==2);
 settings.has=false; spawn.name=""; assert(object.visual_name(&spawn)==spawn.name);
 spawn.name=nullptr; assert(object.visual_name(&spawn)==nullptr);
 std::puts("PASS actual spawn visual resolver: empty map overrides use defaults; explicit visuals and absent defaults preserved");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "visual.cpp"
    exe = Path(tmp) / ("visual.exe" if os.name == "nt" else "visual")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
