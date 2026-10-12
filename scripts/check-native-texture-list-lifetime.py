"""Exercise the actual standalone/registered texture-list destructor in CI."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
text = (root / "src/Layers/xrRender/Shader.cpp").read_text(encoding="latin-1")
start = text.index("STextureList::~STextureList()")
method = text[start:text.index("\nSMatrixList::~SMatrixList()", start)]
source = r'''
#include <cassert>
#include <cstdio>
struct xr_resource_flagged {enum {RF_REGISTERED=1}; unsigned dwFlags=0;};
struct STextureList: xr_resource_flagged {~STextureList();};
struct Manager {
 unsigned deleted=0;
 void _DeleteTextureList(const STextureList* list){assert(list->dwFlags & xr_resource_flagged::RF_REGISTERED);++deleted;}
};
Manager* DEV=nullptr;
''' + method + r'''
// This list outlives the device, just like the empty menu texture list.
static STextureList menu_no_textures;
int main(){
 {STextureList standalone;}
 Manager manager;DEV=&manager;
 {STextureList registered; registered.dwFlags|=xr_resource_flagged::RF_REGISTERED;}
 assert(manager.deleted==1);
 {STextureList standalone;}
 assert(manager.deleted==1);DEV=nullptr;
 std::puts("PASS actual texture-list destructor: registered resources released; standalone lists survive device shutdown");
}
'''
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "texture_lifetime.cpp"
    exe = Path(tmp) / ("texture_lifetime.exe" if os.name == "nt" else "texture_lifetime")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
