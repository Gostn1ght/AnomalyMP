// Runs the actual server transaction include with isolated transport/save adapters.
#include "../src/xrGame/netcoop_storage_policy.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <iostream>
using u32=unsigned;using u16=unsigned short;using xr_string=std::string;
template<class T> using xr_vector=std::vector<T>;
using string32=char[32];using string_path=char[260];using LPCSTR=const char*;
#define _min std::min
#define _max std::max
#define TRUE true
#define FALSE false
#define xr_strcmp std::strcmp
template<size_t N,class... Args> void xr_sprintf(char(&out)[N],const char* fmt,Args... args){std::snprintf(out,N,fmt,args...);}
struct CInifile {CInifile(char*,bool,bool,bool){}bool line_exist(const char*,const char*){return false;}u32 r_u32(const char*,const char*){return 60;}};
struct FileSystem {bool exist(char*,const char*,const char*){return false;}} FS;
struct Settings {bool line_exist(const char*,const char*){return true;}u32 r_u32(const char* s,const char* k){return std::strcmp(k,"inv_grid_height")==0 ? 1 : std::strcmp(s,"rifle")==0 ? 10 : std::strcmp(s,"huge")==0 ? 200 : 1;}} settings,*pSettings=&settings;
enum {eItemPlaceSlot=1,eItemPlaceBelt=2};
union SInvItemPlace {u16 value;struct {unsigned short type:2;};};
struct CSE_Abstract {virtual ~CSE_Abstract()=default;u16 ID_Parent=0xffff;xr_string s_name;std::vector<u16> children;};
struct CSE_ALifeCreatureActor:CSE_Abstract{};struct CSE_ALifeInventoryItem:CSE_Abstract{};
template<class T> T smart_cast(CSE_Abstract* p){return dynamic_cast<T>(p);}
struct Game {std::map<u16,CSE_Abstract*> objects;CSE_Abstract* get_entity_from_eid(u16 id){auto p=objects.find(id);return p==objects.end()?nullptr:p->second;}};
struct xrServer {Game* game;};
namespace netcoop {
enum {role_none=0,role_player=1,role_admin=2};
struct xrClientData {unsigned netcoop_role=role_player;xr_string netcoop_login="owner";};
struct Character {
    struct Item {xr_string section;u16 parent=0,place=0;xr_string spawn;};
    xr_string account="owner",storage_request,storage_signature;unsigned slot=1;bool initialized=true,respawn=false;
    u32 storage_revision=1;xr_vector<Item> items,safe;
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
    assert(storage_execute(&server,&client,req).find("OK\n2|1|60|10|120\n")==0);
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
    CSE_ALifeInventoryItem root,incoming;root.s_name="rifle";incoming.s_name="huge";game.objects[10]=&root;game.objects[11]=&incoming;actor.children={10};
    assert(!server_inventory_can_take(&server,9,11));incoming.s_name="medkit";assert(server_inventory_can_take(&server,9,11));
    std::cout<<"Actual server transaction: authenticated owner/slot, replay/restart, signature, stale revision, failed save rollback, online/dead exclusion and capacity PASS\n";
}
