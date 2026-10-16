"""CI-only actual optional actor slot tail: late join, swaps, ownership and legacy."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT/'src/xrGame/Actor_Network.cpp').read_text(encoding='utf-8')
start = text.index('void CActor::netcoop_export_weapon_slots(')
stop = text.index('void CActor::net_Export(NET_Packet& P)', start)
export = text[stop:text.index('static void w_vec_q8(', stop)]
assert export.count('netcoop_export_weapon_slots(P);') == 2
receive = text[text.index('void CActor::net_Import(NET_Packet& P)'):text.index('void CActor::net_Import_Base(', stop)]
assert receive.count('netcoop_import_weapon_slots(P);') == 2
objects = (ROOT/'src/xrEngine/xr_object_list.cpp').read_text(encoding='utf-8')
assert 'own.construct(&Packet->B.data[rsize], size);' in objects and 'P->net_Import(own);' in objects
source = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <map>
#include <vector>
using u16=uint16_t;using u8=uint8_t;
constexpr u16 INV_SLOT_2=2,INV_SLOT_3=3,eItemPlaceSlot=1;
namespace CHUDState{constexpr unsigned eIdle=1;}
namespace netcoop{bool enabled_flag=true,client=true;bool enabled(){return enabled_flag;}bool pure_client(){return enabled_flag&&client;}}
struct NET_Packet{std::vector<u8> bytes;unsigned pos=0;
 void w_u8(u8 v){bytes.push_back(v);}void w_u16(u16 v){w_u8(u8(v));w_u8(u8(v>>8));}
 unsigned r_elapsed(){return unsigned(bytes.size())-pos;}u8 r_u8(){assert(pos<bytes.size());return bytes[pos++];}
 u16 r_u16(){u16 lo=r_u8();return u16(lo|(u16(r_u8())<<8));}};
struct CActor;struct CInventory;
struct CObject{virtual ~CObject()=default;CActor* parent=nullptr;CActor* H_Parent(){return parent;}};
struct CHudItem{unsigned state=1;bool IsHidden(){return state==0;}unsigned GetState(){return state;}
 void OnStateSwitch(unsigned s,unsigned){state=s;}};
struct CInventoryItem:CObject{CInventory* m_pInventory=nullptr;u16 id=0,slot=0,place=2;CHudItem hud;
 u16 object_id(){return id;}CObject& object(){return *this;}u16 CurrSlot(){return slot;}u16 CurrPlace(){return place;}
 CHudItem* cast_hud_item(){return &hud;}};
using PIItem=CInventoryItem*;
template<class T,class U>T smart_cast(U* p){return dynamic_cast<T>(p);}
struct Registry{std::map<u16,CObject*> values;CObject* net_Find(u16 id){auto found=values.find(id);return found==values.end()?nullptr:found->second;}};
struct{Registry Objects;}level;
auto& Level(){return level;}
struct CInventory{PIItem slots[4]={};u16 active=0;unsigned moves=0;
 PIItem ItemFromSlot(u16 n){return slots[n];}PIItem ActiveItem(){return active?slots[active]:nullptr;}
 bool Ruck(PIItem item,bool strict){assert(strict);if(item->place==1){slots[item->slot]=nullptr;if(active==item->slot){active=0;item->hud.state=0;}}
  item->place=2;++moves;return true;}
 bool Slot(u16 n,PIItem item,bool no_activate,bool strict){assert(no_activate&&strict&&!slots[n]);
  if(item->place==1)slots[item->slot]=nullptr;slots[n]=item;item->slot=n;item->place=1;++moves;return true;}
 void SetActiveSlot(u16 n){active=n;}};
struct CActor{CInventory inv;bool server=false,local=false,alive=true;
 bool OnServer(){return server;}bool OnClient(){return !server;}bool Local(){return local;}bool g_Alive(){return alive;}
 CInventory& inventory(){return inv;}void netcoop_export_weapon_slots(NET_Packet&);void netcoop_import_weapon_slots(NET_Packet&);};
''' + text[start:stop] + r'''
NET_Packet tail(u16 first,u16 second){NET_Packet p;p.w_u16(0x5342);p.w_u8(1);p.w_u8(2);p.w_u16(first);p.w_u16(second);return p;}
void own(CActor& actor,CInventoryItem& item,u16 id){item.parent=&actor;item.m_pInventory=&actor.inv;item.id=id;level.Objects.values[id]=&item;}
int main(){
 CActor actor;CInventoryItem a,b,foreign;own(actor,a,10);own(actor,b,11);own(actor,foreign,12);
 NET_Packet none;actor.netcoop_export_weapon_slots(none);assert(none.bytes.empty());
 actor.server=true;actor.inv.slots[2]=&a;actor.inv.slots[3]=&b;
 NET_Packet exported;actor.netcoop_export_weapon_slots(exported);assert(exported.bytes==tail(10,11).bytes);
 netcoop::enabled_flag=false;NET_Packet disabled;actor.netcoop_export_weapon_slots(disabled);assert(disabled.bytes.empty());
 netcoop::enabled_flag=true;actor.server=false;actor.inv.slots[2]=actor.inv.slots[3]=nullptr;
 auto fresh=tail(10,11);actor.netcoop_import_weapon_slots(fresh);assert(actor.inv.slots[2]==&a&&actor.inv.slots[3]==&b);
 auto moves=actor.inv.moves;fresh.pos=0;actor.netcoop_import_weapon_slots(fresh);assert(actor.inv.moves==moves);
 actor.inv.active=2;auto swap=tail(11,10);actor.netcoop_import_weapon_slots(swap);
 assert(actor.inv.slots[2]==&b&&actor.inv.slots[3]==&a&&actor.inv.active==3&&a.hud.state==CHUDState::eIdle);
 // A missing or foreign half refuses the complete observation, without
 // removing a valid old weapon. A later snapshot retries after ownership.
 moves=actor.inv.moves;auto missing=tail(10,99);actor.netcoop_import_weapon_slots(missing);assert(actor.inv.moves==moves);
 foreign.parent=nullptr;auto wrong=tail(10,12);actor.netcoop_import_weapon_slots(wrong);assert(actor.inv.moves==moves);
 foreign.parent=&actor;foreign.m_pInventory=nullptr;wrong.pos=0;actor.netcoop_import_weapon_slots(wrong);assert(actor.inv.moves==moves);
 auto duplicate=tail(10,10);actor.netcoop_import_weapon_slots(duplicate);assert(actor.inv.moves==moves);
 for(unsigned size=0;size<9;++size){if(size==8)continue;auto truncated=tail(10,11);truncated.bytes.resize(size);
  actor.netcoop_import_weapon_slots(truncated);assert(actor.inv.moves==moves&&truncated.pos==0);}
 for(unsigned byte=0;byte<4;++byte){auto malformed=tail(10,11);malformed.bytes[byte]^=0x7f;
  actor.netcoop_import_weapon_slots(malformed);assert(actor.inv.moves==moves);}
 for(unsigned mode=0;mode<4;++mode){actor.local=mode==0;actor.server=mode==1;actor.alive=mode!=2;netcoop::client=mode!=3;
  auto p=tail(u16(-1),u16(-1));actor.netcoop_import_weapon_slots(p);assert(actor.inv.moves==moves);}
 actor.local=false;actor.server=false;actor.alive=true;netcoop::client=true;
 auto empty=tail(u16(-1),u16(-1));actor.netcoop_import_weapon_slots(empty);
 assert(!actor.inv.slots[2]&&!actor.inv.slots[3]&&actor.inv.active==0);
 // Old clients stop before this optional tail. The object-list reader uses
 // its declared object size to skip it, independently of the next object.
 assert(exported.bytes.size()==8);
 std::puts("PASS actual optional actor weapon-slot tail: server-only author, legacy empty tail, exact bounds/tag/version, late join, swap, selected-object preservation, missing/foreign/duplicate refusal and owner/dead/server exclusion");
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='weapon-slots-') as temporary:
    folder = Path(temporary)
    cpp, exe = folder/'slots.cpp', folder/('slots.exe' if os.name == 'nt' else 'slots')
    cpp.write_text(source, encoding='utf-8')
    command = (['cl', '/nologo', '/utf-8', '/std:c++17', '/EHsc', '/W4', '/WX', str(cpp), '/Fe:'+str(exe)] if os.name == 'nt' else
               ['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)])
    subprocess.run(command, cwd=folder, check=True)
    subprocess.run([str(exe)], cwd=folder, check=True, timeout=10)
