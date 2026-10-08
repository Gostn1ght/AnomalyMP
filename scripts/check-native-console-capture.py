"""Actual player classifier: local capture/startup preferences, gameplay denied."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,re,subprocess

if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
text=(root/'src/xrEngine/XR_IOConsole.cpp').read_text(encoding='latin-1')
start=text.index('static bool player_internal_command(')
method=text[start:text.index('\nvoid CConsole::ExecuteCommand',start)]
assert method.count('"screenshot", "r_screenshot_mode",')==1
assert method.count('"g_always_active",')==1
assert method.count('"keypress_on_start",')==1
legacy=method.replace('        "screenshot", "r_screenshot_mode",\n','',1).replace('        "g_always_active", "keypress_on_start",\n','',1).replace('static bool player_internal_command(','static bool legacy_player_internal_command(',1)
assert legacy!=method
names=set(re.findall(r'"([A-Za-z0-9_]+)"',method))
names.update(['god','g_god','noclip','g_noclip','ph_gravity','time_factor','power_loss_bias',
              'screenshot_all','dbg_make_screenshot','r_debug_ai','netcoop_seed_inventory',
              'r2_wireframe','shader_param_wireframe','unknown_command','start'])
name_literals=','.join('"'+name+'"' for name in sorted(names))
source=r'''
#include <cassert>
#include <cstring>
#include <iostream>
#include <initializer_list>
#ifndef _WIN32
#include <strings.h>
#define _strnicmp strncasecmp
#endif
using LPCSTR=const char*;
int xr_strcmp(LPCSTR a,LPCSTR b){return std::strcmp(a,b);}
'''+method+'\n'+legacy+'\n'+r'''
int main(){
 const char* names[]={NAMES};
 const char* args[]={"","capture_guid","0","1","2","client(localhost)","server(all)",
   "client(localhost/server(all))","CLIENT(localhost/SERVER(all))"};
 unsigned cases=0;
 for(const char* name:names)for(const char* arg:args){
  const bool now=player_internal_command(name,arg);
  const bool old=legacy_player_internal_command(name,arg);
  if(!std::strcmp(name,"screenshot") || !std::strcmp(name,"r_screenshot_mode") ||
     !std::strcmp(name,"g_always_active") || !std::strcmp(name,"keypress_on_start")){
   assert(now && !old);
  }else assert(now==old);
  ++cases;
 }
 for(const char* cheat:{"god","g_god","noclip","g_noclip","ph_gravity","time_factor",
      "power_loss_bias","screenshot_all","dbg_make_screenshot","r_debug_ai","netcoop_seed_inventory"})
  assert(!player_internal_command(cheat,"1"));
 assert(player_internal_command("start","client(localhost)"));
 assert(!player_internal_command("start","server(all)"));
 assert(!player_internal_command("start","client(localhost/server(all))"));
 assert(!player_internal_command("r2_wireframe","1"));
 std::cout<<"PASS actual console classifier "<<cases<<" differential cases: only local screenshot/format/startup preferences added; gameplay/server/debug commands remain denied\n";
}
'''.replace('NAMES',name_literals)
with TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'capture.cpp';exe=Path(tmp)/('capture.exe' if os.name=='nt' else 'capture')
    cpp.write_text(source,encoding='utf-8')
    command=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt' else
        ['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)])
    subprocess.run(command,cwd=tmp,check=True);subprocess.run([str(exe)],cwd=tmp,check=True)
