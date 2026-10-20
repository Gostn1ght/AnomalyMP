"""CI: replacing a task list must not let a map spot reach destroyed tasks.

Owner 2026-10-18 client crash: release_task_location -> MapLocationRelcase ->
HasGameTask walked tasks clear_tasks had already destroyed (null game_task).
"""
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
#include <vector>
typedef unsigned u32;
struct CMapLocation{};
struct CGameTask;
struct SGameTaskKey{CGameTask* game_task=nullptr;void destroy();};
typedef std::vector<SGameTaskKey> vGameTasks;
typedef vGameTasks::iterator vGameTasks_it;
enum ETaskState{eTaskStateInProgress};
struct CGameTaskManager{vGameTasks tasks;unsigned changed=0;vGameTasks& GetGameTasks(){return tasks;}void MarkChanged(){++changed;}
 CGameTask* HasGameTask(const CMapLocation* ml,bool only_inprocess);void MapLocationRelcase(CMapLocation* ml){HasGameTask(ml,false);}};
CGameTaskManager* level_manager=nullptr;unsigned removed=0;
struct CGameTask{CMapLocation spot;CMapLocation* linked=&spot;ETaskState state=eTaskStateInProgress;
 CMapLocation* LinkedMapLocation(){return linked;}ETaskState GetTaskState(){return state;}
 // Level().MapManager().RemoveMapLocation -> release_task_location
 void RemoveMapLocations(bool notify){if(linked&&!notify){++removed;level_manager->MapLocationRelcase(linked);}linked=nullptr;}};
void SGameTaskKey::destroy(){delete game_task;game_task=nullptr;}
''' + method('src/xrGame/GametaskManager.cpp','CGameTask* CGameTaskManager::HasGameTask(const CMapLocation* ml') + '\n' + method(
    'src/xrGame/netcoop_tasks.inc','static void clear_tasks(') + r'''
int main(){
 for(unsigned count:{0u,1u,2u,5u}){
  CGameTaskManager manager;level_manager=&manager;removed=0;
  for(unsigned i=0;i<count;++i){SGameTaskKey key;key.game_task=new CGameTask;manager.tasks.push_back(key);}
  clear_tasks(&manager);
  assert(manager.tasks.empty() && removed==count && manager.changed==1);
 }
 // A list that already holds a destroyed entry is searched safely too.
 CGameTaskManager manager;level_manager=&manager;manager.tasks.push_back(SGameTaskKey());
 CMapLocation other;assert(manager.HasGameTask(&other,false)==nullptr);
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native compilation is permitted only in GitHub Actions')
with TemporaryDirectory(prefix='task-clear-') as tmp:
    folder=Path(tmp);cpp=folder/'task_clear.cpp';exe=folder/'task_clear.exe';cpp.write_text(source,encoding='utf-8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)],cwd=folder,check=True)
    subprocess.run([str(exe)],cwd=folder,check=True,timeout=10)
print('PASS actual task list replacement: map spots of 0/1/2/5 tasks removed, no destroyed task searched')
