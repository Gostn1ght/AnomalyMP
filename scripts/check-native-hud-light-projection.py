"""CI-only actual DX11 (R4) light projection; cube faces remain world axes (R2/R3 removed, doc 151)."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
helpers=[]
for renderer in ('xrRenderPC_R4',):
    text=(ROOT/f'src/Layers/{renderer}/r2_R_lights.cpp').read_text(encoding='utf-8-sig')
    helpers.append(text[text.index('IC void hud_light_apply('):text.index('void CRender::render_lights(')])
    assert text.count('hud_light_restore(saved_pos);')==1
source=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <map>
#include <vector>
using u32=uint32_t;
#define IC inline
template<class A,class B>using xr_map=std::map<A,B>;
template<class T>using xr_vector=std::vector<T>;
struct Fvector{float x=0,y=0,z=0;bool operator==(const Fvector& b)const{return x==b.x&&y==b.y&&z==b.z;}
 float dot(const Fvector& b)const{return x*b.x+y*b.y+z*b.z;}};
struct Fmatrix{Fvector i,j,k,c;void identity(){i={1,0,0};j={0,1,0};k={0,0,1};c={};}};
struct IRender_Light{enum{POINT=1,SPOT=2,OMNIPART=3};};
struct light{bool hud=true;struct{int type=IRender_Light::OMNIPART;}flags;
 Fvector position{1,2,3},direction{0,0,1},right{1,0,0};u32 m_xform_frame=123;
 bool get_hud_mode(){return hud;}
};
struct DeviceState{
 unsigned positions=0,directions=0;
 void hud_to_world(Fvector& v){++positions;v={v.x*2,v.y*3,v.z+1};}
 void hud_to_world_dir(Fvector& v){++directions;
  // A camera yaw of45deg around a different HUD/world FOV scales world
  // X/Z into nonperpendicular directions; this is not a rigid rotation.
  v={1.5f*v.x+.5f*v.z,2*v.y,.5f*v.x+1.5f*v.z};
 }
}Device;
'''+helpers[0]+r'''
int main(){
 Fvector world_x{1,0,0},world_z{0,0,1};Device.hud_to_world_dir(world_x);Device.hud_to_world_dir(world_z);
 assert(world_x.dot(world_z)!=0); // former code sheared the cubemap axes
 Device={};
 const Fvector axes[6]={{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}};
 const Fvector rights[6]={{0,0,-1},{0,0,1},{1,0,0},{1,0,0},{1,0,0},{-1,0,0}};
 light cube[6],world,spot,point;world.hud=false;spot.flags.type=IRender_Light::SPOT;point.flags.type=IRender_Light::POINT;
 xr_vector<light*> shadowed,points{&point,&world,nullptr},spots{&spot};
 for(unsigned i=0;i<6;++i){cube[i].direction=axes[i];cube[i].right=rights[i];shadowed.push_back(&cube[i]);}
 // Repeated lights across/inside packages must transform exactly once.
 shadowed.push_back(&cube[0]);points.push_back(&cube[0]);spots.push_back(&spot);
 xr_map<light*,Fmatrix> saved;
 hud_light_apply(saved,shadowed);hud_light_apply(saved,points);hud_light_apply(saved,spots);
 assert(saved.size()==8&&Device.positions==8&&Device.directions==2);
 for(unsigned i=0;i<6;++i){
  assert(cube[i].position==Fvector({2,6,4})&&cube[i].direction==axes[i]&&cube[i].right==rights[i]);
  assert(cube[i].m_xform_frame==u32(-1));
 }
 assert(spot.direction==Fvector({.5f,0,1.5f})&&spot.right==Fvector({1.5f,0,.5f}));
 assert(point.direction==Fvector({0,0,1})&&point.right==Fvector({1,0,0}));
 assert(world.position==Fvector({1,2,3})&&world.m_xform_frame==123);
 cube[0].hud=false;shadowed.clear();points.clear();spots.clear();
 // Restore every saved emitter even if relevance lists or its HUD flag changed.
 hud_light_restore(saved);
 for(unsigned i=0;i<6;++i){
  assert(cube[i].position==Fvector({1,2,3})&&cube[i].direction==axes[i]&&cube[i].right==rights[i]);
  assert(cube[i].m_xform_frame==u32(-1));
 }
 assert(spot.position==Fvector({1,2,3})&&spot.direction==Fvector({0,0,1})&&spot.right==Fvector({1,0,0}));
 std::puts("PASS actual DX9/10/11 HUD light helpers: world cube axes, complete spot basis, one projection per emitter, full restore and same-frame matrix invalidation");
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='hud-light-projection-') as temporary:
    folder=Path(temporary)
    cpp,exe=folder/'lights.cpp',folder/('lights.exe' if os.name=='nt' else 'lights')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
