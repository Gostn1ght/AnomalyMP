"""CI-only real skeleton history; first use/pool reuse/gaps must not read garbage."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT/'src/Layers/xrRender/SkeletonCustom.cpp').read_text(encoding='utf-8-sig')
start = text.index('void CKinematics::ResetMotionHistory()')
stop = text.index('CKinematics::~CKinematics()', start)
for begin, end in (('CKinematics::CKinematics()', 'void CKinematics::ResetMotionHistory()'),
                   ('void CKinematics::Copy(', 'void CKinematics::CalculateBones_Invalidate()'),
                   ('void CKinematics::Spawn()', 'void CKinematics::Depart()')):
    assert 'ResetMotionHistory();' in text[text.index(begin):text.index(end, text.index(begin))]
render = (ROOT/'src/Layers/xrRender/SkeletonX.cpp').read_text(encoding='utf-8-sig')
assert 'Parent->UpdateMotionHistory(Device.dwFrame, RCache.xforms.m_w);' in render
assert 'Device.dwFrame > Parent->CurrentFrame' not in render
source = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <vector>
using u16=uint16_t;using u32=uint32_t;
struct Fmatrix{
 float values[16];
 Fmatrix(){std::fill(values,values+16,std::numeric_limits<float>::quiet_NaN());}
 void identity(){std::fill(values,values+16,0.f);for(unsigned i=0;i<4;++i)values[i*5]=1;}
 void set(const Fmatrix& other){std::copy(other.values,other.values+16,values);}
 bool operator==(const Fmatrix& other)const{return std::equal(values,values+16,other.values);}
 bool finite()const{for(float value:values)if(!std::isfinite(value))return false;return true;}
};
Fmatrix pose(float value){Fmatrix result;result.identity();result.values[12]=value;return result;}
struct CBoneInstance{Fmatrix mRenderTransform,mRenderTransform_prev,mRenderTransform_temp;};
struct CKinematics{
 u32 CurrentFrame=0xcccccccc;bool m_motion_history_valid=true;
 Fmatrix Matrix_Prev,Matrix_Temp;std::vector<CBoneInstance> bones;
 u16 LL_BoneCount(){return u16(bones.size());}CBoneInstance& LL_GetBoneInstance(u16 b){return bones.at(b);}
 void ResetMotionHistory();void UpdateMotionHistory(u32,const Fmatrix&);
 void current(float value){for(u16 b=0;b<LL_BoneCount();++b)bones[b].mRenderTransform=pose(value+float(b));}
 void check(float previous,float temporary){
  assert(Matrix_Prev.finite()&&Matrix_Temp.finite());
  assert(Matrix_Prev==pose(previous)&&Matrix_Temp==pose(temporary));
  for(u16 b=0;b<LL_BoneCount();++b){
   assert(bones[b].mRenderTransform_prev.finite()&&bones[b].mRenderTransform_temp.finite());
   assert(bones[b].mRenderTransform_prev==pose(previous+float(b)));
   assert(bones[b].mRenderTransform_temp==pose(temporary+float(b)));
  }
 }
};
'''+text[start:stop]+r'''
int main(){
 CKinematics actor;actor.bones.resize(3);actor.ResetMotionHistory();
 assert(!actor.m_motion_history_valid&&actor.CurrentFrame==0);
 assert(actor.Matrix_Prev.finite()&&actor.Matrix_Temp.finite());
 // Bone histories still contain NaNs: the real first draw must seed them.
 assert(!actor.bones[0].mRenderTransform_temp.finite());
 actor.current(10);actor.UpdateMotionHistory(0,pose(10));actor.check(10,10);
 actor.current(20);actor.UpdateMotionHistory(1,pose(20));actor.check(10,20);
 // Another child, shadow or scope pass of this skeleton in the same frame
 // cannot advance the history and erase the genuine previous pose.
 actor.UpdateMotionHistory(1,pose(99));actor.check(10,20);
 actor.current(30);actor.UpdateMotionHistory(2,pose(30));actor.check(20,30);
 // Returning from culling/disabled motion vectors after a gap.
 actor.current(50);actor.UpdateMotionHistory(8,pose(50));actor.check(50,50);
 actor.current(60);actor.UpdateMotionHistory(9,pose(60));actor.check(50,60);
 // Model pool reuse at the SAME device frame discards its old actor's pose.
 actor.ResetMotionHistory();actor.current(100);actor.UpdateMotionHistory(9,pose(100));actor.check(100,100);
 // New actors may first draw at any frame, including the largest u32.
 actor.ResetMotionHistory();actor.current(200);actor.UpdateMotionHistory(u32(-1),pose(200));actor.check(200,200);
 actor.current(210);actor.UpdateMotionHistory(0,pose(210));actor.check(200,210);
 actor.current(220);actor.UpdateMotionHistory(1,pose(220));actor.check(210,220);
 // A backwards/restarted device counter is a gap rather than a permanent freeze.
 actor.current(230);actor.UpdateMotionHistory(0,pose(230));actor.check(230,230);
 CKinematics empty;empty.ResetMotionHistory();empty.UpdateMotionHistory(17,pose(1));empty.check(1,1);
 std::puts("PASS actual skeleton motion history: poisoned first-use memory, multi-pass once per frame, sequential bones/world, culling gaps, model reuse, frame zero and u32 wrap");
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='skeleton-motion-history-') as temporary:
    folder=Path(temporary)
    cpp,exe=folder/'history.cpp',folder/('history.exe' if os.name=='nt' else 'history')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
