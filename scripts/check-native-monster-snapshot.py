"""Actual monster snapshot exports current pose/time without changing wire shape."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/CustomMonster.cpp').read_text(encoding='latin-1')
code=text[text.index('void CCustomMonster::net_Export('):text.index('void CCustomMonster::net_Import(')]
source=r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include <cstdio>
using u8=std::uint8_t;using u32=std::uint32_t;
#define R_ASSERT(x) assert(x)
struct Fvector{float x=0,y=0,z=0;};
struct SRotation{float yaw=0,pitch=0,roll=0;};
struct Fmatrix{float heading=-0.7f;void getHPB(float& h,float& p,float& b){h=heading;p=0;b=0;}};
float angle_normalize(float v){return v;}
struct NET_Packet{std::vector<float>values;void w_float(float v){values.push_back(v);}
 void w_u32(u32 v){values.push_back(float(v));}void w_u8(u8 v){values.push_back(float(v));}
 void w_vec3(const Fvector& v){w_float(v.x);w_float(v.y);w_float(v.z);}};
struct LevelState{u32 stamp=1234;u32 timeServer(){return stamp;}}fixture_level;
LevelState& Level(){return fixture_level;}
namespace netcoop{bool fixture_smooth=false;bool smooth(){return fixture_smooth;}}
struct net_update{u32 dwTimeStamp=100;Fvector p_pos{1,2,3};float o_model=0.1f;SRotation o_torso{0.2f,0.3f,0.4f};};
struct Movement{struct{SRotation current{1.2f,0.8f,0.5f};}m_body;};
struct CCustomMonster{std::vector<net_update>NET{{}};Fvector fixture_position{10,20,30};Movement fixture_movement;Fmatrix fixture_matrix;
 bool Local(){return true;}float GetfHealth(){return 0.75f;}Fvector& Position(){return fixture_position;}
 Movement& movement(){return fixture_movement;}Fmatrix& XFORM(){return fixture_matrix;}
 int g_Team(){return 1;}int g_Squad(){return 2;}int g_Group(){return 3;}void net_Export(NET_Packet&);};
''' + code + r'''
int main(){
 CCustomMonster beast;NET_Packet stock;beast.net_Export(stock);
 assert(stock.values.size()==13&&stock.values[0]==0.75f&&stock.values[1]==100);
 assert(stock.values[3]==1&&stock.values[4]==2&&stock.values[5]==3&&stock.values[6]==0.1f);
 netcoop::fixture_smooth=true;NET_Packet fresh;beast.net_Export(fresh);
 assert(fresh.values.size()==13&&fresh.values[1]==1234);
 assert(fresh.values[3]==10&&fresh.values[4]==20&&fresh.values[5]==30&&fresh.values[6]==0.7f);
 assert(fresh.values[7]==1.2f&&fresh.values[8]==0.8f&&fresh.values[9]==0.5f);
 assert(fresh.values[10]==1&&fresh.values[11]==2&&fresh.values[12]==3);
 fixture_level.stamp=1250;beast.fixture_position.x=15;beast.fixture_matrix.heading=-0.9f;
 NET_Packet following;beast.net_Export(following);
 assert(following.values[1]==1250&&following.values[3]==15&&following.values[6]==0.9f);
 assert(beast.NET.back().dwTimeStamp==100&&beast.NET.back().p_pos.x==1);
 std::puts("PASS actual monster pose export: fresh frame position/body/view/time, unchanged 13-field wire and stock scheduled snapshot");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'snapshot.cpp';exe=Path(tmp)/('snapshot.exe' if os.name=='nt' else 'snapshot')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
