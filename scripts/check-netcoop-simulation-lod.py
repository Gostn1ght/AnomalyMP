"""Real LOD policy and representation barrier, compiled only in Actions."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
source = r'''
#include "netcoop_simulation_lod.h"
#include <cassert>
#include <iostream>
using namespace netcoop_world;
template<class F> void rejects(F f) {
 bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);
}
int main() {
 SpatialGrid grid;
 SimulationLodPlanner planner;
 const CellId near{1,0,0}, far{1,50,0}, between{1,25,0};
 std::vector<PlayerInterest> observers{{{1,1},1,{},{}},{{1,2},1,{5000,0,0},{}}};
 auto left=planner.observer_demand(grid,near,observers);
 auto right=planner.observer_demand(grid,far,observers);
 auto middle=planner.observer_demand(grid,between,observers);
 assert(left.minimum==SimulationLod::Full && right.minimum==SimulationLod::Full);
 assert(middle.minimum==SimulationLod::Dormant); // union, not one huge enclosing circle
 assert(planner.observer_demand(grid,{2,0,0},observers).minimum==SimulationLod::Dormant);
 assert(planner.observer_demand(grid,{1,3,0},{{{1,3},1,{299,0,0},{}}}).minimum==SimulationLod::Full); // bounds
 assert(planner.update({left,right,middle,{between,SimulationLod::Abstract}},100).size()==3);
 assert(planner.level(between)==SimulationLod::Abstract); // active distant group/event
 assert(planner.update({{near,SimulationLod::Reduced}},200).empty());
 assert(planner.update({{near,SimulationLod::Full}},1900).empty()); // crossing boundary cancels exit
 assert(planner.update({{near,SimulationLod::Reduced}},3000).empty());
 planner.update({{near,SimulationLod::Reduced}},5100);
 assert(planner.level(near)==SimulationLod::Reduced); // dwell + uninterrupted delay
 planner.update({{near,SimulationLod::Full}},5101);
 assert(planner.level(near)==SimulationLod::Full); // escalation is immediate
 rejects([&]{planner.update({},5100);});
 rejects([&]{planner.update({{{0,0,0},SimulationLod::Full}},6000);});
 assert(planner.level(near)==SimulationLod::Full); // invalid input changed nothing
 planner.update({},10101);planner.update({},12101);
 assert(planner.level(near)==SimulationLod::Dormant);
 assert(planner.prune_dormant()==3 && planner.size()==0);
 LodConfig budget;budget.maximum_cells=1;
 SimulationLodPlanner bounded(budget);
 rejects([&]{bounded.update({left,right},1);});assert(bounded.size()==0);
 // Diagonal high-speed preparation covers intermediate cells; untrusted
 // speed cannot broaden admission beyond the configured server speed cap.
 LodConfig moving;moving.prewarm_radius=800;moving.prediction_seconds=10;moving.max_speed=100;
 SimulationLodPlanner predictive(moving);
 assert(predictive.observer_demand(grid,{1,7,7},{{{1,3},1,{}, {100,0,100}}}).minimum==SimulationLod::Reduced);
 assert(predictive.observer_demand(grid,{1,30,30},{{{1,3},1,{}, {100000,0,100000}}}).minimum==SimulationLod::Dormant);
 LodConfig invalid;invalid.prewarm_radius=invalid.reduced_radius;
 rejects([&]{SimulationLodPlanner bad(invalid);});
 // No visual appearance until ownership, full capture, placement and Reduced
 // AI are acknowledged. Failed/late ACKs cannot resurrect stale runtimes.
 RepresentationGate gate;
 assert(gate.abstract_writable() && !gate.runtime_writable() && !gate.replication_ready());
 auto ticket=gate.begin_hydration(1);
 assert(!gate.abstract_writable() && !gate.replication_ready());
 rejects([&]{gate.begin_hydration(1);});
 rejects([&]{gate.finish_hydration(ticket,2,true,true,false,true);});
 assert(gate.state()==Representation::Hydrating);
 rejects([&]{gate.finish_hydration({ticket.generation+1,1},2,true,true,true,true);});
 gate.finish_hydration(ticket,2,true,true,true,true);
 assert(gate.replication_ready() && gate.runtime_writable() && !gate.abstract_writable());
 gate.critical(true);rejects([&]{gate.begin_dehydration(2);});gate.critical(false);
 auto capture=gate.begin_dehydration(2);
 assert(!gate.runtime_writable() && !gate.abstract_writable() && !gate.replication_ready());
 rejects([&]{gate.finish_dehydration(capture,3,false,true);});
 rejects([&]{gate.cancel_dehydration(capture,false);}); // backend may have committed
 gate.cancel_dehydration(capture,true);
 auto newer=gate.begin_dehydration(2);
 rejects([&]{gate.finish_dehydration(capture,3,true,true);}); // late ACK/ABA
 gate.finish_dehydration(newer,3,true,true);
 auto retry=gate.begin_hydration(3);
 rejects([&]{gate.cancel_hydration(retry,4,false);});
 gate.cancel_hydration(retry,4,true);
 rejects([&]{gate.finish_hydration(retry,5,true,true,true,true);});
 auto final=gate.begin_hydration(4);gate.finish_hydration(final,5,true,true,true,true);
 rejects([&]{gate.finish_hydration(ticket,6,true,true,true,true);});
 std::cout<<"PASS: multi-observer cell union, independent simulation radii, bounds, hysteresis, prewarm, work budget, hydration/dehydration prerequisites and stale ACK fencing\n"
  <<"Policy fixture only; live AI/physics/replication adapter remains separate\n";
}
'''
with TemporaryDirectory(prefix="world-lod-") as tmp:
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
