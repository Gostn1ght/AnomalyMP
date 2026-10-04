"""Compile actual interpolation/contact code and check its physical bounds on CI."""
from pathlib import Path
import os
import subprocess
import tempfile

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run on GitHub Actions.')
root = Path(__file__).resolve().parents[1]
source = (root/'src/xrGame/PhysicsShellHolder.cpp').read_text()
begin = source.index('static float netcoop_physics_coordinate(')
end = source.index('\nvoid CPhysicsShellHolder::netcoop_physics_update()', begin)
interpolation = source[begin:end]
begin = source.index('static void netcoop_item_ground_contact(')
end = source.index('\nCPhysicsShellHolder::~', begin)
contact = source[begin:end]
fixtures = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <random>
template<class T> T _max(T a,T b){return std::max(a,b);}
template<class T> T _min(T a,T b){return std::min(a,b);}
float _abs(float v){return std::abs(v);} float _sqrt(float v){return std::sqrt(v);}
template<class T> void clamp(T& v,T a,T b){v=std::clamp(v,a,b);}
constexpr float EPS_S=0.0000001f;
struct SGameMtl {};
struct dContact {
 struct {void* g1=nullptr;void* g2=nullptr;float normal[3]={0,1,0};} geom;
 struct {int mode=0;float mu=0,mu2=0,bounce=1,bounce_vel=0,slip1=1,slip2=1;} surface;
};
void* dGeomGetBody(void* g){return g;}
constexpr int dContactSlip1=1,dContactSlip2=2,dContactApprox1=4;
'''
checks = r'''
int main(){
 assert(netcoop_physics_coordinate(3,3,100,-100,.05f,.4f)==3);
 // A free-fall interval reproduces the parabolic midpoint from endpoint velocities.
 float mid=netcoop_physics_coordinate(1,.9f,-1,-3,.05f,.5f);
 assert(std::abs(mid-.9625f)<.00001f);
 std::mt19937 gen(7731);std::uniform_real_distribution<float> pos(-20,20),vel(-200,200);
 for(int n=0;n<10000;++n){float a=pos(gen),b=pos(gen),va=vel(gen),vb=vel(gen);
   float previous=a;
   for(int i=0;i<=100;++i){float v=netcoop_physics_coordinate(a,b,va,vb,.05f,float(i)/100);
     assert(std::isfinite(v));assert(v>=std::min(a,b)-.00002f && v<=std::max(a,b)+.00002f);
     assert(b>=a ? v>=previous-.00002f : v<=previous+.00002f);previous=v;
   }
 }
 bool collide=true;dContact c;c.geom.g1=(void*)1;c.surface.mode=dContactSlip1|dContactSlip2;
 netcoop_item_ground_contact(collide,true,c,nullptr,nullptr);
 assert(c.surface.mu>=.8f && c.surface.mu2>=.8f && !(c.surface.mode&(dContactSlip1|dContactSlip2)));
 assert(c.surface.slip1==0 && c.surface.slip2==0 && c.surface.bounce<=.08f);
 dContact dynamic;dynamic.geom.g1=(void*)1;dynamic.geom.g2=(void*)2;
 netcoop_item_ground_contact(collide,true,dynamic,nullptr,nullptr);assert(dynamic.surface.mu==0);
 dContact wall;wall.geom.normal[1]=0;
 netcoop_item_ground_contact(collide,true,wall,nullptr,nullptr);assert(wall.surface.mu==0);
 puts("Actual physics: ballistic midpoint, 1M monotone samples, static-ground friction and dynamic/wall exclusions PASS");
}
'''
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    (path/'check.cpp').write_text(fixtures+interpolation+contact+checks)
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra',str(path/'check.cpp'),'-o',str(path/'check')],check=True)
    subprocess.run([str(path/'check')],check=True)
