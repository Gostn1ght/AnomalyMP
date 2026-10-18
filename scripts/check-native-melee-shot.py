"""CI-only actual melee impact, shot request dispatch and authoritative bullets."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]

def method(path, signature):
    s = (root/path).read_text(encoding='utf-8-sig')
    a = s.index(signature); b = s.index('{', a); n = 1; e = b+1
    while n:
        n += (s[e] == '{') - (s[e] == '}'); e += 1
    return s[a:e]

source = r'''
#include <cassert>
#include <cmath>
#include <vector>
#include <algorithm>
#include <string>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;
constexpr float EPS=.00001f,EPS_L=.0001f;constexpr bool FALSE=false;
constexpr u16 GE_NETCOOP_WPN_AIM=1;
template<class T>T _min(T a,T b){return std::min(a,b);}
template<class T>T _max(T a,T b){return std::max(a,b);}
void Msg(const char*,...){}
struct Fvector{float x=0,y=0,z=0;Fvector& set(const Fvector& v){*this=v;return *this;}
 float square_magnitude()const{return x*x+y*y+z*z;}float distance_to(const Fvector& p)const{return std::sqrt((x-p.x)*(x-p.x)+(y-p.y)*(y-p.y)+(z-p.z)*(z-p.z));}
 Fvector& normalize(){float n=std::sqrt(square_magnitude());x/=n;y/=n;z/=n;return *this;}};
bool _valid(const Fvector& v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
struct CWeapon;
struct CEntity{virtual ~CEntity()=default;bool local=true;Fvector pos;
 bool Local(){return local;}bool Local()const{return local;}u16 ID(){return 10;}Fvector Position(){return pos;}
 void g_fireParams(CWeapon*,Fvector& p,Fvector& d){p=pos;d={0,0,1};}};
struct Item{CWeapon* weapon=nullptr;CWeapon* cast_weapon(){return weapon;}};using PIItem=Item*;
struct CActor:CEntity{bool seated=false;Item* active=nullptr;
 bool netcoop_seated(){return seated;}CActor& inventory(){return *this;}PIItem ActiveItem(){return active;}} actor;
template<class T,class V>T smart_cast(V* p){return dynamic_cast<T>(p);}
namespace netcoop{
 bool online=true,client=false,copy=true,owns=true;CActor* victim=nullptr;
 bool enabled(){return online;}bool pure_client(){return client;}
 bool server_player_copy(CEntity* p){return !client&&copy&&p==&actor;}
 bool client_owns_hud_item(void*){return owns;}
 struct ServerVictimScope{CActor* old;explicit ServerVictimScope(CActor* p):old(victim){victim=p;}~ServerVictimScope(){victim=old;}};
}
struct {u32 dwTimeGlobal=1000;}Device;
struct motion_marks{};
struct CHudItem{void* object(){return this;}void OnMotionMark(u32,const motion_marks&){} };
struct CCartridge{
 struct{u32 buckShot=0;float impair=0,kDisp=0,kHit=0,kImpulse=0,kAP=0,fWallmarkSize=0;}param_s;
 struct{void set(int,bool){}}m_flags;u16 bullet_material_idx=0;
 enum{cfTracer,cfRicochet};
};
struct Magazine:std::vector<CCartridge>{u32 size()const{return static_cast<u32>(std::vector<CCartridge>::size());}};
struct Bullet{float power,impulse,distance,scale;bool damage;};
std::vector<Bullet> bullets;
struct BulletManager{
 void AddBullet(const Fvector&,const Fvector&,float,float power,float impulse,u16,u16,int,float distance,const CCartridge& c,float,bool damage){
  if(damage)assert(netcoop::victim==&actor||!netcoop::enabled());
  bullets.push_back({power,impulse,distance,c.param_s.kHit,damage});
 }
};
struct LevelType{::BulletManager manager;::BulletManager& BulletManager(){return manager;}} level;
LevelType& Level(){return level;}
struct NET_Packet{Fvector pos,dir;u8 kind=0;u32 remaining=25;
 u32 r_elapsed(){return remaining;}void r_vec3(Fvector& p){p=remaining==25?pos:dir;remaining-=12;}
 u8 r_u8(){--remaining;return kind;}};
struct CWeapon:CHudItem{
 bool server=true;CEntity* parent=&actor;Magazine m_magazine;int iAmmoElapsed=0;
 Fvector m_netcoop_aim_pos,m_netcoop_aim_dir;u32 m_netcoop_aim_time=0,m_netcoop_last_shot=0,m_netcoop_budget_time=1000;
 float m_netcoop_shot_budget=3,fOneShotTime=.1f,fModeShotTime=0;
 virtual ~CWeapon()=default;
 CEntity* H_Parent(){return parent;}bool OnServer(){return server;}u16 ID(){return 20;}
 std::string cNameSect(){return "wpn_knife";}
 virtual bool netcoop_fire_shot(u8,const Fvector&,const Fvector&){++gunshots;return true;}
 virtual void netcoop_shot_effect(u8){}int gunshots=0;
 bool netcoop_shot_allowed();void OnEvent(NET_Packet&,u16);
};
struct CWeaponKnife:CWeapon{
 using inherited=CHudItem;enum{eFire=1,eFire2=2};
 int m_eHitType=0,m_eHitType_1=4,m_eHitType_2=5;
 float fCurrentHit=0,fHitImpulse_cur=0,m_hit_dist=0,m_splash_radius=0,fireDistance=0;
 float m_Hit1Distance=1,m_Hit2Distance=2,m_Hit1SplashRadius=.3f,m_Hit2SplashRadius=.5f;
 Fvector m_splash_dir,m_Hit1SpashDir,m_Hit2SpashDir;
 u32 m_hits_count=0,m_perv_hits_count=0,m_Splash1HitsCount=3,m_Splash1PerVictimsHCount=2,m_Splash2HitsCount=4;
 float fWallmarkSize=.1f,m_fStartBulletSpeed=10;u16 knife_material_idx=1;
 int requests=0,sounds=0,strikes=0;u8 requested=255;
 float GetHit1Power(){return .5f;}float GetHit2Power(){return .8f;}
 float GetHit1Impulse(){return 10;}float GetHit2Impulse(){return 20;}
 bool netcoop_player_copy(){return netcoop::online&&(server||!netcoop::owns);}
 Fvector get_LastFP(){return Fvector{};}Fvector get_LastFD(){return Fvector{0,0,1};}
 bool SendHitAllowed(CEntity*){return !netcoop::pure_client();}
 void PlaySound(const char*,const Fvector&){++sounds;}
 void netcoop_send_shot(const Fvector&,const Fvector&,u8 kind){if(netcoop::online&&netcoop::client&&parent&&parent->Local()){++requests;requested=kind;}}
 // One attack may hit several targets. Each bullet must stay inside one
 // authoritative request, with no fabricated ammunition reported to peers.
 void KnifeStrike(const Fvector& p,const Fvector& d){++strikes;MakeShot(p,d,1);MakeShot(p,d,.5f);}
 bool prepare_strike(u32);void OnMotionMark(u32,const motion_marks&);
 void MakeShot(const Fvector&,const Fvector&,float=1);
 bool netcoop_fire_shot(u8,const Fvector&,const Fvector&)override;
 void netcoop_shot_effect(u8)override;
};
'''
for signature in ('bool CWeaponKnife::prepare_strike(', 'bool CWeaponKnife::netcoop_fire_shot(',
                  'void CWeaponKnife::netcoop_shot_effect(', 'void CWeaponKnife::OnMotionMark(',
                  'void CWeaponKnife::MakeShot('):
    source += method('src/xrGame/WeaponKnife.cpp', signature)+'\n'
source += method('src/xrGame/Weapon.cpp', 'bool CWeapon::netcoop_shot_allowed(')+'\n'
event = method('src/xrGame/Weapon.cpp', 'void CWeapon::OnEvent(')
source += 'void CWeapon::OnEvent(NET_Packet& P,u16 type){switch(type){\n'+event[event.index('case GE_NETCOOP_WPN_AIM:'):event.index('case GE_ADDON_CHANGE:')]+'default:break;}}\n'
source += r'''
int main(){
 CWeaponKnife knife;Item held{&knife};actor.active=&held;
 NET_Packet primary;primary.dir={0,0,1};knife.OnEvent(primary,GE_NETCOOP_WPN_AIM);
 assert(knife.strikes==1&&bullets.size()==2&&bullets.back().damage&&bullets.back().power==.5f&&bullets.back().distance==1.3f);
 assert(knife.iAmmoElapsed==0&&knife.m_magazine.empty()&&knife.requests==0&&netcoop::victim==nullptr);
 NET_Packet secondary;secondary.dir={0,0,1};secondary.kind=1;knife.OnEvent(secondary,GE_NETCOOP_WPN_AIM);
 assert(knife.strikes==2&&bullets.back().power==.8f&&bullets.back().impulse==20&&bullets.back().distance==2.5f);
 motion_marks mark;knife.OnMotionMark(CWeaponKnife::eFire,mark);assert(knife.strikes==2);
 actor.active=nullptr;assert(!knife.netcoop_fire_shot(0,{},Fvector{0,0,1})&&knife.strikes==2);actor.active=&held;
 assert(!knife.netcoop_fire_shot(2,{},Fvector{0,0,1}));
 const auto reject=[&](NET_Packet p){int before=knife.strikes;knife.OnEvent(p,GE_NETCOOP_WPN_AIM);assert(knife.strikes==before);};
 NET_Packet bad;bad.dir={0,0,1};bad.kind=2;reject(bad);
 bad.kind=0;bad.pos.x=4;reject(bad);bad.pos.x=0;bad.dir={};reject(bad);
 bad.dir={0,0,1};bad.remaining=23;reject(bad);bad.remaining=26;reject(bad);
 actor.seated=true;bad.remaining=25;reject(bad);actor.seated=false;
 knife.m_netcoop_shot_budget=0;reject(bad);Device.dwTimeGlobal+=250;knife.OnEvent(bad,GE_NETCOOP_WPN_AIM);assert(knife.strikes==3);
 // Empty guns still cannot fire; the exemption is confined to knife classes.
 CWeapon gun;NET_Packet g;g.dir={0,0,1};gun.OnEvent(g,GE_NETCOOP_WPN_AIM);assert(gun.gunshots==0);
 gun.iAmmoElapsed=1;gun.m_magazine.resize(1);g.remaining=25;gun.OnEvent(g,GE_NETCOOP_WPN_AIM);assert(gun.gunshots==1);
 netcoop::client=true;knife.server=false;knife.OnMotionMark(CWeaponKnife::eFire2,mark);
 assert(knife.requests==1&&knife.requested==1&&!bullets.back().damage&&knife.iAmmoElapsed==0&&knife.m_magazine.empty());
 int before=knife.strikes;knife.OnMotionMark(7,mark);assert(knife.strikes==before);
 netcoop::owns=false;knife.OnMotionMark(CWeaponKnife::eFire,mark);assert(knife.strikes==before&&knife.requests==1);
 assert(!knife.netcoop_fire_shot(0,{},Fvector{0,0,1}));
 netcoop::client=false;netcoop::online=false;knife.server=false;knife.OnMotionMark(CWeaponKnife::eFire,mark);
 assert(knife.strikes==before+1&&knife.iAmmoElapsed==2&&knife.m_magazine.size()==2&&bullets.back().damage);
}
'''

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='melee-shot-') as tmp:
    folder=Path(tmp);cpp=folder/'melee.cpp';exe=folder/'melee.exe';cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
print('PASS actual knife primary/secondary impacts, zero-ammo dispatch, authoritative bullet creation, active item/origin/rate/seated gates, replicas and SP')
