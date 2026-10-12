"""Compile the actual Vector4 parser in CI: GAMMA three-value compatibility."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/xrEngine/xr_ioc_cmd.h").read_text(encoding="latin-1")
start = text.index("bool parse(LPCSTR args, Fvector4& v)", text.index("class CCC_Vector4"))
method = text[start:text.index("\n\tpublic", start)]
source = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <cassert>
#include <cstdio>
#include <initializer_list>
using LPCSTR = const char*;
struct Fvector4 { float x=0,y=0,z=0,w=0; };
struct Parser {
 Fvector4 min{0,0,0,0}, max{10,10,10,10};
''' + method + r'''
};
int main() {
 Parser p; Fvector4 v;
 for (const char* s : {"1,2,3", "(1,2,3)", "(0,0,0)", "0,0,0"}) {
  v.w=9; assert(p.parse(s,v)); assert(v.w==0);
 }
 for (const char* s : {"1,2,3,4", "(1,2,3,4)"}) {
  assert(p.parse(s,v)); assert(v.x==1 && v.y==2 && v.z==3 && v.w==4);
 }
 for (const char* s : {"", "1", "1,2", "(1,2)", "-1,2,3", "1,11,3", "1,2,3,11"})
  assert(!p.parse(s,v));
 p.min.w=1; assert(!p.parse("1,2,3",v)); assert(p.parse("1,2,3,4",v));
 std::puts("PASS actual Vector4 parser: three values default w=0, four preserved, incomplete and out-of-range rejected");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "vector.cpp"
    exe = Path(tmp) / ("vector.exe" if os.name == "nt" else "vector")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
