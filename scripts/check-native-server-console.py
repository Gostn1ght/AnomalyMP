"""CI-only: actual sv_cmd adapter, trusted local role and client rejection."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]
text = (root / "src/xrGame/console_commands.cpp").read_text(encoding="utf-8-sig")
start = text.index("class CCC_NetAnomalySvCmd :")
end = text.index("void CCC_RegisterCommands()", start)
adapter = text[start:end]
source = r'''
#include <cassert>
#include <cstring>
#include <stdexcept>
#include <string>
using LPCSTR=const char*;
constexpr bool TRUE=true;
struct IConsole_Command {bool bEmptyArgsHandled=false; explicit IConsole_Command(LPCSTR){};virtual ~IConsole_Command()=default;virtual void Execute(LPCSTR)=0;};
static int calls=0;static bool loaded=true,fail=false;
static std::string last;
static unsigned xr_strlen(LPCSTR s){return unsigned(std::strlen(s));}
static void Msg(LPCSTR format,LPCSTR value=nullptr){last=value?value:format;}
static void* g_pGameLevel=nullptr;
struct TestLevel {void* Server=nullptr;} level;
static TestLevel& Level(){return level;}
namespace luabind {
template<class T> struct functor {
 T operator()(LPCSTR cid,LPCSTR name,int entity,LPCSTR command,LPCSTR role)const {
  ++calls;
  assert(!std::strcmp(cid,"console") && !std::strcmp(name,"CONSOLE") && entity==65535);
  assert(!std::strcmp(command,"approve_registration guest") && !std::strcmp(role,"admin"));
  if(fail)throw std::runtime_error("test handler failure");
  return "registration guest approved";
 }
};
}
struct Engine {
 template<class T>bool functor(LPCSTR name,luabind::functor<T>&) {
  assert(!std::strcmp(name,"netanomaly_server.on_client_command"));return loaded;
 }
} engine;
struct AI {Engine& script_engine(){return engine;}} ai_instance;
static AI& ai(){return ai_instance;}
'''+adapter+r'''
int main(){
 CCC_NetAnomalySvCmd command("sv_cmd");
 command.Execute("");assert(calls==0);
 command.Execute("approve_registration guest");assert(calls==0 && last.find("not a server")!=std::string::npos);
 g_pGameLevel=&level;command.Execute("approve_registration guest");assert(calls==0);
 level.Server=&level;loaded=false;command.Execute("approve_registration guest");assert(calls==0 && last.find("not loaded")!=std::string::npos);
 loaded=true;command.Execute("approve_registration guest");assert(calls==1 && last=="registration guest approved");
 fail=true;command.Execute("approve_registration guest");assert(calls==2 && last.find("script error")!=std::string::npos);
}
'''

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native fixture compiles only in GitHub Actions; no local engine/compiler invocation.")
with TemporaryDirectory(prefix="server-console-") as temporary:
    folder = Path(temporary)
    cpp = folder / "console.cpp"
    exe = folder / ("console.exe" if os.name == "nt" else "console")
    cpp.write_text(source, encoding="utf-8")
    args = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:"+str(exe)]
            if os.name == "nt" else
            ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(args, cwd=folder, check=True)
    subprocess.run([str(exe)], cwd=folder, check=True)
print("PASS actual sv_cmd: local server supplies admin role, pure clients/missing handlers rejected, exceptions contained")
