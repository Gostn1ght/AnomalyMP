#include "../src/xrGame/netcoop_storage_policy.h"
#include <cassert>
#include <string>
#include <iostream>
struct Item { std::string state; unsigned parent=0,place=0,cost=1; };
using Items=std::vector<Item>;
static unsigned cost(const Item& i) { return i.cost; }
static bool is_equipped(const Item& i) { return i.place!=0; }
int main()
{
    using namespace hideout_storage;
    Items bag={{"rifle:condition=.73,ammo=17",0,0,10},{"scope:condition=.9",1,0,2},{"battery:charge=.4",2,0,1},{"medkit",0,0,1},{"other-rifle",0,1,10},{"other-scope",5,0,2}};
    Items safe={{"food",0,0,1}};
    assert(cells(bag,cost)==21);
    assert(transfer(bag,safe,0,120,cost,is_equipped)==ok);
    assert(bag.size()==3 && safe.size()==4);
    assert(bag[2].parent==2 && safe[2].parent==2 && safe[3].parent==3);
    assert(safe[1].state=="rifle:condition=.73,ammo=17" && safe[2].state=="scope:condition=.9");
    assert(transfer(safe,bag,1,60,cost,[](const Item&){return false;})==ok);
    assert(bag.size()==6 && safe.size()==1 && bag[4].parent==4 && bag[5].parent==5);
    assert(transfer(bag,safe,1,120,cost,is_equipped)==Result::equipped);
    assert(transfer(bag,safe,4,120,cost,is_equipped)==unavailable);
    assert(transfer(bag,safe,6,120,cost,is_equipped)==unavailable);
    assert(transfer(bag,safe,3,10,cost,is_equipped)==full);
    assert(bag.size()==6 && safe.size()==1);
    // Corrupt parents fail before any mutation.
    Items broken={{"a",0,0,1},{"b",4,0,1}};
    assert(transfer(broken,safe,0,120,cost,is_equipped)==corrupt && broken.size()==2 && safe.size()==1);
    Items maximum(512,Item{"root",0,0,1}), one={{"nested-root",0,0,1},{"nested-child",1,0,1}};
    assert(transfer(one,maximum,0,10000,cost,is_equipped)==full && maximum.size()==512 && one.size()==2);
    Items a={{"edge",0,0,60}},b;
    assert(transfer(a,b,0,60,cost,is_equipped)==ok && cells(b,cost)==60);
    std::cout<<"Storage policy: subtree identity, indices, state/ammo, equipped, capacity, corruption, no mutation on rejection PASS\n";
}
