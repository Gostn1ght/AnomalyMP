"""CI only: execute the actual admission prefix of finish_auth, including bans."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

root=Path(__file__).resolve().parents[1]
text=(root/'src/xrGame/netcoop.cpp').read_text(encoding='utf-8-sig')
start=text.index('static bool finish_auth(')
end=text.index('    // Slot zero authenticates',start)
admission=text[start:end]+'    return false;\n}\n' # the world master phase follows the prefix (doc 135)
source=r'''
#include <algorithm>
#include <cassert>
#include <cctype>
#include <map>
#include <string>
using u32=unsigned;using LPCSTR=const char*;using xr_string=std::string;
enum Role {role_none,role_player,role_admin};
struct Account {
 xr_string login,salt,hash,device,firebase_uid;Role role=role_player;
 unsigned approval=1,money=0,failures=0,locked_until=0;bool touched=false,has_money=false;
};
struct xrClientData {unsigned ID=1;xr_string netcoop_login;Role netcoop_role=role_none;};
struct PendingAuth {
 unsigned client=1;xr_string login="Player",salt="fixture-salt",hash="fixture-digest",device="fixture-device",firebase_uid;
 bool create=false,hashed=true,firebase=false,claim=false;
};
struct LoginInUse {xr_string login;xrClientData* self=nullptr;};
std::map<xr_string,Account> s_accounts;bool s_accounts_dirty=false;
xrClientData test_client;unsigned saves=0;xr_string rejection;bool banned=false;
struct xrServer {
 bool disconnected=false,duplicate=false;
 xrClientData* ID_to_client(unsigned){return disconnected?nullptr:&test_client;}
 xrClientData* FindClient(const LoginInUse&){return duplicate?&test_client:nullptr;}
};
void to_lower(xr_string& value){for(char& c:value)c=char(std::tolower(static_cast<unsigned char>(c)));}
Account* account_find(LPCSTR name){xr_string key=name;to_lower(key);auto i=s_accounts.find(key);return i==s_accounts.end()?nullptr:&i->second;}
void accounts_save(){++saves;s_accounts_dirty=false;}
void reject(xrServer*,xrClientData*,LPCSTR reason){rejection=reason;}
bool constant_time_equal(const xr_string& a,const xr_string& b){return a==b;}
bool server_banned(const xr_string&,const xr_string&){return banned;}
u32 GetTickCount(){return 1000;}
void Msg(LPCSTR,...){ }
''' + admission + r'''
void reset(){s_accounts.clear();s_accounts_dirty=false;test_client={};saves=0;rejection.clear();banned=false;}
Account legacy(unsigned approval,Role role=role_player){
 Account a;a.login="Player";a.salt="fixture-salt";a.hash="fixture-digest";a.device="fixture-device";
 a.role=role;a.approval=approval;a.has_money=true;a.money=5000;return a;
}
int main(){
 xrServer server;PendingAuth request;
 for(unsigned old: {0u,1u,2u})for(Role role: {role_player,role_admin}){
  reset();s_accounts["player"]=legacy(old,role);finish_auth(&server,&request);
  assert(rejection.empty() && test_client.netcoop_login=="Player" && test_client.netcoop_role==role);
  const auto& a=s_accounts.at("player");assert(a.approval==1 && saves==(old==1?0u:1u));
  assert(a.role==role && a.money==5000 && a.has_money && a.salt==request.salt && a.hash==request.hash && a.device==request.device);
 }
 reset();request.create=true;finish_auth(&server,&request);
 assert(rejection.empty() && saves==1 && s_accounts.at("player").approval==1);
 assert(test_client.netcoop_role==role_player && s_accounts.at("player").role==role_player);
 reset();request.hashed=false;finish_auth(&server,&request);
 assert(!rejection.empty() && s_accounts.empty() && test_client.netcoop_role==role_none && !saves);
 request.hashed=true;request.create=false;
 for(unsigned old: {0u,2u}){
  reset();s_accounts["player"]=legacy(old);request.hash="wrong-fixture-digest";finish_auth(&server,&request);
  assert(rejection=="Wrong password" && test_client.netcoop_role==role_none);
  assert(s_accounts.at("player").approval==old && !saves);
  request.hash="fixture-digest";
  reset();s_accounts["player"]=legacy(old);request.device="other-fixture-device";finish_auth(&server,&request);
  assert(!rejection.empty() && test_client.netcoop_role==role_none && s_accounts.at("player").approval==old && !saves);
  request.device="fixture-device";
  reset();s_accounts["player"]=legacy(old);banned=true;finish_auth(&server,&request);
  assert(rejection=="You are banned on this server" && test_client.netcoop_role==role_none);
  assert(s_accounts.at("player").approval==old && !saves);
 }
 reset();s_accounts["player"]=legacy(0);server.duplicate=true;finish_auth(&server,&request);
 assert(rejection=="This account is already online" && !saves);server.duplicate=false;
 reset();request.firebase=true;request.firebase_uid="fixture-uid";s_accounts["player"]=legacy(0);
 s_accounts["player"].firebase_uid="different-fixture-uid";finish_auth(&server,&request);
 assert(rejection=="Wrong password" && !saves && test_client.netcoop_role==role_none);
 reset();s_accounts["player"]=legacy(0);s_accounts["player"].firebase_uid=request.firebase_uid;finish_auth(&server,&request);
 assert(rejection.empty() && saves==1 && test_client.netcoop_role==role_player);
 assert(s_accounts.at("player").firebase_uid==request.firebase_uid);
 reset();server.disconnected=true;finish_auth(&server,&request);assert(s_accounts.empty() && !saves && rejection.empty());
 server.disconnected=false;
 // Google sign-in off (owner 2026-10-17): a Google account takes a password
 // from the computer it is bound to, and signs in with it afterwards.
 PendingAuth claim;claim.claim=true;claim.salt="new-fixture-salt";claim.hash="new-fixture-digest";
 reset();s_accounts["player"]=legacy(1);s_accounts["player"].firebase_uid="fixture-uid";s_accounts["player"].hash="firebase";
 finish_auth(&server,&claim);
 assert(rejection.empty() && test_client.netcoop_role==role_player && saves==1);
 assert(s_accounts.at("player").firebase_uid.empty() && s_accounts.at("player").salt=="new-fixture-salt" && s_accounts.at("player").hash=="new-fixture-digest");
 PendingAuth again;again.salt="new-fixture-salt";again.hash="new-fixture-digest";
 test_client={};rejection.clear();finish_auth(&server,&again);assert(rejection.empty() && test_client.netcoop_role==role_player);
 reset();s_accounts["player"]=legacy(1);s_accounts["player"].firebase_uid="fixture-uid";s_accounts["player"].hash="firebase";
 claim.device="other-fixture-device";finish_auth(&server,&claim);
 assert(!rejection.empty() && test_client.netcoop_role==role_none && s_accounts.at("player").hash=="firebase" && !saves);
}
'''
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Native fixture compiles only in GitHub Actions; no local compiler invocation.')
with TemporaryDirectory(prefix='open-registration-') as temporary:
    target=Path(temporary);cpp=target/'auth.cpp';exe=target/('auth.exe' if os.name=='nt' else 'auth')
    cpp.write_text(source,encoding='utf-8')
    args=(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX',str(cpp),'/Fe:'+str(exe)] if os.name=='nt'
          else ['g++','-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)])
    subprocess.run(args,cwd=target,check=True);subprocess.run([str(exe)],cwd=target,check=True)
print('PASS actual auth admission: Google accounts take a password from their own computer, immediate player registration, legacy approval migration, roles/credentials retained; wrong password/device/identity, duplicate login and bans still denied')
