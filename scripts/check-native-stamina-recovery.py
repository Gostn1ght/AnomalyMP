"""Actual satiety/stand/inherited condition code: owner recovery stays separate from damage."""
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
#include <cmath>
#include <cstdio>
#include <algorithm>
template<class T>void clamp(T& v,T lo,T hi){v=std::max(lo,std::min(hi,v));}
constexpr float MIN_HEALTH=0.f;
constexpr unsigned AF_GODMODE_RT=1;
struct Flags{bool rt=false;bool test(unsigned){return rt;}}psActorFlags;
namespace netcoop{bool client=true;bool pure_client(){return client;}}
bool single=true;bool IsGameTypeSingle(){return single;}
struct Object{void OnCriticalHitHealthLoss(){};void OnHitHealthLoss(float){};
 void OnCriticalWoundHealthLoss(){};void OnCriticalRadiationHealthLoss(){};}owner,other;
struct GameLevel{Object* control=&owner;Object* CurrentControlEntity(){return control;}}level;
GameLevel& Level(){return level;}
struct{float fTimeGlobal=2.f;}Device;
struct CEntityCondition{
 Object* m_object=&owner;bool server=false,m_bCanBeHarmed=true;
 bool OnServer() const{return server;}
 float health=0.8f,m_fPower=0.2f,m_fPowerMax=1.f,m_fDeltaTime=0.1f;
 float m_fPsyHealth=1,m_fEntityMorale=1,m_fRadiation=0;
 float m_fRadiationMax=1,m_fEntityMoraleMax=1,m_fPsyHealthMax=1;
 float m_fDeltaHealth=0,m_fDeltaPower=0,m_fDeltaRadiation=0,m_fDeltaPsyHealth=0;
 float m_fDeltaCircumspection=0,m_fDeltaEntityMorale=0;
 float m_fInvulnerableTime=0,m_fKillHitTreshold=0.1f,m_fLastChanceHealth=0.05f,m_fInvulnerableTimeDelta=1;
 float GetHealth(){return health;}void SetHealth(float v){health=v;}float max_health(){return 1;}
 void UpdateHealth(){}void UpdatePower(){}void UpdateRadiation(){};
 void UpdatePsyHealth(){}void UpdateEntityMorale(){};
 bool CanBeHarmed() const;
 void UpdateCondition();
};
struct CActorCondition:CEntityCondition{
 bool sleeping=false;float m_fSatiety=1,m_fSatietyChange=0,m_fSatietyCritical=0.5f;
 float m_fV_SatietyPower=0.3f,m_fV_SatietyPowerSleep=0.6f;
 float m_fV_Satiety=0,m_fV_SatietySleep=0,m_fV_SatietyHealth=0.02f,m_fV_SatietyHealthSleep=0.04f;
 float m_fStandPower=0.01f;
 bool IsSleeping(){return sleeping;}
 void UpdateSatiety();void ConditionStand(float);
 void frame(){ConditionStand(0);UpdateSatiety();CEntityCondition::UpdateCondition();}
};
'''
harm = method("src/xrGame/EntityCondition.h", "IC bool CanBeHarmed() const")
source += harm.replace("IC bool CanBeHarmed() const", "bool CEntityCondition::CanBeHarmed() const")
source += method("src/xrGame/EntityCondition.cpp", "void CEntityCondition::UpdateCondition()")
source += method("src/xrGame/ActorCondition.cpp", "void CActorCondition::UpdateSatiety()")
# The unused weight in GAMMA's real stand implementation is intentional.
source += method("src/xrGame/ActorCondition.cpp", "void CActorCondition::ConditionStand(float weight)").replace("float weight", "float")
source += r'''
bool near(float a,float b){return std::fabs(a-b)<0.00001f;}
int main(){
 CActorCondition c;assert(!c.CanBeHarmed());
 for(unsigned i=0;i<10;++i)c.frame();
 assert(near(c.m_fPower,0.49f) && near(c.health,0.8f));
 for(unsigned i=0;i<100;++i)c.frame();
 assert(near(c.m_fPower,1.f) && c.m_fDeltaPower==0 && near(c.health,0.8f));
 c.m_fPowerMax=0.7f;c.frame();assert(near(c.m_fPower,0.7f));
 CActorCondition hungry;hungry.m_fSatiety=0;hungry.frame();assert(near(hungry.m_fPower,0.199f));
 CActorCondition half;half.m_fSatiety=0.5f;half.frame();assert(near(half.m_fPower,0.214f));
 CActorCondition asleep;asleep.sleeping=true;asleep.frame();assert(near(asleep.m_fPower,0.259f));
 CActorCondition observer;observer.m_object=&other;observer.frame();
 assert(near(observer.m_fPower,0.199f) && near(observer.health,0.8f));
 level.control=nullptr;CActorCondition no_owner;no_owner.frame();assert(near(no_owner.m_fPower,0.199f));
 level.control=&owner;netcoop::client=false;
 CActorCondition freeplay;freeplay.server=true;freeplay.frame();
 assert(near(freeplay.m_fPower,0.229f) && near(freeplay.health,0.802f));
 CActorCondition protected_actor;protected_actor.server=true;protected_actor.m_bCanBeHarmed=false;
 protected_actor.frame();assert(near(protected_actor.m_fPower,0.199f) && near(protected_actor.health,0.8f));
 // Legacy multiplayer restoration remains its original unconditional path.
 single=false;CActorCondition mp;mp.frame();assert(near(mp.m_fPower,0.229f));single=true;
 netcoop::client=true;psActorFlags.rt=true;CActorCondition menu;menu.frame();
 assert(near(menu.m_fPower,0.199f) && near(menu.health,0.8f));psActorFlags.rt=false;
 CActorCondition starving;starving.m_fSatiety=0.1f;starving.server=true;netcoop::client=false;
 starving.frame();assert(starving.health<0.8f && starving.m_fPower>0.2f);
 std::puts("PASS actual stamina recovery: pure owner frames, hunger/sleep, max power, no client health regeneration, observer/menu isolation, protected freeplay and legacy MP");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "stamina.cpp"
    exe = Path(tmp) / ("stamina.exe" if os.name == "nt" else "stamina")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
