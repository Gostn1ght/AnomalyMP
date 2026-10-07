"""Exercise actual bot callback forwarding and concurrent gap probe in Actions."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
bot = (root / "src/xrGame/netcoop_bots.cpp").read_text(encoding="utf-8")
start = bot.index("\tvoid OnMessage(void* data, u32 size) override")
opening = bot.index("{", start)
depth = 1
end = opening + 1
while depth:
    depth += (bot[end] == "{") - (bot[end] == "}")
    end += 1
callback = bot[start:end]
assert "~NetcoopBot() override { stop(); }" in bot
source = r'''
#include "netcoop_bot_gap_probe.h"
#include <algorithm>
#include <cassert>
#include <cstring>
#include <iostream>
#include <thread>
#include <vector>
using u16=std::uint16_t;using u32=std::uint32_t;
#include "xrMessages.h"
u32 clock_now=0;
u32 bot_now(){return clock_now;}
struct IPureClient {
 std::vector<std::vector<unsigned char>> messages;
 virtual ~IPureClient()=default;
 virtual void OnMessage(void* data,u32 size){
  auto* bytes=static_cast<unsigned char*>(data);messages.emplace_back(bytes,bytes+size);
 }
};
struct Bot:IPureClient {
 netcoop::BotGapProbe m_receive_gap;
''' + callback + r'''
};
int main(){
 netcoop::BotGapProbe probe;
 assert(probe.take_maximum()==0);probe.observe(0);probe.observe(10);probe.observe(25);
 assert(probe.take_maximum()==15);assert(probe.take_maximum()==0);
 probe.observe(40);assert(probe.take_maximum()==15); // preserve previous across reporting windows
 netcoop::BotGapProbe wrap;wrap.observe(0xfffffff0u);wrap.observe(0x10u);assert(wrap.take_maximum()==32);
 netcoop::BotGapProbe concurrent;std::atomic<bool> done{false};u32 reported=0;
 std::thread producer([&]{for(u32 i=0;i<=100000;++i)concurrent.observe(i*17u);done.store(true,std::memory_order_release);});
 while(!done.load(std::memory_order_acquire)){
  const auto maximum=concurrent.take_maximum();assert(maximum==0||maximum==17);reported=std::max(reported,maximum);
 }
 producer.join();reported=std::max(reported,concurrent.take_maximum());assert(reported==17);
 // Real callback observes deliveries while the consumer drains nothing for 1 s.
 Bot bot;u16 packet[2]={M_UPDATE,123};
 clock_now=100;bot.OnMessage(packet,u32(sizeof(packet)));
 clock_now=120;bot.OnMessage(packet,u32(sizeof(packet)));
 clock_now=140;packet[0]=M_UPDATE_OBJECTS;bot.OnMessage(packet,u32(sizeof(packet)));
 clock_now=1140;assert(bot.m_receive_gap.take_maximum()==20);assert(bot.messages.size()==3);
 for(const auto& forwarded:bot.messages){assert(forwarded.size()==sizeof(packet));u16 value;std::memcpy(&value,forwarded.data()+2,2);assert(value==123);}
 // Non-update bytes are forwarded unchanged, without falsely creating a gap.
 unsigned char short_packet=42;bot.OnMessage(&short_packet,1);
 packet[0]=900;bot.OnMessage(packet,u32(sizeof(packet)));assert(bot.m_receive_gap.take_maximum()==0);
 assert(bot.messages.size()==5&&bot.messages[3][0]==42);
 std::cout<<"PASS actual bot callback: unchanged forwarding; receive gap 20 ms despite 1000 ms consumer pause; rollover/reset; concurrent producer/report max retained\n";
}
'''
with TemporaryDirectory(prefix="bot-gap-") as tmp:
    folder = Path(tmp)
    (folder / "netcoop_bot_gap_probe.h").write_bytes((root / "src/xrGame/netcoop_bot_gap_probe.h").read_bytes())
    (folder / "xrMessages.h").write_bytes((root / "src/xrServerEntities/xrMessages.h").read_bytes())
    cpp = folder / "check.cpp"
    cpp.write_text(source, encoding="utf-8")
    exe = folder / ("check.exe" if os.name == "nt" else "check")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2", str(cpp), "/Fe:" + str(exe)] if os.name == "nt" else
               ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1", "-g", "-pthread", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, check=True, cwd=folder)
    subprocess.run([str(exe)], check=True, cwd=folder, timeout=30)
