"""CI-only actual carry-weight methods feed the authoritative cells policy."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]


def function(path, marker):
    source = (root/path).read_text(encoding='utf-8')
    start = source.index(marker)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


characters = (root/'src/xrGame/netcoop_characters.inc').read_text(encoding='utf-8')
assert 'character.inventory_cells = storage_live_capacity(runtime);' in characters
assert 'fwrite(&character.inventory_cells,4,1,f)' in characters
source = r'''
#include <cassert>
#include <cmath>
#include <limits>
#include <vector>
#include <algorithm>
using u32=unsigned;const int BACKPACK_SLOT=13;
template<class T>T _min(T a,T b){return std::min(a,b);}
template<class T>T _max(T a,T b){return std::max(a,b);}
template<class T,class U>T smart_cast(U* value){return dynamic_cast<T>(value);}
bool _valid(float weight){return std::isfinite(weight);}
struct Item {virtual ~Item()=default;};
struct CCustomOutfit {float m_additional_weight=5;};
struct CBackpack:Item {float m_additional_weight=20;};
struct CArtefact:Item {float weight=10,condition=.5f;float AdditionalInventoryWeight(){return weight;}float GetCondition(){return condition;}};
using TIItemContainer=std::vector<Item*>;
struct Inventory {float weight=40;Item* backpack=nullptr;TIItemContainer m_belt;float GetMaxWeight()const{return weight;}
 Item* ItemFromSlot(int slot)const{assert(slot==BACKPACK_SLOT);return backpack;}};
struct Conditions {float boost=0;float GetCarryWeightBoost()const{return boost;}};
struct CActor {Inventory bag;Conditions stats;CCustomOutfit* outfit=nullptr;
 const Inventory& inventory()const{return bag;}const Conditions& conditions()const{return stats;}
 CCustomOutfit* GetOutfit()const{return outfit;}float MaxCarryWeight()const;float get_additional_weight()const;};
u32 storage_capacity(bool safe){assert(!safe);return 120;}
''' + function('src/xrGame/Actor_Movement.cpp', 'float CActor::MaxCarryWeight() const') + '\n' + function(
    'src/xrGame/Actor_Movement.cpp', 'float CActor::get_additional_weight() const') + '\n' + function(
    'src/xrGame/netcoop_storage.inc', 'static u32 storage_live_capacity(CActor* actor)') + r'''
int main(){
 CActor actor;CCustomOutfit outfit;CBackpack backpack;CArtefact artifact;Item ordinary;
 assert(storage_live_capacity(nullptr)==120 && storage_live_capacity(&actor)==160);
 actor.outfit=&outfit;assert(storage_live_capacity(&actor)==180);
 actor.bag.backpack=&backpack;assert(storage_live_capacity(&actor)==260);
 actor.stats.boost=10;assert(storage_live_capacity(&actor)==300);
 actor.bag.m_belt={&artifact,&ordinary};assert(storage_live_capacity(&actor)==320);
 outfit.m_additional_weight=20;assert(storage_live_capacity(&actor)==380);
 artifact.condition=0;assert(storage_live_capacity(&actor)==360);
 actor.bag.weight=1000;assert(storage_live_capacity(&actor)==512);
 actor.bag.weight=std::numeric_limits<float>::quiet_NaN();assert(storage_live_capacity(&actor)==120);
 actor.bag.weight=-1000;assert(storage_live_capacity(&actor)==120);
 actor.outfit=nullptr;actor.bag.backpack=nullptr;actor.stats.boost=0;actor.bag.m_belt.clear();
 actor.bag.weight=40.24f;assert(storage_live_capacity(&actor)==160);
 actor.bag.weight=40.25f;assert(storage_live_capacity(&actor)==161);
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='carry-capacity-') as temporary:
    folder = Path(temporary)
    cpp = folder/'carry.cpp'
    exe = folder/('carry.exe' if os.name == 'nt' else 'carry')
    cpp.write_text(source, encoding='utf-8')
    command = (['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name == 'nt' else
               ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True)
print('PASS actual native carry-weight/cells: armor, backpack, upgrades, booster, belt condition, floor, cap and invalid inputs')
