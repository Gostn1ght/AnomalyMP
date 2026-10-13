"""CI-only: real reject-path resolver, including a client with no patrols."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/level_changer.cpp").read_text(encoding="utf-8-sig")
start = text.index("bool CLevelChanger::get_reject_pos(")
end = text.index("bool CLevelChanger::feel_touch_contact", start)
method = text[start:end]
source = r'''
#include <cassert>
#include <cmath>
#include <string>
using LPCSTR=const char*;
struct Fvector{
 float x=0.f,y=0.f,z=0.f;
 void set(float a,float b,float c){x=a;y=b;z=c;}
 void sub(const Fvector& a,const Fvector& b){set(a.x-b.x,a.y-b.y,a.z-b.z);}
 void getHP(float& h,float& p){h=std::atan2(-x,z);p=std::atan2(y,std::sqrt(x*x+z*z));}
};
static bool client=true,configured=true,has_path=true;
static unsigned points=2,registry_reads=0,messages=0;
namespace netcoop{static bool pure_client(){return client;}}
static void Msg(LPCSTR,LPCSTR){++messages;}
struct CInifile{
 bool section_exist(LPCSTR name){assert(std::string(name)=="pt_move_if_reject");return configured;}
 LPCSTR r_string(LPCSTR,LPCSTR){return "reject_path";}
};
struct CPatrolPoint{Fvector value;const Fvector& position()const{return value;}};
struct Vertex{CPatrolPoint point;const CPatrolPoint& data()const{return point;}};
struct CPatrolPath{
 Vertex vertices[2];
 const Vertex* vertex(unsigned index)const{return index<points?&vertices[index]:nullptr;}
} test_path;
struct Registry{
 const CPatrolPath* path(LPCSTR name,bool no_assert){
  ++registry_reads;assert(!client && no_assert && std::string(name)=="reject_path");
  return has_path?&test_path:nullptr;
 }
} registry;
struct AI{Registry& patrol_paths(){return registry;}} test_ai;
static AI& ai(){return test_ai;}
struct CLevelChanger{CInifile* m_ini_file=nullptr;bool get_reject_pos(Fvector&,Fvector&);};
''' + method + r'''
int main(){
 CInifile config;CLevelChanger changer;changer.m_ini_file=&config;
 Fvector position,rotation;position.set(9,9,9);rotation.set(9,9,9);
 assert(!changer.get_reject_pos(position,rotation));
 assert(registry_reads==0 && position.x==0 && position.y==0 && position.z==0 && rotation.y==0);
 client=false;has_path=false;
 assert(!changer.get_reject_pos(position,rotation) && messages==1);
 has_path=true;points=0;assert(!changer.get_reject_pos(position,rotation));
 points=1;assert(!changer.get_reject_pos(position,rotation));
 points=2;test_path.vertices[0].point.value.set(2,3,4);test_path.vertices[1].point.value.set(2,3,5);
 assert(changer.get_reject_pos(position,rotation));
 assert(position.x==2 && position.y==3 && position.z==4 && rotation.y==0 && rotation.x==0);
 configured=false;assert(!changer.get_reject_pos(position,rotation));
 changer.m_ini_file=nullptr;assert(!changer.get_reject_pos(position,rotation));
}
'''

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native fixture compiles only in GitHub Actions; no local compiler invocation.")
with TemporaryDirectory(prefix="level-changer-reject-") as temporary:
    folder = Path(temporary)
    cpp = folder / "reject.cpp"
    exe = folder / ("reject.exe" if os.name == "nt" else "reject")
    cpp.write_text(source, encoding="utf-8")
    args = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:"+str(exe)]
            if os.name == "nt" else
            ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(args, cwd=folder, check=True)
    subprocess.run([str(exe)], cwd=folder, check=True)
print("PASS actual reject paths: multiplayer needs no patrols; missing/short paths safe; valid single-player path preserved")
