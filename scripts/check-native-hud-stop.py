"""Actual StopScriptAnim: preserve cleanup and diagnose only invalid states."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/player_hud.cpp').read_text()
begin=text.index('void player_hud::StopScriptAnim()')
method=text[begin:text.index('\nu32 player_hud::anim_play',begin)]
assert method.count('part > 2 && part != u8(-1)')==1
legacy=method.replace('part > 2 && part != u8(-1)','part > 2').replace('player_hud::StopScriptAnim()','player_hud::LegacyStop()')
source=r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
#include <iostream>
using u8=std::uint8_t;
namespace ACTOR_DEFS {enum EMoveCommand {None};}
std::vector<std::string> trace;
bool print_bone_warnings=true;
void Msg(const char* format,u8 part){
 assert(std::string(format)=="![player_hud::StopScriptAnim()] invalid script_anim_part %d, must be < 3");
 trace.push_back("warning:"+std::to_string(part));
}
struct Script {void print_stack(){trace.push_back("stack");}} script;
struct AI {Script& script_engine(){return script;}} space;
AI& ai(){return space;}
struct player_hud {
 u8 script_anim_part=0;void* script_anim_item_model=nullptr;
 bool script_anim_lead_gun=true;void* m_attached_items[2]={nullptr,nullptr};
 void updateMovementLayerState(){trace.push_back("layers");}
 void re_sync_anim(int part){trace.push_back("resync:"+std::to_string(part));}
 void OnMovementChanged(ACTOR_DEFS::EMoveCommand value){assert(value==0);trace.push_back("movement");}
 void StopScriptAnim();void LegacyStop();
};
''' + method + '\n' + legacy + '\n' + r'''
int main(){
 int item=1;unsigned cases=0;
 for(unsigned part=0;part<256;++part)for(unsigned mask=0;mask<4;++mask)for(unsigned warnings=0;warnings<2;++warnings){
  player_hud now,old;
  now.script_anim_part=old.script_anim_part=static_cast<u8>(part);
  now.script_anim_item_model=old.script_anim_item_model=&item;
  for(unsigned i=0;i<2;++i)now.m_attached_items[i]=old.m_attached_items[i]=(mask & (1u<<i))?&item:nullptr;
  print_bone_warnings=warnings!=0;
  trace.clear();old.LegacyStop();auto reference=trace;
  trace.clear();now.StopScriptAnim();
  if(part==255 && warnings){
   assert(reference.size()==4 && reference[1]=="warning:255" && reference[2]=="stack");
   reference.erase(reference.begin()+1,reference.begin()+3);
  }
  assert(trace==reference);
  assert(now.script_anim_part==u8(-1) && old.script_anim_part==u8(-1));
  assert(!now.script_anim_item_model && !old.script_anim_item_model);
  assert(!now.script_anim_lead_gun && !old.script_anim_lead_gun);
  ++cases;
 }
 assert(cases==2048);
 std::cout<<"PASS actual HUD stop2048 differential cases; normal255 silent, invalid3..254 preserved, all cleanup callbacks unchanged\n";
}
'''
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'hud.cpp';exe=Path(tmp)/('hud.exe' if os.name=='nt' else 'hud')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
