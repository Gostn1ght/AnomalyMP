"""CI: actual remote NPC release path must not enter unbound AI memory."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root=Path(__file__).resolve().parents[1]


def method(path, signature):
    text=(root/path).read_text(encoding='utf-8')
    start=text.index(signature);begin=text.index('{',start);depth,end=1,begin+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


source=r'''
#include <cassert>
#include <initializer_list>
bool client=true;namespace netcoop{bool pure_client(){return client;}}
struct CObject{};
struct Links{unsigned calls=0;bool bound=true;void remove_links(CObject*){assert(bound);++calls;}};
struct Physics{unsigned calls=0;void in_NetRelcase(CObject*){++calls;}};
struct Base{unsigned generic=0;void net_Relcase(CObject*){++generic;}};
struct CCustomMonster:Base{using inherited=Base;bool remote=true;Links mem;
 bool Remote(){return remote;}Links& memory(){return mem;}void net_Relcase(CObject*);};
struct CAI_Stalker:CCustomMonster{using inherited=CCustomMonster;bool alive=true;Links see,move,agent;Physics physics;Physics* m_pPhysics_support=&physics;
 bool g_Alive(){return alive;}Links& sight(){return see;}Links& movement(){return move;}Links& agent_manager(){return agent;}void net_Relcase(CObject*);};
''' + method('src/xrGame/CustomMonster.cpp','void CCustomMonster::net_Relcase(') + '\n' + method(
    'src/xrGame/ai/stalker/ai_stalker.cpp','void CAI_Stalker::net_Relcase(') + r'''
int main(){
 CObject disappearing_pda;
 for(bool alive:{false,true}){
  CAI_Stalker replica;replica.alive=alive;
  replica.mem.bound=replica.see.bound=replica.move.bound=replica.agent.bound=false;
  replica.net_Relcase(&disappearing_pda);
  assert(replica.generic==1 && replica.physics.calls==1);
  assert(!replica.mem.calls && !replica.see.calls && !replica.move.calls && !replica.agent.calls);
 }
 // Authoritative server and local/SP NPCs retain their normal AI cleanup.
 for(bool remote:{false,true}){
  client=false;CAI_Stalker authoritative;authoritative.remote=remote;authoritative.net_Relcase(&disappearing_pda);
  assert(authoritative.generic==1 && authoritative.mem.calls==1 && authoritative.see.calls==1);
  assert(authoritative.move.calls==1 && authoritative.agent.calls==1 && authoritative.physics.calls==1);
 }
 client=true;CAI_Stalker local;local.remote=false;local.net_Relcase(&disappearing_pda);
 assert(local.mem.calls==1 && local.agent.calls==1 && local.physics.calls==1);
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='replica-relcase-') as tmp:
    folder=Path(tmp);cpp=folder/'relcase.cpp';exe=folder/'relcase.exe';cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
print('PASS actual NPC release: remote living/dead replicas, generic/physics cleanup, server/SP AI links')
