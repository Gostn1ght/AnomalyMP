"""Ground items never age out (the MP removal timers are gone from the
engine) and the actual armed missile fuse path detonates once, in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import re
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")

root = Path(__file__).resolve().parents[1]
game = root / "src/xrGame"

# Persistent ground items: no object may schedule its own removal by age.
for path in game.rglob("*.*"):
    if path.suffix not in (".cpp", ".h", ".inc"):
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"\bNeedToDestroyObject\b|\bTimePassedAfterIndependant\b", text):
        raise SystemExit(f"{path.relative_to(root)}: an age-based ground item removal is back")


def method(file, start, end):
    text = (game / file).read_text(encoding="utf-8")
    return text[text.index(start):text.index(end, text.index(start))]


source = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
using u32=std::uint32_t;
#define VERIFY(x) assert(x)
struct FixtureLevel {u32 now=1000;u32 timeServer()const{return now;}} fixture_level;
FixtureLevel& Level(){return fixture_level;}
struct MissileBase {void shedule_Update(u32) {}};
struct CMissile:MissileBase {
 using inherited=MissileBase;
 bool parent=false,visible=true;void* m_pPhysicsShell=this;void* m_pInventory=nullptr;
 u32 m_dwDestroyTime=0xffffffff;int detonated=0;
 bool H_Parent()const{return parent;}bool getVisible()const{return visible;}
 void Destroy(){++detonated;}void shedule_Update(u32);
};
''' + method("Missile.cpp", "void CMissile::shedule_Update(u32 dt)", "void CMissile::State(") + r'''
int main() {
 CMissile armed;armed.m_dwDestroyTime=999;armed.shedule_Update(1);
 assert(armed.detonated==1 && armed.m_dwDestroyTime==0xffffffff);
 armed.shedule_Update(1);assert(armed.detonated==1);
 CMissile future;future.m_dwDestroyTime=1001;future.shedule_Update(1);assert(future.detonated==0);
 fixture_level.now=1001;future.shedule_Update(1);assert(future.detonated==1);
 CMissile dropped;dropped.shedule_Update(1);assert(dropped.detonated==0);
 std::cout<<"PASS: no age-based ground item removal; actual armed fuse detonates once\n";
}
'''
with TemporaryDirectory(prefix="item-lifetime-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / ("check.exe" if os.name == "nt" else "check")
    cpp.write_text(source, encoding="utf-8")
    if os.name == "nt":
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   str(cpp), "/Fe:" + str(exe), "/Fo:" + str(Path(tmp) / "check.obj")]
    else:
        command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2", str(cpp), "-o", str(exe)]
    subprocess.run(command, check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True)
