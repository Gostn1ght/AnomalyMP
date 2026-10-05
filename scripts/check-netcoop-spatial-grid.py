"""Exercise the real spatial index, exclusively through GitHub Actions."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
source = r'''
#include "netcoop_spatial_grid.h"
#include <cassert>
#include <chrono>
#include <iostream>
#include <random>
using namespace netcoop_world;
template<class F> void rejects(F f) {
 bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);
}
int main() {
 SpatialGrid grid(100);
 assert(grid.cell(1,{-0.001,0,-100.001}).x==-1);
 assert(grid.cell(1,{-0.001,0,-100.001}).z==-2);
 assert(grid.cell(1,{100,0,100}).x==1);
 assert(grid.distance_to_cell(1,{99,0,50},{1,1,0})==1);
 rejects([&]{grid.distance_to_cell(2,{0,0,0},{1,0,0});});
 grid.upsert({1,2},1,{-1,0,0});
 grid.upsert({2,2},2,{-1,0,0});
 assert(grid.size()==2 && grid.cell_count()==2);
 assert(grid.query(1,{0,0,0},1)==std::vector<SpatialId>({{1,2}}));
 grid.upsert({1,2},1,{200,0,0});
 assert(grid.query(1,{0,0,0},1).empty());
 assert(grid.query(1,{200,0,0},0).size()==1);
 grid.upsert({1,2},2,{-1,0,0});
 assert(grid.cell_count()==1 && grid.query(2,{},1).size()==2);
 assert(grid.erase({1,2}) && !grid.erase({1,2}));
 assert(grid.erase({2,2}) && grid.cell_count()==0);
 rejects([&]{grid.upsert({},1,{});});
 rejects([&]{grid.upsert({1,1},0,{});});
 rejects([&]{grid.upsert({1,1},1,{std::numeric_limits<double>::infinity(),0,0});});
 rejects([&]{grid.query(1,{},-1);});
 rejects([&]{grid.query(1,{},1e7);}); // bounded query workload
 grid.upsert({1,1},1,{0,0,500});
 grid.upsert({1,2},1,{100,0,500});
 grid.upsert({1,3},1,{0,0,1100});
 auto swept=grid.swept(1,{0,0,0},{0,0,1000},50);
 assert(swept==std::vector<SpatialId>({{1,1}})); // middle, not just endpoints
 grid.upsert({1,1},1,{0,200,500});
 assert(grid.swept(1,{0,0,0},{0,0,1000},50).empty()); // height matters
 grid.clear();

 struct Entry {SpatialId id;std::uint32_t location;SpatialPoint point;};
 std::vector<Entry> entries;
 std::mt19937 random(7384);
 std::uniform_real_distribution<double> horizontal(-4000,4000), vertical(-100,100);
 for(std::uint64_t i=1;i<=20000;++i) {
  Entry e{{i%17,i},std::uint32_t(1+i%4),{horizontal(random),vertical(random),horizontal(random)}};
  entries.push_back(e);grid.upsert(e.id,e.location,e.point);
 }
 SpatialQueryStats stats;
 const auto start=std::chrono::steady_clock::now();
 for(unsigned i=0;i<256;++i) {
  SpatialPoint p{horizontal(random),vertical(random),horizontal(random)};
  const std::uint32_t location=1+i%4;
  const double radius=50+(i%8)*100;
  const auto actual=grid.query(location,p,radius,&stats);
  std::vector<SpatialId> expected;
  for(const auto& e:entries)
   if(e.location==location && point_distance_squared(e.point,p)<=radius*radius)expected.push_back(e.id);
  std::sort(expected.begin(),expected.end());assert(actual==expected);
 }
 assert(stats.candidates<entries.size()*256/16);
 const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
 // Two disjoint observers do not activate the objects between them.
 grid.clear();grid.upsert({1,1},1,{});grid.upsert({1,2},1,{5000,0,0});grid.upsert({1,3},1,{2500,0,0});
 auto sets=interest_sets(grid,{{{9,1},1,{},{}},{{9,2},1,{5000,0,0},{}}});
 assert(sets.size()==2 && sets[0].visible.size()==1 && sets[1].visible.size()==1);
 assert(sets[0].visible[0]==SpatialId({1,1}) && sets[1].visible[0]==SpatialId({1,2}));
 InterestConfig invalid;invalid.prewarm_radius=invalid.observable_radius;
 rejects([&]{interest_sets(grid,{},invalid);});
 auto prediction=interest_sets(grid,{{{9,1},1,{0,0,0},{100000,0,0}}});
 assert(prediction[0].prewarm.size()==1); // untrusted speed clamped to server cap
 std::cout<<"PASS: real cell grid, negative boundaries, moves/erase, location scope, sphere/capsule, deterministic AOI, bounded query\n"
  <<"20k synthetic records / 256 indexed vs brute queries: "<<stats.candidates<<" candidates vs "<<entries.size()*256<<" scans, "<<elapsed<<" ms including reference\n"
  <<"Spatial microbenchmark only; no 128/512 gameplay capacity claim\n";
}
'''
with TemporaryDirectory(prefix="world-spatial-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    include = str(root / "src/xrGame")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   "/I" + include, str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2", "-I", include, str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
