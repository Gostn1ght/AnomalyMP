"""Actual remote HUD state gate: owned item and complete packet before mutation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/netcoop.cpp").read_text(encoding="utf-8")
start = text.index("static bool remote_hud_state_allowed(")
end = text.index("bool server_remote_event_allowed(", start)
dispatch = text[end:text.index('#include "netcoop_transfer.inc"', end)]
assert "case GE_WPN_STATE_CHANGE:\n\t\treturn remote_hud_state_allowed(server, CL, P, destination);" in dispatch
source = r'''
#include <cassert>
#include <cstdio>
#include <map>
#include <vector>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;
struct CSE_Abstract{virtual ~CSE_Abstract()=default;u16 ID=1,ID_Parent=1;};
struct CSE_ALifeItemWeapon:CSE_Abstract{};
template<class T,class U>T smart_cast(U* obj){return dynamic_cast<T>(obj);}
struct CObject{virtual ~CObject()=default;};
struct CWeapon:CObject{std::vector<int>m_ammoTypes{0,1};int capacity=30;int GetAmmoMagSize(){return capacity;}};
struct ObjectRegistry{CObject* runtime=nullptr;CObject* net_Find(u16){return runtime;}};
struct LevelState{ObjectRegistry Objects;}level_state;
LevelState& Level(){return level_state;}
struct Game{
 std::map<u16,CSE_Abstract*> objects;
 CSE_Abstract* get_entity_from_eid(u16 id){auto it=objects.find(id);return it==objects.end()?nullptr:it->second;}
};
struct xrServer{Game* game;};struct xrClientData{CSE_Abstract* owner;};
struct NET_Packet{u32 size=0,r_pos=0;u8 data[5]={0,0,0,0,255};
 u32 r_elapsed(){return size-r_pos;}u8 r_u8(){assert(r_pos<size);return data[r_pos++];}
};
'''
source += text[start:end]
source += r'''
int main(){
 Game game;xrServer server{&game};CSE_Abstract actor,other,device;
 actor.ID=7;other.ID=8;CSE_ALifeItemWeapon weapon;weapon.ID_Parent=7;device.ID_Parent=7;
 CWeapon runtime;level_state.Objects.runtime=&runtime;
 game.objects[10]=&weapon;game.objects[11]=&device;xrClientData client{&actor};NET_Packet packet;
 for(u32 size=0;size<10;++size){
  packet.size=size;
  assert(remote_hud_state_allowed(&server,&client,packet,10)==(size==5));
  assert(remote_hud_state_allowed(&server,&client,packet,11)==(size==1));
  assert(packet.r_pos==0);
 }
 packet.size=5;packet.data[3]=31;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 packet.data[3]=1;packet.data[2]=2;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 packet.data[2]=0;packet.data[4]=2;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 packet.data[4]=255;assert(remote_hud_state_allowed(&server,&client,packet,10));
 runtime.m_ammoTypes.clear();runtime.capacity=0;
 assert(!remote_hud_state_allowed(&server,&client,packet,10));packet.data[3]=0;
 assert(remote_hud_state_allowed(&server,&client,packet,10));
 level_state.Objects.runtime=nullptr;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 level_state.Objects.runtime=&runtime;
 packet.size=5;client.owner=&other;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 client.owner=nullptr;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 client.owner=&actor;weapon.ID_Parent=0xffff;assert(!remote_hud_state_allowed(&server,&client,packet,10));
 assert(!remote_hud_state_allowed(&server,&client,packet,99));
 std::puts("PASS actual HUD state gate: owner, size, magazine capacity and ammo indexes; cursor preserved");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "state.cpp"
    exe = Path(tmp) / ("state.exe" if os.name == "nt" else "state")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
