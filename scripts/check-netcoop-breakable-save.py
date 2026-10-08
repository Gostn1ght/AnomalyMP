"""Exercise actual breakable capture and net_Spawn with engine API doubles."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
text = (root / 'src/xrGame/BreakableObject.cpp').read_text()
start = text.index('BOOL CBreakableObject::net_Spawn(')
spawn = text[start:text.index('void CBreakableObject::shedule_Update(', start)]
start = text.index('bool CBreakableObject::netcoop_capture_saved_health(')
capture = text[start:text.index('void CBreakableObject::net_Export(', start)]
source = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
using u16=std::uint16_t;using BOOL=bool;constexpr bool TRUE=true,FALSE=false;
template<class T,class P>T smart_cast(P* p){return dynamic_cast<T>(p);}
template<class T>void xr_delete(T*& p){delete p;p=nullptr;}
template<class T,class P>T* xr_new(P p){return new T(p);}
#define R_ASSERT(x) do{if(!(x))throw std::runtime_error("engine assertion");}while(false)
bool _valid(float v){return std::isfinite(v);}
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=7,parent=55;std::string name="glass",section="breakable_object";};
struct CSE_ALifeObjectBreakable:CSE_Abstract {float m_health=1.f;};
struct IKinematics {virtual ~IKinematics()=default;};
struct CCF_Skeleton {template<class T>explicit CCF_Skeleton(T*){}};
namespace netcoop {bool cooperative=true;bool enabled(){return cooperative;}}
struct CPhysicsShellHolder {
 struct {CCF_Skeleton* model=nullptr;} collidable;
 IKinematics visual;bool spawn_ok=true,deactivated=false,visible=false,enabled=false;
 bool destroyed=false,parented=false;u16 id=7;int token=0;int* m_pPhysicsShell=nullptr;
 virtual ~CPhysicsShellHolder(){xr_delete(collidable.model);}
 BOOL net_Spawn(CSE_Abstract*){return spawn_ok;}
 IKinematics* Visual(){return &visual;}
 void processing_deactivate(){deactivated=true;}
 void setVisible(bool v){visible=v;}void setEnabled(bool v){enabled=v;}
 bool getDestroy()const{return destroyed;}bool H_Parent()const{return parented;}
 u16 ID()const{return id;}
};
struct CBreakableObject:CPhysicsShellHolder {
 using inherited=CPhysicsShellHolder;
 float fHealth=1.f;bool bRemoved=false,unbroken=false;int break_calls=0,unbroken_calls=0;
 void CreateUnbroken(){unbroken=true;++unbroken_calls;}
 void Break(){assert(unbroken);unbroken=false;m_pPhysicsShell=&token;++break_calls;}
 BOOL net_Spawn(CSE_Abstract*);
 bool netcoop_capture_saved_health(CSE_Abstract*);
};
''' + spawn + capture + r'''
int main(){
 CSE_ALifeObjectBreakable saved;CBreakableObject live;
 live.fHealth=0.61f;assert(live.netcoop_capture_saved_health(&saved));assert(saved.m_health==0.61f);
 assert(saved.ID==7 && saved.parent==55 && saved.name=="glass" && saved.section=="breakable_object");
 auto unchanged=[&](){assert(saved.m_health==0.61f && saved.ID==7 && saved.parent==55);};
 CSE_Abstract wrong;assert(!live.netcoop_capture_saved_health(&wrong));assert(!live.netcoop_capture_saved_health(nullptr));unchanged();
 saved.ID=8;assert(!live.netcoop_capture_saved_health(&saved));saved.ID=7;unchanged();
 live.destroyed=true;assert(!live.netcoop_capture_saved_health(&saved));live.destroyed=false;unchanged();
 live.parented=true;assert(!live.netcoop_capture_saved_health(&saved));live.parented=false;unchanged();
 for(float bad:{std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}){
  live.fHealth=bad;assert(!live.netcoop_capture_saved_health(&saved));unchanged();
 }
 live.fHealth=1.f;live.m_pPhysicsShell=&live.token;assert(live.netcoop_capture_saved_health(&saved));assert(saved.m_health==0.f); // strike break without health loss
 live.m_pPhysicsShell=nullptr;live.fHealth=-1.f;assert(live.netcoop_capture_saved_health(&saved));assert(saved.m_health==0.f);
 live.fHealth=0.f;assert(live.netcoop_capture_saved_health(&saved));assert(saved.m_health==0.f);
 live.fHealth=12.5f;assert(live.netcoop_capture_saved_health(&saved));assert(saved.m_health==12.5f); // authoring health may exceed1
 CBreakableObject damaged;saved.m_health=0.61f;assert(damaged.net_Spawn(&saved));
 assert(damaged.fHealth==0.61f && damaged.unbroken && damaged.break_calls==0 && damaged.unbroken_calls==1);
 assert(damaged.collidable.model && damaged.deactivated && damaged.visible && damaged.enabled && !damaged.bRemoved);
 CBreakableObject broken;saved.m_health=0.f;assert(broken.net_Spawn(&saved));
 assert(broken.fHealth==0.f && !broken.unbroken && broken.m_pPhysicsShell && broken.break_calls==1);
 CBreakableObject negative;saved.m_health=-0.5f;assert(negative.net_Spawn(&saved));assert(negative.break_calls==1);
 CBreakableObject intact;saved.m_health=1.f;assert(intact.net_Spawn(&saved));assert(intact.unbroken && intact.break_calls==0);
 netcoop::cooperative=false;CBreakableObject freeplay;saved.m_health=0.f;assert(freeplay.net_Spawn(&saved));assert(freeplay.unbroken && freeplay.break_calls==0);
 netcoop::cooperative=true;CBreakableObject refused;refused.spawn_ok=false;assert(!refused.net_Spawn(&saved));assert(!refused.collidable.model && refused.unbroken_calls==0 && refused.break_calls==0);
 std::cout<<"PASS: actual breakable health capture and net_Spawn; partial damage, strike/zero destruction, finite/type/identity guards, metadata, failed spawn and unchanged freeplay\n";
}
'''
with TemporaryDirectory(prefix='breakable-save-') as tmp:
    cpp=Path(tmp)/'check.cpp';exe=Path(tmp)/('check.exe' if os.name=='nt' else 'check')
    cpp.write_text(source,encoding='utf-8')
    if os.name=='nt':
        command=['cl','/nologo','/std:c++17','/EHsc','/W4','/WX','/O2',str(cpp),'/Fe:'+str(exe),'/Fo:'+str(Path(tmp)/'check.obj')]
    else:
        command=['g++','-std=c++17','-Wall','-Wextra','-Werror','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)]
    subprocess.run(command,check=True,cwd=tmp)
    subprocess.run([str(exe)],check=True,cwd=tmp)
