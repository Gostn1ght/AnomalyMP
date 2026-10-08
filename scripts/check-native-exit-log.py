"""Exercise actual do_exit logging, flush, dialog and termination ordering."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os,subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root=Path(__file__).resolve().parents[1]
for filename in ['xrDebug.cpp','xrDebugNew.cpp']:
    text=(root/'src/xrCore'/filename).read_text()
    start=text.index('void xrDebug::do_exit(const std::string& message)')
    method=text[start:text.index('\n}',start)+2]
    source=r'''
#include <cassert>
#include <string>
#include <vector>
#include <iostream>
struct xrDebug {void do_exit(const std::string&);};
std::vector<std::string> events;
std::string reason;
constexpr int MB_OK=1,MB_ICONERROR=2,MB_SYSTEMMODAL=4;
struct Terminated {};
void Msg(const char* format,const char* value){
 assert(std::string(format)=="! [X-Ray][exit] %s");
 assert(std::string(value)==reason);events.push_back("log");
}
void FlushLog(){events.push_back("flush");}
void MessageBox(void* window,const char* message,const char* title,int flags){
 assert(!window && std::string(message)==reason && std::string(title)=="Error");
 assert(flags==(MB_OK|MB_ICONERROR|MB_SYSTEMMODAL));events.push_back("dialog");
}
void* GetCurrentProcess(){return &events;}
void TerminateProcess(void* process,int code){
 assert(process==&events && code==1);events.push_back("terminate");throw Terminated{};
}
''' + method + r'''
int main(){
 for(const std::string value:{"", "world is locked or lock file is inaccessible", "missing archive %s %n", "invalid path\nsecond line"}){
  events.clear();reason=value;xrDebug debug;bool stopped=false;
  try{debug.do_exit(reason);}catch(const Terminated&){stopped=true;}
  assert(stopped);
  assert((events==std::vector<std::string>{"log","flush","dialog","terminate"}));
 }
 std::cout<<"PASS actual do_exit: logged reason before flush, unchanged dialog/exit\n";
}
'''
    with TemporaryDirectory() as tmp:
        cpp=Path(tmp)/'exit.cpp';exe=Path(tmp)/('exit.exe' if os.name=='nt' else 'exit')
        cpp.write_text(source,encoding='utf-8')
        if os.name=='nt':
            command=['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)]
        else:
            command=['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)]
        subprocess.run(command,cwd=tmp,check=True)
        subprocess.run([str(exe)],cwd=tmp,check=True)
