"""CI-only actual blast direction and bullet trajectory searches, float stalls."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def method(path, signature):
    text = (ROOT/path).read_text(encoding='utf-8')
    start = text.index(signature)
    brace = text.index('{', start)
    depth, end = 1, brace+1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


source = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <string>
#include <initializer_list>
using u32=uint32_t;
const float EPS_S=1e-7f,EPS_L=1e-3f,air_resistance_epsilon=0.01f;
float _sqrt(float v){return std::sqrt(v);}float _sqr(float v){return v*v;}float _abs(float v){return std::fabs(v);}
template<class T>T _min(T a,T b){return std::min(a,b);}template<class T>T _max(T a,T b){return std::max(a,b);}
bool _valid(float v){return std::isfinite(v);}
bool fis_zero(float a,float epsilon=1e-6f){return _abs(a)<epsilon;}
bool fsimilar(float a,float b){return fis_zero(a-b);}
void clamp(float& v,float low,float high){v=_max(low,_min(v,high));}
std::string make_string(const char*,...){return {};}
#define VERIFY(x) assert(x)
#define VERIFY2(x,text) do{(void)(text);assert(x);}while(false)
static unsigned operations=0;
struct Fvector{
 float x=0,y=0,z=0;
 Fvector& set(float a,float b,float c){x=a;y=b;z=c;return *this;}
 Fvector& sub(const Fvector&a,const Fvector&b){return set(a.x-b.x,a.y-b.y,a.z-b.z);}
 Fvector& mul(float v){x*=v;y*=v;z*=v;return *this;}
 Fvector& mad(const Fvector&a,float v){x+=a.x*v;y+=a.y*v;z+=a.z*v;return *this;}
 Fvector& mad(const Fvector&a,const Fvector&b,float v){*this=a;return mad(b,v);}
 float square_magnitude()const{return x*x+y*y+z*z;}
 float magnitude()const{++operations;return _sqrt(square_magnitude());}
 float dotproduct(const Fvector& b)const{return x*b.x+y*b.y+z*b.z;}
 float distance_to(const Fvector& b)const{return Fvector().sub(*this,b).magnitude();}
 Fvector& normalize(){return mul(1.f/magnitude());}
 Fvector& normalize_safe(){const float n=square_magnitude();return n>std::numeric_limits<float>::min()?mul(_sqrt(1.f/n)):*this;}
};
bool _valid(const Fvector& v){return _valid(v.x)&&_valid(v.y)&&_valid(v.z);}
struct SBullet{Fvector start_position,start_velocity{100,10,0};float max_dist=10000,fly_dist=0,speed=100;};
'''
source += method('src/xrGame/Explosive.cpp', 'static Fvector explosive_hit_direction(')
for signature in ('static Fvector parabolic_velocity(', 'static Fvector parabolic_position(',
                  'static Fvector trajectory_position(', 'inline static float trajectory_max_error_time(',
                  'static float trajectory_pick_error(', 'static float trajectory_select_pick_gravity(',
                  'static float trajectory_select_pick_parabolic(', 'static bool trajectory_select_pick_ranges(',
                  'static float trajectory_select_pick_time('):
    source += '\n'+method('src/xrGame/Level_Bullet_Manager.cpp', signature)
source += r'''
int main(){
 const Fvector origin{};
 for(float x:{-10.f,0.f,10.f})for(float y:{-10.f,-1.f,0.f,1.f,10.f})
 for(float z:{-10.f,0.f,10.f})for(float lift:{0.f,1.f,2.f,10.f}){
  Fvector direction=explosive_hit_direction(origin,Fvector{x,y,z},lift);
  assert(_valid(direction)&&std::fabs(direction.magnitude()-1.f)<1e-5f);
 }
 const float nan=std::numeric_limits<float>::quiet_NaN(),inf=std::numeric_limits<float>::infinity();
 for(Fvector target:{Fvector{nan,0,0},Fvector{inf,0,0},Fvector{1e30f,0,0}}){
  Fvector direction=explosive_hit_direction(origin,target,2);
  assert(_valid(direction)&&direction.y==1);
 }
 assert(_valid(explosive_hit_direction(origin,Fvector{0,-1,0},1)));
 assert(_valid(explosive_hit_direction(origin,Fvector{1,0,0},nan)));
 // Old sqrt expression is NaN for a target ten metres below a blast.
 assert(!std::isfinite(std::sqrt(4.f+1.f+4.f*(-10.f))));
 SBullet bullet;const Fvector gravity{0,-9.81f,0};
 for(float start:{0.f,1.f,128.f,1024.f})for(float duration:{0.001f,0.033f,1.f}){
  const float high=start+duration;operations=0;
  const float result=trajectory_select_pick_time(bullet,start,high,gravity,0.f);
  assert(std::isfinite(result)&&result>=start&&result<=high&&operations<2000);
 }
 // Adjacent float endpoints cannot converge under an absolute epsilon.
 float low=1024.f,high=std::nextafter(low,inf);
 assert(!fsimilar(low,high) && ((low+high)*.5f==low || (low+high)*.5f==high));
 operations=0;bullet.max_dist=0.001f;
 const float bounded=trajectory_select_pick_parabolic(bullet,low,high,gravity,0.f);
 assert(bounded==low && operations<20);
 operations=0;bullet.max_dist=10000;
 const float precise=trajectory_select_pick_time(bullet,low,high,gravity,0.f);
 assert(precise>=low&&precise<=high&&operations<100);
 // Normal 30 Hz flight keeps the entire interval and its existing trajectory.
 const float end=trajectory_select_pick_time(bullet,0.f,1.f/30.f,gravity,0.01f);
 assert(std::fabs(end-1.f/30.f)<1e-6f);
 std::puts("PASS actual blast unit directions, invalid/cancelled vectors, real ballistic searches at normal and adjacent-float flight times");
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='blast-ballistics-') as temporary:
    folder = Path(temporary)
    cpp, exe = folder/'blast.cpp', folder/('blast.exe' if os.name == 'nt' else 'blast')
    cpp.write_text(source, encoding='utf-8')
    command = (['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name == 'nt' else
               ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
