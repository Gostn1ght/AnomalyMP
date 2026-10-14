"""CI only: real player-map visibility, Lua permission and map rendering guard."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]
policy = (root/'src/xrGame/netcoop_map.inc').read_text(encoding='utf-8-sig')
location = (root/'src/xrGame/map_location.cpp').read_text(encoding='utf-8-sig')
guard = location[location.index('void CMapLocation::UpdateSpot('):location.index('\tif (map->MapName() == GetLevelName())')]
assert 'map_player_forget(ID())' in (root/'src/xrGame/Actor_Network.cpp').read_text(encoding='utf-8-sig')
assert 'map_players_reset();' in (root/'src/xrGame/Level_network.cpp').read_text(encoding='utf-8-sig')
source = r'''
#include <cassert>
#include <cstring>
#include <map>
#include <string>
using u16=unsigned short;using LPCSTR=const char*;
template<class K,class V>using xr_map=std::map<K,V>;
int xr_strcmp(LPCSTR a,LPCSTR b){return std::strcmp(a,b);}
struct Object {virtual ~Object()=default;};
struct CActor:Object {std::string name;explicit CActor(const char* n):name(n){}LPCSTR Name()const{return name.c_str();}};
template<class T>T smart_cast(Object* p){return dynamic_cast<T>(p);}
std::map<u16,Object*> objects;CActor* own=nullptr;bool client=true;
struct ObjectRegistry {Object* net_Find(u16 id){auto it=objects.find(id);return it==objects.end()?nullptr:it->second;}};
struct LevelMock {ObjectRegistry Objects;} level;
LevelMock& Level(){return level;}CActor* Actor(){return own;}
namespace netcoop {bool pure_client(){return client;}
''' + policy + r'''
}
struct CUICustomMap {};struct CMapSpot {};
struct CMapLocation {
 u16 m_objectID=0;LPCSTR spot_type="actor_location";int drawn=0;
 void UpdateSpot(CUICustomMap*,CMapSpot*);
};
''' + guard + r'''
 (void)map;(void)sp;++drawn;
}
int main(){
 CActor anchor("authority"),self("self"),buddy("friend"),stranger("other"),replacement("friend");Object npc;
 own=&self;objects={{u16(0),&anchor},{u16(7),&self},{u16(8),&buddy},{u16(9),&stranger},{u16(10),&npc}};
 assert(netcoop::map_player_visible(7,false));
 assert(!netcoop::map_player_visible(0,false) && !netcoop::map_player_visible(8,false) && !netcoop::map_player_visible(9,false));
 assert(netcoop::map_player_visible(10,false) && netcoop::map_player_visible(99,false));
 assert(!netcoop::map_player_visible(99,true));
 assert(!netcoop::script_map_friend(8,"wrong") && !netcoop::script_map_friend(10,"friend"));
 assert(!netcoop::script_map_friend(0,"authority") && !netcoop::script_map_friend(65535,"friend") && !netcoop::script_map_friend(-1,"friend"));
 assert(!netcoop::script_map_friend(8,nullptr) && !netcoop::script_map_friend(8,""));
 assert(netcoop::script_map_friend(8,"friend") && netcoop::map_player_visible(8,true));
 objects[8]=&replacement;assert(!netcoop::map_player_visible(8,true));
 objects[8]=&buddy;netcoop::map_player_forget(8);assert(!netcoop::map_player_visible(8,true));
 assert(netcoop::script_map_friend(8,"friend"));netcoop::map_players_reset();assert(!netcoop::map_player_visible(8,true));
 CMapLocation spot;CUICustomMap map;CMapSpot icon;
 spot.m_objectID=9;spot.UpdateSpot(&map,&icon);assert(spot.drawn==0);
 spot.m_objectID=7;spot.UpdateSpot(&map,&icon);assert(spot.drawn==1);
 spot.m_objectID=8;assert(netcoop::script_map_friend(8,"friend"));spot.UpdateSpot(&map,&icon);assert(spot.drawn==2);
 spot.m_objectID=99;spot.UpdateSpot(&map,&icon);assert(spot.drawn==2);
 spot.spot_type="actor_location_p";spot.UpdateSpot(&map,&icon);assert(spot.drawn==2);
 spot.spot_type="quest";spot.UpdateSpot(&map,&icon);assert(spot.drawn==3);
 client=false;assert(netcoop::map_player_visible(0,true) && netcoop::map_player_visible(9,true));
 assert(!netcoop::script_map_friend(9,"other"));spot.m_objectID=9;spot.UpdateSpot(&map,&icon);assert(spot.drawn==4);
}
'''
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native fixture compiles only in GitHub Actions; no local compiler invocation.')
with TemporaryDirectory(prefix='map-privacy-') as temporary:
    folder = Path(temporary)
    cpp = folder/'map.cpp'
    exe = folder/('map.exe' if os.name == 'nt' else 'map')
    cpp.write_text(source, encoding='utf-8')
    args = (['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name == 'nt' else
            ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(args,cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True)
print('PASS actual map privacy: self/mutual friend, hidden strangers/anchor, pending spawn, reused ID, destroy/reset, NPC/quest and single-player preservation')
