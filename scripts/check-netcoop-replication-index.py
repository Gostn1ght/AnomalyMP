"""Compare actual indexed candidates + native cadence against a full scan in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
game = root / "src/xrGame"
server = (game / "xrServer.cpp").read_text(encoding="utf-8")
start = server.index("\t\t\t\tconst float d = c.id == CL->owner->ID")
end = server.index("\t\t\t\tif ((server->m_aoi_tick + c.id) % every)", start)
cadence = server[start:end]
source = r'''
#include "netcoop_replication_index.h"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <vector>
using u16=std::uint16_t;using u32=std::uint32_t;
using namespace netcoop_world;
struct Fvector {
 float x,y,z;
 float distance_to(const Fvector& p)const{return std::sqrt((x-p.x)*(x-p.x)+(y-p.y)*(y-p.y)+(z-p.z)*(z-p.z));}
};
struct Chunk {u16 id;bool player;Fvector position;};
bool eligible(const ReplicationRecord& record,u16 owner,const Fvector& eye,u32 tick) {
 struct Owner {u16 ID;} object{owner};
 struct Client {Owner* owner;} client{&object};auto CL=&client;
 struct Server {u32 m_aoi_tick;} instance{tick};auto server=&instance;
 Chunk c{record.id,record.player,{record.x,record.y,record.z}};
''' + cadence + r'''
 return (server->m_aoi_tick+c.id)%every==0;
}
std::size_t compare(ReplicationIndex& index,const std::vector<ReplicationRecord>& records,u16 owner,Fvector eye,u32 tick) {
 const auto selected=index.select(owner,eye.x,eye.y,eye.z,tick);assert(selected.valid);
 std::vector<u32> actual,expected;
 for(std::size_t i=0;i<selected.count;++i) {
  const auto offset=selected.indices[i];assert(offset<records.size());
  if(i)assert(selected.indices[i-1]<offset);
  if(eligible(records[offset],owner,eye,tick))actual.push_back(offset);
 }
 for(std::size_t i=0;i<records.size();++i)
  if(eligible(records[i],owner,eye,tick))expected.push_back(u32(i));
 assert(actual==expected);return selected.count;
}
int main() {
 ReplicationIndex index;assert(!index.select(0,0,0,0,1).valid);
 assert(index.prepare(nullptr,0));assert(index.select(0,0,0,0,1).valid);
 assert(!index.prepare(nullptr,1));assert(!index.select(0,0,0,0,1).valid);
 assert(!index.prepare(nullptr,65537));
 std::vector<ReplicationRecord> records{
  {0,true,10000,0,0},{1,false,49.999f,0,0},{2,false,50,0,0},
  {3,false,149.999f,0,0},{4,false,150,0,0},{5,false,299.99997f,0,0},
  {6,false,300,0,0},{7,false,300.00003f,0,0},{8,false,0,299.99997f,0},
  {9,true,-10000,0,0},{65535,false,9999,0,0},{10,false,-300,0,0}
 };
 assert(index.prepare(records.data(),records.size()));
 for(u32 tick=0;tick<64;++tick)compare(index,records,0,{0,0,0},tick);
 for(u32 tick:{0xffffffffu,0xfffffffeu,0xfffffff0u})compare(index,records,65535,{0,0,0},tick);
 assert(!index.select(0,std::numeric_limits<float>::quiet_NaN(),0,0,1).valid);
 auto bad=records;bad[1].id=bad[0].id;
 assert(!index.prepare(bad.data(),bad.size()) && !index.select(0,0,0,0,1).valid);
 bad=records;bad[2].x=std::numeric_limits<float>::infinity();
 assert(!index.prepare(bad.data(),bad.size()) && !index.select(0,0,0,0,1).valid);
 assert(index.prepare(records.data(),records.size()));
 // Remove/reorder/reuse runtime handles: offsets always belong to this frame.
 records.erase(records.begin()+1);std::reverse(records.begin(),records.end());
 records.push_back({1,false,0,0,0});records[1].x=-450;
 assert(index.prepare(records.data(),records.size()));
 for(u32 tick=0;tick<32;++tick)compare(index,records,65535,{-450,0,0},tick);
 std::mt19937 rng(7251);std::uniform_real_distribution<float> coord(-5000,5000);
 records.clear();
 for(u32 i=0;i<12000;++i)records.push_back({u16(i),i<64,coord(rng),coord(rng)/30,coord(rng)});
 std::uint64_t candidates=0,full_scan=0;
 for(u32 frame=0;frame<32;++frame) {
  std::shuffle(records.begin(),records.end(),rng);
  for(std::size_t i=0;i<records.size();i+=17) {records[i].x=coord(rng);records[i].z=coord(rng);}
  assert(index.prepare(records.data(),records.size()));
  for(u16 player=0;player<64;++player) {
   // Includes distant observers, negative cells, height and high-speed jumps.
   candidates+=compare(index,records,player,{coord(rng),coord(rng)/30,coord(rng)},frame);
   full_scan+=records.size();
  }
 }
 assert(candidates<full_scan/4);
 std::cout<<"PASS: real grid candidates + unchanged native cadence match full scan, order, players/owner, float boundaries, tick overflow, moves/removals/reuse and fallback\n"
          <<"Synthetic candidate count "<<candidates<<" versus "<<full_scan<<" full checks; not a gameplay capacity/load test\n";
}
'''
with TemporaryDirectory(prefix="replication-index-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    implementation = str(game / "netcoop_replication_index.cpp")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2", "/I" + str(game),
                   str(cpp), implementation, "/Fe:" + str(exe), "/Fo:" + tmp + os.sep]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2", "-I", str(game),
                   str(cpp), implementation, "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
