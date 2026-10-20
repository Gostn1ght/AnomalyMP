"""Actual native trade admission fails closed before transaction effects (CI only)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from netcoop_source import netcoop_cpp

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = netcoop_cpp(root, encoding="utf-8")
start = text.index("static bool server_trade_item_allowed(")
end = text.index("\nstatic void send_trade_result", start)
helper = text[start:end]
# The actual per-basket price/admission pass precedes all money/transfer calls.
start = text.index("void server_on_trade(")
end = text.index("} // namespace netcoop", start)
trade = text[start:end]
assert trade.index("server_trade_item_allowed(partner_id, items[i], partner_buys)") < trade.index("trade->OnPerformTrade(")
assert trade.index("server_trade_item_allowed(partner_id, items[i], partner_buys)") < trade.index("trade->TransferItem(")
start = trade.index("\tfor (u32 i = 0; i < items.size(); ++i)")
end = trade.index("\n\tif (partner_buys)", start)
admission_pass = trade[start:end]

source = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
using u16=unsigned short;using u32=unsigned;
bool script_present=true,script_result=true,script_throws=false;
unsigned calls=0,errors=0;u16 seen_id=0;bool seen_direction=false;
struct Item {bool tradable=true,accepted=true;u32 price=100;bool CanTrade(){return tradable;}
 Item& object(){return *this;} Item* lua_game_object(){return this;}};
using PIItem=Item*;Item* seen_item=nullptr;
namespace luabind {template<class T> struct functor {
 T operator()(u16 id,Item* item,bool direction){
  ++calls;seen_id=id;seen_item=item;seen_direction=direction;
  if(script_throws)throw std::runtime_error("GAMMA policy failed");
  return script_result && item->accepted;
 }
};}
struct Engine {bool functor(const char* name,luabind::functor<bool>&){
 assert(std::strcmp(name,"netcoop_server_compat.trade_item_allowed")==0);return script_present;}};
struct AI {Engine engine;Engine& script_engine(){return engine;}};
AI test_ai;AI& ai(){return test_ai;}
void Msg(const char*,u16){++errors;}
'''
source += helper
source += r'''
struct Trade {unsigned stopped=0,priced=0;
 void StopTrade(){++stopped;}u32 GetItemPrice(Item* item,bool){++priced;return item->price;}};
unsigned committed=0,refused=0;
void validate_basket(const std::vector<PIItem>& items,bool partner_buys){
 const u16 partner_id=27;Trade check;Trade* trade=&check;u32 total=0;
 auto finish=[](bool ok,const char*){assert(!ok);++refused;};
'''
source += admission_pass
source += r'''
 assert(check.stopped==0 && check.priced==items.size() && total>0);
 ++committed; // witness after the actual complete pre-transaction pass
}
'''
source += r'''
int main(){
 Item item;
 assert(!server_trade_item_allowed(u16(27),nullptr,true) && calls==0);
 item.tradable=false;assert(!server_trade_item_allowed(u16(27),&item,true) && calls==0);
 item.tradable=true;script_present=false;assert(!server_trade_item_allowed(u16(27),&item,true) && calls==0);
 script_present=true;script_result=false;assert(!server_trade_item_allowed(u16(27),&item,true) && calls==1);
 script_result=true;assert(server_trade_item_allowed(u16(27),&item,true));
 assert(seen_id==27 && seen_item==&item && seen_direction);
 assert(server_trade_item_allowed(u16(28),&item,false) && seen_id==28 && !seen_direction);
 script_throws=true;assert(!server_trade_item_allowed(u16(27),&item,true) && errors==1);
 script_throws=false;assert(server_trade_item_allowed(u16(27),&item,true));
 Item second;second.accepted=false;
 validate_basket({&item,&second},true);assert(committed==0 && refused==1);
 validate_basket({&item,&second},false);assert(committed==0 && refused==2);
 second.accepted=true;validate_basket({&item,&second},true);assert(committed==1);
 second.price=0;validate_basket({&item,&second},true);assert(committed==1 && refused==3);
 second.price=100;script_throws=true;validate_basket({&item,&second},true);assert(committed==1 && refused==4);
 std::puts("PASS actual native trade admission: CanTrade, authoritative item/direction, missing/rejected/throwing Lua and mixed/zero-price baskets fail closed before transaction effects");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "trade.cpp"
    exe = Path(tmp) / ("trade.exe" if os.name == "nt" else "trade")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
