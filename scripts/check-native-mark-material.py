"""Actual decal/object invariant, including late blood marks on reused prop IDs."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/netcoop_marks.inc').read_text(encoding='utf-8')
helper=text[text.index('static bool mark_matches_object('):text.index('void client_marks_reset(')]
assert 'if (!mark_matches_object(object, texture)) return;' in text
assert 'if (mark_matches_object(object, mark.texture.c_str()))' in text
source=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
using LPCSTR=const char*;
struct CObject{virtual ~CObject()=default;};
struct CEntityAlive:CObject{};
struct Prop:CObject{};
template<class T>T smart_cast(const CObject* o){return dynamic_cast<T>(o);}
'''+helper+r'''
int main(){
 Prop box,barrel,fragment;CEntityAlive npc,corpse;
 const CObject* props[]={&box,&barrel,&fragment};
 const char* blood[]={"wm\\wm_blood_1","wm\\wm_bloodA5","wm\\wm_blood_drip_2"};
 for(const auto* o:props)for(const auto* t:blood)assert(!mark_matches_object(o,t));
 for(const auto* t:blood){assert(mark_matches_object(nullptr,t));assert(mark_matches_object(&npc,t));assert(mark_matches_object(&corpse,t));}
 for(const auto* o:props)assert(mark_matches_object(o,"wm\\wm_wood_1"));
 const CObject* reused=&corpse;assert(mark_matches_object(reused,blood[0]));reused=&fragment;assert(!mark_matches_object(reused,blood[0]));
 std::puts("PASS actual mark/object invariant: dynamic props/fragments reject blood including reused IDs; normal wood marks, organisms, corpses and static blood splashes retained; guard wired on server and client.");
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'mark.cpp';exe=Path(tmp)/('mark.exe' if os.name=='nt' else 'mark')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
             ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
