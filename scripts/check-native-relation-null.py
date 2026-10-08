"""Actual relation API nil target regression from the retained native server dump."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/script_game_object_use.cpp').read_text(encoding='latin-1')
start=text.index('ALife::ERelationType CScriptGameObject::GetRelationType(')
method=text[start:text.index('template <typename T>',start)]
source=r'''
#include <cassert>
#include <cstdio>
namespace ALife{enum ERelationType:unsigned{eRelationTypeFriend=0,eRelationTypeNeutral=1,eRelationTypeEnemy=2,eRelationTypeDummy=0xffffffffu};}
namespace ScriptStorage{constexpr int eLuaMessageTypeError=1;}
struct Name{const char* operator*()const{return "test entity";}};
struct CGameObject{virtual ~CGameObject()=default;Name cName()const{return {};}};
struct CEntityAlive:CGameObject{
 ALife::ERelationType result=ALife::eRelationTypeNeutral;CEntityAlive* last=nullptr;unsigned calls=0;
 ALife::ERelationType tfGetRelationType(CEntityAlive* target){last=target;++calls;return result;}
};
template<class T>T smart_cast(CGameObject* o){return dynamic_cast<T>(o);}
struct Engine{unsigned logs=0;template<class... T>void script_log(int,const char*,T...){++logs;}}engine;
struct AI{Engine& script_engine(){return engine;}}ai_instance;AI& ai(){return ai_instance;}
struct CScriptGameObject{
 CGameObject* value=nullptr;mutable unsigned object_reads=0;
 CGameObject& object()const{++object_reads;assert(value);return *value;}
 ALife::ERelationType GetRelationType(CScriptGameObject* who);
};
'''+method+r'''
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
 std::puts("PASS actual GetRelationType: nil target does not dereference; friend/neutral/enemy forwarding and non-entity contract retained");
}
'''
source=source.replace('#include <cstdio>','#include <cstdio>\n#include <initializer_list>')
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'relation.cpp';exe=Path(tmp)/('relation.exe' if os.name=='nt' else 'relation')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
