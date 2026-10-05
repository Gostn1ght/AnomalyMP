"""Exercise actual native corpse adapters with ALife/network fixtures in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
game = root / "src/xrGame"
release = (game / "alife_simulator_base.cpp").read_text()
release = release[release.index("void CALifeSimulatorBase::release("):
                  release.index("void CALifeSimulatorBase::append_item_vector(")]
online = (game / "xrServer_process_event_destroy.cpp").read_text()
online = online[online.index("\tconst auto creature ="):
                online.index("\t// check if we have children")]
source = r'''
#include "netcoop_corpse_inventory.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <vector>
#include <iostream>
#ifdef _WIN32
#include <malloc.h>
#pragma warning(disable:4267) // legacy release uses u32 with the engine vector
#else
#include <alloca.h>
#define _alloca alloca
#endif
using u16=std::uint16_t; using u32=std::uint32_t;
namespace ALife {using _OBJECT_ID=u16;}
#define VERIFY(x) assert(x)
#define CopyMemory std::memcpy
void Msg(const char*,...) {}
template<class T,class U> T smart_cast(U* value) {return dynamic_cast<T>(value);}
struct CSE_Abstract {
 virtual ~CSE_Abstract()=default;
 u16 ID=0,ID_Parent=65535;std::vector<u16> children;
 bool m_bALifeControl=true;
 const char* name_replace() const {return "fixture";}
};
struct CSE_ALifeDynamicObject:CSE_Abstract {
 bool m_bOnline=false;int m_tGraphID=3,m_tNodeID=7,o_Position=12;
};
struct CSE_ALifeCreatureAbstract:CSE_ALifeDynamicObject {
 float health=0;float get_health() const {return health;}
};
struct CSE_ALifeCreatureActor:CSE_ALifeCreatureAbstract {};
struct CSE_ALifeInventoryItem:CSE_ALifeDynamicObject {int quantity=9,ammo=17;float condition=.43f;};
struct Registry {
 std::map<u16,CSE_ALifeDynamicObject*> values;
 CSE_ALifeDynamicObject* object(u16 id,bool optional=false) {
  auto i=values.find(id);if(i!=values.end())return i->second;
  assert(optional);return nullptr;
 }
};
struct Graph {
 std::map<u16,CSE_ALifeDynamicObject*> ground;
 void detach(CSE_ALifeDynamicObject& parent,CSE_ALifeInventoryItem* child,int vertex,bool query,bool remove) {
  assert(query && remove && child && child->ID_Parent==parent.ID);
  child->ID_Parent=65535;child->m_tGraphID=vertex;
  child->m_tNodeID=parent.m_tNodeID;child->o_Position=parent.o_Position;
  parent.children.erase(std::find(parent.children.begin(),parent.children.end(),child->ID));
  ground[child->ID]=child;
 }
};
struct Server {std::vector<u16> destroyed;void entity_Destroy(CSE_Abstract* value){destroyed.push_back(value->ID);}};
struct CALifeSimulatorBase {
 Registry registry;Graph graph_registry;Server server_registry;
 Registry& objects(){return registry;}Graph& graph(){return graph_registry;}Server& server(){return server_registry;}
 void unregister_object(CSE_ALifeDynamicObject* value,bool) {registry.values.erase(value->ID);}
 void release(CSE_Abstract*,bool);
};
namespace netcoop {bool active=true;bool enabled(){return active;}}
''' + release + r'''
struct ClientID {};
constexpr u16 GE_OWNERSHIP_REJECT=1,M_EVENT=2;
struct NET_Packet {
 u16 id=0;u32 timestamp=0;std::vector<u16> words;
 void w_begin(u16 value){assert(value==M_EVENT);}
 void w_u32(u32 value){timestamp=value;}
 void w_u16(u16 value){words.push_back(value);id=value;}
};
struct Game {
 Registry* registry;std::vector<u16> events;
 CSE_Abstract* get_entity_from_eid(u16 id){return registry->object(id,true);}
 void u_EventGen(NET_Packet&,int kind,u16){assert(kind==GE_OWNERSHIP_REJECT);}
};
struct AI {
 CALifeSimulatorBase* sim=nullptr;
 CALifeSimulatorBase* get_alife(){return sim;}CALifeSimulatorBase& alife(){return *sim;}
} fixture_ai;
AI& ai(){return fixture_ai;}
struct OnlineServer {
 Game* game;bool proceed=false;u16 fail_id=65535;
 bool Process_event_reject(NET_Packet& packet,ClientID,u32 time,u16 parent_id,u16 child_id,bool broadcast) {
  assert(packet.id==child_id && broadcast);
  const std::vector<u16> expected{GE_OWNERSHIP_REJECT,parent_id,child_id};
  assert(packet.words==expected && packet.timestamp==time);
  if(child_id==fail_id)return false;
  auto parent=game->registry->object(parent_id);
  auto child=game->registry->object(child_id);
  child->ID_Parent=65535;child->o_Position=parent->o_Position;
  parent->children.erase(std::find(parent->children.begin(),parent->children.end(),child_id));
  game->events.push_back(child_id);return true;
 }
 void before_destroy(CSE_Abstract* e_dest) {
  u16 id_dest=e_dest->ID;ClientID sender;u32 time=123;proceed=false;
''' + online + r'''
  proceed=true;
 }
};
struct Fixture {
 CALifeSimulatorBase sim;CSE_ALifeCreatureAbstract body;
 CSE_ALifeInventoryItem first,second;Game game;OnlineServer online;
 Fixture():game{&sim.registry,{}},online{&game,false,65535} {
  netcoop::active=true;fixture_ai.sim=&sim;
  body.ID=1;body.children={2,3};first.ID=2;second.ID=3;
  first.ID_Parent=second.ID_Parent=1;
  sim.registry.values={{1,&body},{2,&first},{3,&second}};
 }
 void loot_survives() {
  assert(sim.registry.object(2)==&first && sim.registry.object(3)==&second);
  assert(first.quantity==9 && first.ammo==17 && first.condition==.43f);
  assert(second.quantity==9 && second.ammo==17 && second.condition==.43f);
  assert(first.m_bALifeControl && second.m_bALifeControl);
 }
};
int main() {
 {Fixture f;f.sim.release(&f.body,true);f.loot_survives();
  assert(f.body.children.empty() && f.first.ID_Parent==65535 && f.second.ID_Parent==65535);
  assert(f.first.o_Position==f.body.o_Position && f.first.m_tNodeID==f.body.m_tNodeID);
  assert(f.sim.graph_registry.ground.size()==2 && f.sim.server_registry.destroyed==std::vector<u16>{1});}
 {Fixture f;f.body.m_bOnline=true;f.first.m_bOnline=f.second.m_bOnline=true;
  f.online.before_destroy(&f.body);assert(f.online.proceed);f.loot_survives();
  const std::vector<u16> expected{2,3};assert(f.game.events==expected);
  f.sim.release(&f.body,false);f.loot_survives();assert(!f.sim.registry.object(1,true));}
 {Fixture f;f.second.ID_Parent=99;f.sim.release(&f.body,true);
  assert(f.sim.registry.object(1)==&f.body && f.first.ID_Parent==1 && f.sim.graph_registry.ground.empty());}
 {Fixture f;f.sim.registry.values.erase(3);f.online.before_destroy(&f.body);
  assert(!f.online.proceed && f.first.ID_Parent==1 && f.game.events.empty());}
 {Fixture f;f.body.children={2,2};f.online.before_destroy(&f.body);
  assert(!f.online.proceed && f.game.events.empty());}
 {Fixture f;f.online.fail_id=3;f.online.before_destroy(&f.body);
  assert(!f.online.proceed && f.first.ID_Parent==65535 && f.second.ID_Parent==1);
  f.loot_survives();f.online.fail_id=65535;f.online.before_destroy(&f.body);assert(f.online.proceed);}
 {Fixture f;f.body.m_bOnline=true;f.sim.release(&f.body,false);
  assert(f.sim.registry.object(1)==&f.body && f.first.ID_Parent==1);}
 {Fixture f;CSE_ALifeDynamicObject component;component.ID=3;component.ID_Parent=1;
  f.sim.registry.values[3]=&component;f.sim.release(&f.body,true);
  assert(f.sim.registry.object(1)==&f.body && f.first.ID_Parent==1);}
 // Living NPCs, actors, and the single-player policy retain ordinary release.
 {Fixture f;f.body.health=1;f.sim.release(&f.body,true);assert(f.sim.registry.values.empty());}
 {Fixture f;CSE_ALifeCreatureActor actor;actor.ID=1;actor.children={2,3};
  f.sim.registry.values[1]=&actor;f.sim.release(&actor,true);assert(f.sim.registry.values.empty());}
 {Fixture f;netcoop::active=false;f.sim.release(&f.body,true);assert(f.sim.registry.values.empty());}
 {std::vector<u16> children{1,2};int detached=0;
  assert(!netcoop::preserve_corpse_inventory(children,[](u16){return true;},[&](u16){++detached;return true;}));
  assert(detached==1);}
 {std::vector<u16> children(4097,1);int checked=0;
  assert(!netcoop::preserve_corpse_inventory(children,[&](u16){++checked;return true;},[](u16){return true;}));
  assert(checked==0);}
 std::cout<<"PASS: actual offline release and online adapter preserve IDs/state, order detaches, fail closed and exclude actors/living/single-player\n";
}
'''
with TemporaryDirectory(prefix="corpse-inventory-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    include = str(game)
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   "/I" + include, str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2",
                   "-I", include, str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
