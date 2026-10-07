"""Actual bot start/auth/transfer/retry code, compiled only in GitHub Actions."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
bot = (root / 'src/xrGame/netcoop_bots.cpp').read_text(encoding='utf-8')

def block(marker):
    start = bot.index(marker)
    opening = bot.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (bot[end] == '{') - (bot[end] == '}')
        end += 1
    return bot[start:end]

start_method = block('\tbool start(LPCSTR address, u32 now)')
transfer_method = block('\tbool queue_transfer(LPCSTR data)')
auth = block('case M_NETCOOP_AUTH_RESULT:').split(':', 1)[1]
retry_loop = block('\tfor (NetcoopBot*& b : s_bots)')
source = r'''
#include "netcoop_bot_target.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <utility>
#include <vector>
using u8=std::uint8_t; using u32=std::uint32_t; using LPCSTR=const char*;
using string64=char[64]; using string256=char[256]; using string512=char[512];
template<std::size_t N> void xr_strcpy(char (&out)[N],const char* text){assert(std::strlen(text)<N);std::strcpy(out,text);}
template<std::size_t N,typename... A> int xr_sprintf(char (&out)[N],const char* format,A... args){return std::snprintf(out,N,format,args...);}
template<typename T,typename... A> T* xr_new(A&&... args){return new T(std::forward<A>(args)...);}
template<typename K,typename V> using xr_map=std::map<K,V>;
template<typename... A> void Msg(const char*,A...){ }
struct {string64 UserName="fixture-user";} Core;
u32 clock_now=0; bool connect_ok=true;
struct Packet {u8 ok;const char* text;unsigned reads=0;u8 r_u8(){return reads++ ? 0:ok;}};
bool read_string(Packet& p,char* out,unsigned size){if(std::strlen(p.text)>=size)return false;std::strcpy(out,p.text);return true;}
using netcoop::BotTarget;using netcoop::parse_bot_target;
struct NetcoopBot {
 enum State{st_connecting,st_joining,st_waiting_actor,st_playing,st_failed};
 u32 m_index,m_state_time=0,m_failed_at=0;string64 m_login={};string256 m_address={},m_transfer={};
 State m_state=st_connecting;bool m_played=false,stopped=false;std::string last_options;
 explicit NetcoopBot(u32 n):m_index(n){std::snprintf(m_login,sizeof(m_login),"nbot_%03u",n);}
 bool Connect(const char* options){last_options=options;xr_strcpy(Core.UserName,"temporary-connect-name");return connect_ok;}
 void fail(const char*){m_state=st_failed;m_failed_at=clock_now;}
 void stop(){stopped=true;}
 void update(u32){}
 State state()const{return m_state;}u32 index()const{return m_index;}bool played()const{return m_played;}
 u32 failed_at()const{return m_failed_at;}LPCSTR address()const{return m_address;}
 LPCSTR transfer()const{return m_transfer[0]?m_transfer:nullptr;}
''' + start_method + '\n' + transfer_method + r'''
 void auth(u8 approved,const char* text){Packet P{approved,text};
''' + auth + r'''
 }
};
struct Dead{NetcoopBot* bot;u32 since;};
std::vector<NetcoopBot*> s_bots;std::vector<Dead> s_dead;
const char* s_address="127.0.0.1/port=1367";
void frame(u32 now){static xr_map<u32,u32> retries;
''' + retry_loop + r'''
}
int main(){
 BotTarget target;assert(parse_bot_target("127.0.0.1|1377|l01_escape",target));
 assert(std::string(target.address)=="127.0.0.1/port=1377"&&std::string(target.level)=="l01_escape");
 assert(parse_bot_target("map-server_2.example|65535|k00_marsh",target));
 const std::string invalid[]={"", "host", "host|0|map", "host|-1|map", "host|65536|map", "host|4294967297|map",
  "host|1x|map", "host|+1|map", "host|1|", "host|1|map|extra", "a/b|1|map", "a b|1|map", "host|1|map bad",
  std::string(128,'a')+"|1|map", "host|1|"+std::string(64,'a')};
 for(const auto& text:invalid){BotTarget prior=target;assert(!parse_bot_target(text.c_str(),target));assert(std::memcmp(&prior,&target,sizeof(target))==0);}
 assert(!parse_bot_target(nullptr,target));
 std::mt19937 rng(1924);for(unsigned n=0;n<10000;++n){std::string text;for(unsigned i=0,len=rng()%400;i<len;++i)text+=char(1+rng()%127);parse_bot_target(text.c_str(),target);}

 NetcoopBot direct(100);assert(direct.start("127.0.0.1/port=1377",0));
 assert(std::string(direct.address())=="127.0.0.1/port=1377"&&direct.last_options=="127.0.0.1/port=1377/name=nbot_100");
 assert(std::string(Core.UserName)=="fixture-user");
 direct.auth(0,"redirect|127.0.0.1|1367|k00_marsh");
 assert(direct.state()!=NetcoopBot::st_failed&&!direct.stopped); // queue, no disconnect under lock
 assert(std::string(direct.transfer())=="127.0.0.1/port=1367");
 NetcoopBot denied(101);denied.auth(0,"wrong password");assert(denied.state()==NetcoopBot::st_failed);
 NetcoopBot malformed(102);malformed.auth(0,"redirect|host|65536|map");assert(malformed.state()==NetcoopBot::st_failed&&!malformed.transfer());
 NetcoopBot accepted(103);accepted.auth(1,"OK");assert(accepted.state()!=NetcoopBot::st_failed&&!accepted.transfer());
 connect_ok=false;NetcoopBot immediate(104);assert(!immediate.start("host/port=1377",0));assert(std::string(immediate.address())=="host/port=1377");connect_ok=true;

 // Reproduce native failure: timeout after moving to Cordon must retry Cordon.
 auto* old=new NetcoopBot(1);old->start("127.0.0.1/port=1377",0);old->fail("timeout");s_bots.push_back(old);
 frame(4000);assert(s_bots[0]!=old&&old->stopped);assert(std::string(s_bots[0]->address())=="127.0.0.1/port=1377");
 // A server redirect after an admission retry is a target, not a failed bot.
 s_bots[0]->auth(0,"redirect|127.0.0.1|1367|k00_marsh");auto* redirected=s_bots[0];frame(5000);
 assert(s_bots[0]!=redirected&&redirected->stopped&&std::string(s_bots[0]->address())=="127.0.0.1/port=1367");
 auto* retry2=s_bots[0];retry2->fail("timeout");frame(9000);
 assert(s_bots[0]!=retry2&&std::string(s_bots[0]->address())=="127.0.0.1/port=1367");
 auto* retry3=s_bots[0];retry3->fail("timeout");frame(13000);assert(s_bots[0]!=retry3);
 auto* exhausted=s_bots[0];exhausted->fail("timeout");frame(17000);assert(s_bots[0]==exhausted&&exhausted->state()==NetcoopBot::st_failed);
 // Keep the existing bounded retry policy and stable-playing disconnect behavior.
 exhausted->m_played=true;frame(20000);assert(s_bots[0]==exhausted);
 for(auto* b:s_bots)delete b;for(auto entry:s_dead)delete entry.bot;
 std::cout<<"PASS actual bot start/auth/transfer/retry loop: target address survives failed handoff, redirects queue reconnects, malformed targets reject, retry bounds and name restoration preserved\n";
}
'''
with TemporaryDirectory() as temp:
    directory = Path(temp)
    cpp = directory / 'check.cpp'
    cpp.write_text(source, encoding='utf-8')
    include = root / 'src/xrGame'
    exe = directory / ('check.exe' if os.name == 'nt' else 'check')
    if os.name == 'nt':
        command = ['cl', '/nologo', '/EHsc', '/std:c++17', '/W4', f'/I{include}', str(cpp), f'/Fe:{exe}']
    else:
        command = ['g++', '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-fsanitize=address,undefined',
                   '-fno-omit-frame-pointer', f'-I{include}', str(cpp), '-o', str(exe)]
    subprocess.run(command, cwd=directory, check=True)
    subprocess.run([str(exe)], cwd=directory, check=True)
