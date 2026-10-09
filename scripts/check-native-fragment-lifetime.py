"""Actual stock skeleton autoremove/update with multiplayer prop persistence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/PHSkeleton.cpp').read_text(encoding='latin-1')
update=text[text.index('void CPHSkeleton::Update('):text.index('void CPHSkeleton::SaveNetState(')]
remove=text[text.index('void CPHSkeleton::SetAutoRemove('):text.index('static bool removable;')]
source=r'''
#include <cassert>
#include <cstdint>
#include <cmath>
#include <cstdio>
#include <vector>
#include <initializer_list>
using u32=uint32_t;
float phTimefactor=1.f;int iFloor(float v){return int(std::floor(v));}
struct{u32 dwTimeGlobal=100;}Device;
struct CPhysicsShell{bool fractured=false;bool isFractured(){return fractured;}};
struct CPhysicsShellHolder{virtual ~CPhysicsShellHolder()=default;
 CPhysicsShell shell;unsigned destroys=0,registrations=0;bool local=true;
 CPhysicsShell* PPhysicsShell(){return &shell;}bool Local(){return local;}
 void DestroyObject(){++destroys;}void SheduleRegister(){++registrations;}
};
struct CEntityAlive:CPhysicsShellHolder{};
template<class T>T smart_cast(CPhysicsShellHolder* o){return dynamic_cast<T>(o);}
namespace netcoop{bool fixture_active=false;bool enabled(){return fixture_active;}}
struct CPHSkeleton{
 CPhysicsShellHolder* holder=nullptr;bool b_removing=false;u32 m_remove_time=0;
 std::vector<int> m_unsplited_shels;unsigned no_save=0,splits=0;
 CPhysicsShellHolder* PPhysicsShellHolder(){return holder;}
 void PHSplit(){++splits;}void SetNotNeedSave(){++no_save;}
 void SetAutoRemove(u32);void Update(u32);
};
'''+remove+update+r'''
int main(){
 for(bool multiplayer:{false,true}){
  netcoop::fixture_active=multiplayer;
  CPhysicsShellHolder prop;CPHSkeleton parts;parts.holder=&prop;
  Device.dwTimeGlobal=100;parts.SetAutoRemove(5000);
  assert(parts.b_removing==!multiplayer&&parts.no_save==unsigned(!multiplayer)&&prop.registrations==unsigned(!multiplayer));
  Device.dwTimeGlobal=10000;parts.Update(50);assert(prop.destroys==unsigned(!multiplayer));
  Device.dwTimeGlobal=20000;parts.Update(50);assert(prop.destroys==unsigned(!multiplayer));
  prop.shell.fractured=true;parts.Update(50);assert(parts.splits==1);
  CEntityAlive corpse;CPHSkeleton body;body.holder=&corpse;
  Device.dwTimeGlobal=100;body.SetAutoRemove(5000);assert(body.b_removing&&body.no_save==1&&corpse.registrations==1);
  Device.dwTimeGlobal=10000;body.m_unsplited_shels={1};body.Update(50);assert(corpse.destroys==0&&body.b_removing);
  body.m_unsplited_shels.clear();body.Update(50);assert(corpse.destroys==1&&!body.b_removing);
 }
 std::puts("PASS actual SetAutoRemove/Update: MP props/fragments remain savable and do not vanish on model timers; fractures continue; stock SP removal and corpse branch preserved.");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'lifetime.cpp';exe=Path(tmp)/('lifetime.exe' if os.name=='nt' else 'lifetime')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
