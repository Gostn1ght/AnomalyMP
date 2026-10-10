"""Actual weapon dispatch methods with engine boundaries mocked; GHA only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os, subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
def method(path,signature):
    text=(root/path).read_text(encoding='utf-8');start=text.index(signature);brace=text.index('{',start);depth=1;end=brace+1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
source=r'''
#include <cassert>
#include <vector>
#include <cstdio>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;
struct Fvector{void set(const Fvector&){}};
struct Cartridge{struct {float impair=1;}param_s;};
struct Parent{u16 ID(){return 42;}}parent;
class CWeapon{
public:
 std::vector<Cartridge>m_magazine;int iAmmoElapsed=0;Cartridge m_lastCartridge;
 struct{struct{float condition_shot_dec=1;}dummy;}unused;
 struct{float condition_shot_dec=1;}cur_silencer_koef;
 unsigned sounds=0,bullets=0,launches=0;float condition=1;
 virtual ~CWeapon()=default;
 void OnShot(){++sounds;}void FireTrace(const Fvector&,const Fvector&){++bullets;netcoop_consume_projectile();}
 float GetWeaponDeterioration(){return 0.1f;}void ChangeCondition(float change){condition+=change;}
 virtual bool netcoop_fire_shot(u8,const Fvector&,const Fvector&);
 virtual void netcoop_shot_effect(u8);void netcoop_consume_projectile();
};
#define VERIFY(x) assert(x)
struct CRocketLauncher{static unsigned spawned;void SpawnRocket(int,void*){++spawned;}};unsigned CRocketLauncher::spawned=0;
class CWeaponRPG7:public CWeapon,public CRocketLauncher{
public:
 bool m_netcoop_rocket_spawning=false,m_netcoop_launch_pending=false,ready=true;
 u16 m_netcoop_launch_owner=0;Fvector m_netcoop_launch_pos,m_netcoop_launch_dir;int m_sRocketSection=0;
 Parent* H_Parent(){return &parent;}unsigned getRocketCount(){return ready?1:0;}
 bool netcoop_launch_rocket(const Fvector&,const Fvector&){++launches;return ready;}
 void UpdateMissileVisibility(){}
 bool netcoop_fire_shot(u8,const Fvector&,const Fvector&)override;void netcoop_shot_effect(u8)override;
};
class CWeaponMagazinedWGrenade:public CWeapon{
 using inherited=CWeapon;
public:
 bool m_bGrenadeMode=false,ready=true;unsigned getRocketCount(){return ready?1:0;}
 void LaunchGrenade(){++launches;netcoop_consume_projectile();}
 bool netcoop_fire_shot(u8,const Fvector&,const Fvector&)override;void netcoop_shot_effect(u8)override;
};
'''
for path,signatures in (
 ('src/xrGame/WeaponFire.cpp',('bool CWeapon::netcoop_fire_shot(','void CWeapon::netcoop_shot_effect(','void CWeapon::netcoop_consume_projectile(')),
 ('src/xrGame/WeaponRPG7.cpp',('bool CWeaponRPG7::netcoop_fire_shot(','void CWeaponRPG7::netcoop_shot_effect(')),
 ('src/xrGame/WeaponMagazinedWGrenade.cpp',('bool CWeaponMagazinedWGrenade::netcoop_fire_shot(','void CWeaponMagazinedWGrenade::netcoop_shot_effect('))):
    source+='\n'+'\n'.join(method(path,s)for s in signatures)
source+=r'''
int main(){
 Fvector pos,dir;CWeapon rifle;rifle.iAmmoElapsed=1;rifle.m_magazine.resize(1);
 assert(!rifle.netcoop_fire_shot(1,pos,dir)&&rifle.sounds==0&&rifle.iAmmoElapsed==1);
 assert(rifle.netcoop_fire_shot(0,pos,dir)&&rifle.bullets==1&&rifle.sounds==1&&rifle.iAmmoElapsed==0);
 CWeaponRPG7 rpg;rpg.iAmmoElapsed=1;rpg.m_magazine.resize(1);
 assert(!rpg.netcoop_fire_shot(0,pos,dir)&&rpg.iAmmoElapsed==1);
 assert(rpg.netcoop_fire_shot(1,pos,dir)&&rpg.launches==1&&rpg.bullets==0&&rpg.sounds==1&&rpg.iAmmoElapsed==0);
 assert(!rpg.netcoop_fire_shot(1,pos,dir)&&rpg.launches==1);
 CWeaponRPG7 fresh;fresh.ready=false;fresh.iAmmoElapsed=1;fresh.m_magazine.resize(1);
 assert(fresh.netcoop_fire_shot(1,pos,dir)&&fresh.m_netcoop_launch_pending&&CRocketLauncher::spawned==1);
 assert(fresh.iAmmoElapsed==0&&!fresh.netcoop_fire_shot(1,pos,dir)&&CRocketLauncher::spawned==1);
 CWeaponMagazinedWGrenade gl;gl.iAmmoElapsed=1;gl.m_magazine.resize(1);
 assert(!gl.netcoop_fire_shot(2,pos,dir)&&gl.iAmmoElapsed==1);
 gl.m_bGrenadeMode=true;assert(!gl.netcoop_fire_shot(0,pos,dir));
 assert(gl.netcoop_fire_shot(2,pos,dir)&&gl.bullets==0&&gl.launches==1&&gl.sounds==1&&gl.iAmmoElapsed==0);
 gl.netcoop_shot_effect(2);assert(gl.sounds==1);
 std::puts("PASS actual weapon dispatch: projectile class/mode validation, no hitscan or duplicate launch, one cartridge, asynchronous RPG reservation, single grenade effects");
}
'''
with TemporaryDirectory() as tmp:
 cpp=Path(tmp)/'weapon.cpp';exe=Path(tmp)/('weapon.exe' if os.name=='nt' else 'weapon');cpp.write_text(source)
 command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
          ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
 subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)

