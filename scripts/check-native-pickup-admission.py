"""CI: real pickup admission and the engine vector's real constructors."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]


def method(text, signature):
    start = text.index(signature)
    begin = text.index('{', start)
    depth, end = 1, begin + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


vector = (root/'src/xrCore/_stl_extensions.h').read_text(encoding='utf-8')
start = vector.index('template <typename T, typename allocator = xalloc<T>>')
# Keep the actual class/constructors, with an ordinary allocator in this fixture.
vector = vector[start:vector.index('\n\tu32 size()', start)] + '\n};\n'
vector = vector.replace('xalloc<T>', 'std::allocator<T>')
storage = (root/'src/xrGame/netcoop_storage.inc').read_text(encoding='utf-8')
actual = '\n'.join(method(storage, signature) for signature in (
    'static bool storage_count_tree(', 'static bool storage_inventory_room(',
    'LPCSTR server_inventory_take_failure('))
source = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <vector>
#include <cstring>
using u16=uint16_t;using u32=uint32_t;using LPCSTR=const char*;
''' + vector + r'''
template<class T,class U>T smart_cast(U* p){return dynamic_cast<T>(p);}
struct CSE_Abstract{virtual ~CSE_Abstract()=default;u16 ID=0,ID_Parent=u16(-1);xr_vector<u16> children;};
struct CSE_ALifeInventoryItem{virtual ~CSE_ALifeInventoryItem()=default;};
struct Item:CSE_Abstract,CSE_ALifeInventoryItem{};
struct CSE_ALifeCreatureActor:CSE_Abstract{};
struct Game{std::map<u16,CSE_Abstract*> objects;CSE_Abstract* get_entity_from_eid(u16 id){auto i=objects.find(id);return i==objects.end()?nullptr:i->second;}};
struct xrServer{Game* game;};
bool active=true;bool enabled(){return active;}
''' + actual + r'''
int main(){
 Game game;xrServer server{&game};CSE_ALifeCreatureActor anchor,actor,corpse;
 anchor.ID=0;actor.ID=29194;corpse.ID=23837;
 Item loot,carried;loot.ID=65534;loot.ID_Parent=corpse.ID;carried.ID=301;carried.ID_Parent=actor.ID;
 game.objects={{0,&anchor},{actor.ID,&actor},{corpse.ID,&corpse},{loot.ID,&loot},{carried.ID,&carried}};
 actor.children.push_back(carried.ID);corpse.children.push_back(loot.ID);
 // This is the actual old failure, invisible when xr_vector is mocked as std::vector.
 xr_vector<u16> wrong{loot.ID};assert(wrong.size()==65534 && wrong[0]==0);
 assert(!storage_inventory_room(&server,&actor,wrong));
 assert(!server_inventory_take_failure(&server,actor.ID,loot.ID)); // corpse -> player
 loot.ID_Parent=u16(-1);assert(!server_inventory_take_failure(&server,actor.ID,loot.ID)); // floor -> player
 assert(!server_inventory_take_failure(&server,actor.ID,carried.ID)); // idempotent owner
 // No transaction may pass an incomplete/cyclic/misparented inventory.
 actor.children.push_back(999);assert(server_inventory_take_failure(&server,actor.ID,loot.ID));actor.children.pop_back();
 carried.ID_Parent=corpse.ID;assert(server_inventory_take_failure(&server,actor.ID,loot.ID));carried.ID_Parent=actor.ID;
 carried.children.push_back(carried.ID);assert(server_inventory_take_failure(&server,actor.ID,loot.ID));carried.children.clear();
 std::vector<Item> full(512);actor.children.clear();
 for(unsigned i=0;i<full.size();++i){full[i].ID=u16(1000+i);full[i].ID_Parent=actor.ID;game.objects[full[i].ID]=&full[i];actor.children.push_back(full[i].ID);}
 assert(std::strstr(server_inventory_take_failure(&server,actor.ID,loot.ID),"512"));
 actor.children.pop_back();assert(!server_inventory_take_failure(&server,actor.ID,loot.ID)); // 511 + incoming
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='pickup-admission-') as tmp:
    folder=Path(tmp);cpp=folder/'pickup.cpp';exe=folder/'pickup.exe'
    cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
print('PASS actual pickup: engine vector constructor, high IDs, floor/corpse transfers, idempotency, corrupt trees and 512-item boundary')
