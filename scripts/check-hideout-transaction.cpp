// Runs the actual server transaction include with isolated transport/save adapters.
#include "../src/xrGame/netcoop_storage_policy.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <cmath>
#include <limits>
#include <string>
#include <iostream>
using u32=unsigned;using u16=unsigned short;using xr_string=std::string;
template<class T> using xr_vector=std::vector<T>;
using string128=char[128];using string32=char[32];using string64=char[64];using string_path=char[260];using LPCSTR=const char*;
#define _min std::min
#define _max std::max
#define TRUE true
#define FALSE false
#define xr_strcmp std::strcmp
template<size_t N,class... Args> void xr_sprintf(char(&out)[N],const char* fmt,Args... args){std::snprintf(out,N,fmt,args...);}
struct CInifile {CInifile(char*,bool,bool,bool){}bool line_exist(const char*,const char*){return false;}u32 r_u32(const char*,const char*){return 60;}};
struct FileSystem {unsigned reads=0;bool exist(char*,const char*,const char*){++reads;return false;}} FS;
struct Settings {bool line_exist(const char*,const char*){return true;}u32 r_u32(const char* s,const char* k){return std::strcmp(k,"inv_grid_height")==0 ? 1 : std::strcmp(s,"rifle")==0 ? 10 : std::strcmp(s,"huge")==0 ? 200 : 1;}} settings,*pSettings=&settings;
enum {eItemPlaceSlot=1,eItemPlaceBelt=2};
union SInvItemPlace {u16 value;struct {unsigned short type:2;};};
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID=9,ID_Parent=0xffff;xr_string s_name;std::vector<u16> children;};
struct CSE_ALifeCreatureActor:CSE_Abstract{};struct CSE_ALifeInventoryItem:CSE_Abstract{};
template<class T,class U> T smart_cast(U* p){return dynamic_cast<T>(p);}
struct Game {std::map<u16,CSE_Abstract*> objects;CSE_Abstract* get_entity_from_eid(u16 id){auto p=objects.find(id);return p==objects.end()?nullptr:p->second;}};
struct RuntimeObject {virtual ~RuntimeObject()=default;};
struct RuntimeItem:RuntimeObject {xr_string section="rifle";RuntimeItem& object(){return *this;}const xr_string& cNameSect(){return section;}};
using PIItem=RuntimeItem*;
struct CActor:RuntimeObject {float weight=40;struct Bag {std::vector<PIItem> m_ruck;} bag;Bag& inventory(){return bag;}float MaxCarryWeight(){return weight;}};
struct Registry {std::map<u16,RuntimeObject*> objects;RuntimeObject* net_Find(u16 id){auto it=objects.find(id);return it==objects.end()?nullptr:it->second;}};
struct RuntimeLevel {Registry Objects;} runtime_level;
RuntimeLevel& Level(){return runtime_level;}CActor* own=nullptr;CActor* Actor(){return own;}
bool _valid(float value){return std::isfinite(value);}
struct xrServer {Game* game;};
namespace netcoop {
enum {role_none=0,role_player=1,role_admin=2};
struct xrClientData {unsigned netcoop_role=role_player;xr_string netcoop_login="owner";};
struct Character {
    struct Item {xr_string section;u16 parent=0,place=0;xr_string spawn;};
    xr_string account="owner",storage_request,storage_signature;unsigned slot=1;bool initialized=true,respawn=false;
    u32 storage_revision=1,inventory_cells=0;xr_vector<Item> items,safe;
};
struct StorageRequest {unsigned op=0,slot=1,index=0,revision=1;xr_string id=std::string(32,'a');};
static Character memory,disk;static bool save_failed=false;
static std::map<u16,xr_string> s_actor_character;
static xr_string character_key(const char* account,unsigned slot){return xr_string(account)+":"+std::to_string(slot);}
static Character* character_load(const char* account,unsigned slot){return memory.account==account && memory.slot==slot ? &memory : nullptr;}
static bool character_save(Character& candidate){if(save_failed)return false;disk=candidate;return true;}
bool enabled(){return true;}
#include "../src/xrGame/netcoop_storage.inc"
}
int main()
{
    using namespace netcoop;
    memory.items={{"rifle",0,0,"condition=.73;ammo=17"},{"scope",1,0,"upgrade=x"},{"medkit",0,1,"condition=1"}};disk=memory;
    Game game;xrServer server{&game};xrClientData client;
    StorageRequest req;req.op=1;
    assert(storage_execute(&server,&client,req).find("OK\n2|0|120|10|120\n")==0);
    assert(memory.safe.size()==2 && memory.safe[0].spawn=="condition=.73;ammo=17" && disk.storage_revision==2);
    memory=disk; // simulate persisted state reloaded after restart
    assert(storage_execute(&server,&client,req).find("OK\n")==0 && memory.storage_revision==2 && memory.safe.size()==2);
    req.index=2;assert(storage_execute(&server,&client,req).find("INVALID_REQUEST\n")==0);
    req.id=std::string(32,'b');req.op=2;req.index=0;
    assert(storage_execute(&server,&client,req).find("STALE\n")==0 && memory.safe.size()==2);
    req.revision=2;save_failed=true;
    assert(storage_execute(&server,&client,req).find("SAVE_FAILED\n")==0 && memory.safe.size()==2 && disk.storage_revision==2);
    save_failed=false;assert(storage_execute(&server,&client,req).find("OK\n")==0 && memory.safe.empty() && memory.items[1].spawn=="condition=.73;ammo=17");
    req.op=1;req.revision=3;req.id=std::string(32,'c');
    assert(storage_execute(&server,&client,req).find("UNEQUIP_FIRST\n")==0);
    req.slot=10;assert(storage_execute(&server,&client,req)=="DENIED\n");req.slot=1;
    CSE_ALifeCreatureActor actor;game.objects[9]=&actor;s_actor_character[9]=character_key("owner",1);
    assert(storage_execute(&server,&client,req)=="CHARACTER_ONLINE\n");s_actor_character.clear();
    memory.respawn=true;assert(storage_execute(&server,&client,req).find("CHARACTER_NOT_READY\n")==0);memory.respawn=false;
    memory.safe={{"huge",0,0,""}};req.op=2;req.index=0;
    assert(storage_execute(&server,&client,req).find("NO_FREE_SLOTS\n")==0 && memory.safe.size()==1);
    CSE_ALifeInventoryItem root,incoming;root.ID=10;root.ID_Parent=9;incoming.ID=11;root.s_name="rifle";incoming.s_name="huge";game.objects[10]=&root;game.objects[11]=&incoming;actor.children={10};
    assert(!server_inventory_can_take(&server,9,11));assert(xr_string(server_inventory_take_failure(&server,9,11)).find("inventory cells full (10 + 200 / 120)")==0);incoming.s_name="medkit";assert(server_inventory_can_take(&server,9,11));
    CActor live;RuntimeItem held;live.bag.m_ruck={&held};runtime_level.Objects.objects[9]=&live;own=&live;
    assert(storage_live_capacity(&live)==160 && xr_string(script_inventory_slots())=="10|160");
    incoming.s_name="huge";assert(!server_inventory_can_take(&server,9,11));
    live.weight=80;assert(storage_live_capacity(&live)==320 && server_inventory_can_take(&server,9,11));
    live.weight=1000;assert(storage_live_capacity(&live)==512);live.weight=0;assert(storage_live_capacity(&live)==120);
    live.weight=std::numeric_limits<float>::quiet_NaN();assert(storage_live_capacity(&live)==120);
    // Saved capacity survives offline safe withdrawals; equipped armor occupies no rucksack cells.
    memory.inventory_cells=240;req.revision=memory.storage_revision;req.id=std::string(32,'d');
    assert(storage_execute(&server,&client,req).find("OK\n")==0 && memory.safe.empty());
    assert(memory.inventory_cells==240 && storage_saved_capacity(memory)==240);
    assert(storage_ruck_cost(Character::Item{"huge",0,eItemPlaceSlot,""})==0);
    assert(storage_ruck_cost(Character::Item{"huge",0,0,""})==200);
    CSE_ALifeInventoryItem nested;nested.ID=12;nested.ID_Parent=11;game.objects[12]=&nested;incoming.children={12};
    assert(storage_inventory_room(&server,&actor,xr_vector<u16>{11}));
    nested.children={11};assert(!storage_inventory_room(&server,&actor,xr_vector<u16>{11}));assert(xr_string(server_inventory_take_failure(&server,9,11))=="inventory state is not ready");nested.children.clear();
    incoming.children.clear();actor.children.clear();
    std::vector<CSE_ALifeInventoryItem> maximum(512);
    for(u16 i=0;i<512;++i){const u16 id=u16(100+i);maximum[i].ID=id;maximum[i].ID_Parent=9;game.objects[id]=&maximum[i];actor.children.push_back(id);}
    assert(!storage_inventory_room(&server,&actor,xr_vector<u16>{11}));assert(xr_string(server_inventory_take_failure(&server,9,11))=="inventory save limit reached (512 items)");actor.children.pop_back();
    assert(storage_inventory_room(&server,&actor,xr_vector<u16>{11}));
    assert(FS.reads==1);
    std::cout<<"Actual server transaction: authenticated owner/slot, replay/restart, signature, stale revision, failed save rollback, online/dead exclusion and capacity PASS\n";
}
