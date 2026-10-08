"""Actual nil-target relation/visibility APIs from retained native server failures."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/script_game_object_use.cpp').read_text(encoding='latin-1')
start=text.index('ALife::ERelationType CScriptGameObject::GetRelationType(')
method=text[start:text.index('template <typename T>',start)]
visibility=(root/'src/xrGame/script_game_object.cpp').read_text(encoding='latin-1')
vstart=visibility.index('bool CScriptGameObject::CheckObjectVisibility(')
visibility=visibility[vstart:visibility.index('//////////////////////////////////////////////////////////////////////////',vstart)]
type_visibility=(root/'src/xrGame/script_game_object3.cpp').read_text(encoding='latin-1')
tstart=type_visibility.index('bool CScriptGameObject::CheckTypeVisibility(')
type_visibility=type_visibility[tstart:type_visibility.index('CScriptGameObject* CScriptGameObject::GetCurrentWeapon()',tstart)]
source=r'''
#include <cassert>
#include <cstdio>
namespace ALife{enum ERelationType:unsigned{eRelationTypeFriend=0,eRelationTypeNeutral=1,eRelationTypeEnemy=2,eRelationTypeDummy=0xffffffffu};}
namespace ScriptStorage{constexpr int eLuaMessageTypeError=1;}
struct Name{const char* operator*()const{return "test entity";}};
struct CGameObject{virtual ~CGameObject()=default;Name cName()const{return {};}};
struct CEntityAlive:CGameObject{
 bool alive=true;bool g_Alive()const{return alive;}
 ALife::ERelationType result=ALife::eRelationTypeNeutral;CEntityAlive* last=nullptr;unsigned calls=0;
 ALife::ERelationType tfGetRelationType(CEntityAlive* target){last=target;++calls;return result;}
};
struct CScriptEntity:CEntityAlive{
 bool seen=true;unsigned visions=0;const CGameObject* last_seen=nullptr;
 bool CheckObjectVisibility(const CGameObject* o){++visions;last_seen=o;return seen;}
};
struct CCustomMonster:CScriptEntity{unsigned sections=0;const char* last_section=nullptr;
 bool CheckTypeVisibility(const char* sec){++sections;last_section=sec;return seen;}};
struct Visual{bool seen=true;unsigned calls=0;const CGameObject* last=nullptr;
 bool visible_now(const CGameObject* o){++calls;last=o;return seen;}};
struct Memory{Visual value;Visual& visual(){return value;}};
struct CActor:CEntityAlive{Memory value;Memory& memory(){return value;}};
template<class T>T smart_cast(CGameObject* o){return dynamic_cast<T>(o);}
struct Engine{unsigned logs=0;template<class... T>void script_log(int,const char*,T...){++logs;}}engine;
struct AI{Engine& script_engine(){return engine;}}ai_instance;AI& ai(){return ai_instance;}
struct CScriptGameObject{
 CGameObject* value=nullptr;mutable unsigned object_reads=0;
 CGameObject& object()const{++object_reads;assert(value);return *value;}
 ALife::ERelationType GetRelationType(CScriptGameObject* who);
 bool CheckObjectVisibility(const CScriptGameObject* who);
 bool CheckTypeVisibility(const char* section);
};
'''+method+visibility+type_visibility+r'''
int main(){
 CEntityAlive a,b;CGameObject other;CScriptGameObject self,target,invalid;
 self.value=&a;target.value=&b;invalid.value=&other;
 assert(self.GetRelationType(nullptr)==ALife::eRelationTypeDummy);
 assert(self.object_reads==0&&a.calls==0&&engine.logs==0);
 for(const auto relation:{ALife::eRelationTypeFriend,ALife::eRelationTypeNeutral,ALife::eRelationTypeEnemy}){
  a.result=relation;assert(self.GetRelationType(&target)==relation&&a.last==&b);
 }
 assert(a.calls==3);
 assert(self.GetRelationType(&invalid)==ALife::eRelationTypeDummy&&a.calls==3);
 assert(invalid.GetRelationType(&target)==ALife::eRelationTypeDummy&&a.calls==3);
 assert(engine.logs==2);
 CCustomMonster npc;CActor actor;CScriptGameObject n,ac;n.value=&npc;ac.value=&actor;
 assert(!n.CheckObjectVisibility(nullptr)&&!n.CheckTypeVisibility(nullptr));
 assert(n.object_reads==0&&npc.visions==0&&npc.sections==0&&engine.logs==2);
 for(bool seen:{false,true}){
  npc.seen=seen;actor.value.value.seen=seen;
  assert(n.CheckObjectVisibility(&target)==seen&&npc.last_seen==&b);
  assert(n.CheckTypeVisibility("wpn_pm")==seen);
  assert(ac.CheckObjectVisibility(&target)==seen&&actor.value.value.last==&b);
 }
 assert(npc.visions==2&&npc.sections==2&&actor.value.value.calls==2);
 npc.alive=false;assert(!n.CheckObjectVisibility(&target)&&npc.visions==2);
 assert(!invalid.CheckObjectVisibility(&target)&&!invalid.CheckTypeVisibility("wpn_pm"));
 assert(engine.logs==5);
 std::puts("PASS actual relation/visibility: nil targets do not dereference; relation results, NPC/actor visibility and section queries retained; dead/non-entity contracts retained");
}
'''
source=source.replace('#include <cstdio>','#include <cstdio>\n#include <initializer_list>')
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'relation.cpp';exe=Path(tmp)/('relation.exe' if os.name=='nt' else 'relation')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
