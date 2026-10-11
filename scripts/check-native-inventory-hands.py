"""Actual inventory removal clears hands before the slot disappears (CI only)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/Inventory.cpp").read_text(encoding="utf-8")
start = text.index("void CInventory::netcoop_remove_from_hands(")
end = text.index("bool CInventory::DropItem(", start)
for name in ("DropItem", "Slot", "Belt", "Ruck"):
    begin = text.index("bool CInventory::" + name + "(")
    stop = text.index("\n}", begin)
    method = text[begin:stop]
    assert method.index("netcoop_remove_from_hands(pIItem)") < method.index("m_slots[pIItem->CurrSlot()].m_pIItem = NULL")
source = r'''
#include <cassert>
#include <cstdio>
using u16=unsigned short;
constexpr u16 NO_ACTIVE_SLOT=0xffff;
namespace CHUDState{constexpr unsigned eHidden=0;}
namespace netcoop{bool active=true;bool enabled(){return active;}}
struct Owner{virtual ~Owner()=default;};struct CActor:Owner{};
template<class T>T smart_cast(Owner* p){return dynamic_cast<T>(p);}
struct CHudItem{
 unsigned next=2,state=2,hidden=0;
 void SetNextState(unsigned s){next=s;}
 unsigned GetState(){return state;}
 void OnStateSwitch(unsigned s,unsigned){state=s;++hidden;}
};
struct CWeapon{unsigned unzoomed=0;void OnZoomOut(){++unzoomed;}};
struct Item{
 u16 slot=3;CHudItem hud;CWeapon weapon;bool device=false;
 u16 CurrSlot(){return slot;}
 CHudItem* cast_hud_item(){return &hud;}
 CWeapon* cast_weapon(){return device?nullptr:&weapon;}
};
using PIItem=Item*;
struct CInventory{
 Owner* m_pOwner=nullptr;
 u16 m_iActiveSlot=3,m_iNextActiveSlot=3,m_iPrevActiveSlot=3;
 void netcoop_remove_from_hands(PIItem);
};
'''
source += text[start:end]
source += r'''
int main(){
 CActor actor;Owner npc;Item item;CInventory inv;inv.m_pOwner=&actor;
 inv.netcoop_remove_from_hands(&item);
 assert(item.hud.hidden==1 && item.hud.state==0 && item.hud.next==0 && item.weapon.unzoomed==1);
 assert(inv.m_iActiveSlot==NO_ACTIVE_SLOT && inv.m_iNextActiveSlot==NO_ACTIVE_SLOT && inv.m_iPrevActiveSlot==NO_ACTIVE_SLOT);
 inv.netcoop_remove_from_hands(&item);assert(item.hud.hidden==1);
 inv.m_iActiveSlot=3;inv.m_iNextActiveSlot=5;inv.m_iPrevActiveSlot=5;
 inv.netcoop_remove_from_hands(&item);assert(inv.m_iActiveSlot==NO_ACTIVE_SLOT && inv.m_iNextActiveSlot==5 && inv.m_iPrevActiveSlot==5);
 item.device=true;inv.m_iActiveSlot=3;inv.netcoop_remove_from_hands(&item);assert(item.weapon.unzoomed==2);
 inv.m_iActiveSlot=3;inv.m_iNextActiveSlot=3;inv.m_pOwner=&npc;
 auto count=item.hud.hidden;inv.netcoop_remove_from_hands(&item);assert(item.hud.hidden==count && inv.m_iActiveSlot==3);
 inv.m_pOwner=&actor;netcoop::active=false;inv.netcoop_remove_from_hands(&item);assert(item.hud.hidden==count && inv.m_iActiveSlot==3);
 std::puts("PASS actual hand removal: hidden state, zoom, active/pending/previous slots, devices, NPC/freeplay guards");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "hands.cpp"
    exe = Path(tmp) / ("hands.exe" if os.name == "nt" else "hands")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
