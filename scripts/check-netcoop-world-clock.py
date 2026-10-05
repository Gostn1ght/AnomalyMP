"""Compile and exercise the real W2 clock foundation, exclusively in CI."""
from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
source = r'''
#include "netcoop_world_clock.h"
#include <cassert>
#include <chrono>
#include <iostream>
#include <limits>
#include <vector>
using namespace netcoop_world;
void close(double a, double b) { assert(std::abs(a-b) < 0.01); }
template <class F> void rejects(F f) {
 bool failed=false; try { f(); } catch (const std::exception&) { failed=true; }
 assert(failed);
}
int main() {
 WorldClock a(71, 8, 100000, 10, 900);
 close(a.now(1900), 110000);
 a.set_scale(2,1900); close(a.now(1900),110000); close(a.now(2900),112000);
 a.set_scale(0,2900);close(a.now(100000),112000);
 auto paused=a.publish(100000);
 auto restored=WorldClock::restore(paused,9,7);close(restored.now(999),112000);
 rejects([&]{WorldClock::restore(paused,8,0);});
 rejects([&]{a.set_scale(-1,100000);});
 rejects([&]{a.set_scale(std::numeric_limits<double>::quiet_NaN(),100000);});
 rejects([&]{a.now(1);});
 rejects([&]{a.now(99999);}); // regression after a read, even beyond anchor
 rejects([]{WorldClock bad(0,1,1,1,0);});
 rejects([]{WorldClock bad(1,1,1,std::numeric_limits<double>::infinity(),0);});
 WorldClock overflow(1,1,max_world_ms,1,0); rejects([&]{overflow.now(1);});

 LocationClock f(71);
 ClockSample s{1,71,8,1,500000,10};
 assert(f.observe(s,100,200)==SyncResult::resync_required);
 assert(f.bootstrap(s,100,200)==SyncResult::applied);
 close(f.estimate(200),500500);close(f.estimate(300),501500);
 s.sequence=2;s.world_ms=501600;
 assert(f.observe(s,300,300)==SyncResult::applied);
 close(f.estimate(300),501500); // message receipt is continuous
 close(f.estimate(400),502550);close(f.estimate(500),503600);
 assert(f.observe(s,500,500)==SyncResult::stale);
 s.sequence=3;s.world_ms=502600; // follower ahead: slower, never backwards
 assert(f.observe(s,500,500)==SyncResult::applied);
 close(f.estimate(1500),513100);
 assert(!f.ready(32000));
 auto invalid=s; invalid.world_id=72;
 assert(f.observe(invalid,1500,1500)==SyncResult::invalid);
 invalid=s;invalid.schema=2;assert(f.observe(invalid,1500,1500)==SyncResult::invalid);
 invalid=s;invalid.time_scale=std::numeric_limits<double>::infinity();
 assert(f.observe(invalid,1500,1500)==SyncResult::invalid);
 assert(f.observe(s,2000,1999)==SyncResult::invalid);
 assert(f.observe(s,2000,4000)==SyncResult::invalid);
 s.authority_epoch=9;s.sequence=1;s.world_ms=600000;
 assert(f.observe(s,1500,1500)==SyncResult::epoch_changed);
 assert(!f.ready(1500));
 auto old=s;old.authority_epoch=8;old.sequence=999;
 assert(f.observe(old,1500,1500)==SyncResult::stale);
 assert(f.bootstrap(old,1500,1500)==SyncResult::stale);
 assert(f.bootstrap(s,1500,1500)==SyncResult::applied);
 assert(f.ready(1500));close(f.estimate(1600),601000);
 s.sequence=2;s.world_ms=900000;
 assert(f.observe(s,1600,1600)==SyncResult::resync_required);
 assert(!f.ready(1600));
 assert(f.bootstrap(s,1600,1600)==SyncResult::applied);
 s.sequence=3;s.time_scale=0;s.world_ms=900000;
 assert(f.observe(s,1600,1600)==SyncResult::applied);
 close(f.estimate(2600),900000);
 s.sequence=4;s.world_ms=900010;
 assert(f.observe(s,2600,2600)==SyncResult::resync_required);
 assert(!f.ready(2600));
 rejects([&]{f.estimate(1);});
 // A 64-bit local clock crosses the legacy 32-bit millisecond wrap safely.
 WorldClock uptime(71,1,42,1,UINT32_MAX-50ULL);
 close(uptime.now(UINT32_MAX+50ULL),142);

 // Different monotonic origins on different hosts, one hour at +/-100 ppm.
 WorldClock authority(71,50,700000,10,0);
 std::vector<LocationClock> locations;
 for(int i=0;i<25;++i) locations.emplace_back(71);
 for(int i=0;i<25;++i) {
  auto first=authority.publish(0);
  assert(locations[i].bootstrap(first,1000000+i*10000,1000000+i*10000)==SyncResult::applied);
 }
 double maximum_error=0;
 for(std::uint64_t real=1000; real<=3600000;real+=1000) {
  for(int i=0;i<25;++i) {
   auto local=std::uint64_t(1000000+i*10000+double(real)*(i%2 ? 1.0001 : 0.9999));
   if(real%5000==0) {
    auto sample=authority.publish(real);
    assert(locations[i].observe(sample,local,local)==SyncResult::applied);
   }
   assert(locations[i].ready(local));
   maximum_error=std::max(maximum_error,std::abs(locations[i].estimate(local)-authority.now(real)));
  }
 }
 assert(maximum_error<10); // game ms, ideal symmetric/zero-delay fixture

 // 25 location clocks and 512 estimate consumers; not a gameplay capacity test.
 auto start=std::chrono::steady_clock::now();double checksum=0;
 for(std::uint64_t frame=1;frame<=10000;++frame)
  for(int player=0;player<512;++player) {
   int i=player%25;
   auto local=std::uint64_t(1000000+i*10000+3600000*(i%2 ? 1.0001 : 0.9999))+frame;
   checksum+=locations[i].estimate(local);
  }
 assert(checksum>0);
 LocalWorldService service(WorldClock(71,77,500,10,0),1234,1);
 IWorldService& interface=service;
 auto snapshot=interface.snapshot(100);
 assert(snapshot.world_seed==1234 && snapshot.state_revision==1);
 close(snapshot.clock.world_ms,1500);
 auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
 std::cout << "PASS: real W2 clock, epochs, duplicate/stale/invalid messages, pause, scale continuity, recovery, holdover, 64-bit uptime\n"
  << "25 followers / 1 hour / +/-100 ppm: max ideal-network error " << maximum_error << " game ms\n"
  << "512 consumers / 10000 frames: " << elapsed << " ms; clock microbenchmark only\n";
}
'''
with TemporaryDirectory(prefix="world-clock-") as tmp:
    cpp = Path(tmp)/"check.cpp"
    exe = Path(tmp)/("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    include = str(root/"src/xrGame")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   "/I"+include, str(cpp), "/Fe:"+str(exe), "/Fo:"+str(Path(tmp)/"check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2",
                   "-I", include, str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
