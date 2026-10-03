"""Developer setup: vendor the pinned renderer and compile game archive codecs."""
from pathlib import Path
import shutil, subprocess, urllib.request

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1] / 'src/xrCore'
VENDOR = HERE / 'vendor'
VENDOR.mkdir(exist_ok=True)
for filename in ['three.module.js', 'three.core.js']:
    url = f'https://cdn.jsdelivr.net/npm/three@0.180.0/build/{filename}'
    urllib.request.urlretrieve(url, VENDOR / filename)
for name in ['OrbitControls', 'TransformControls']:
    url = f'https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/controls/{name}.js'
    urllib.request.urlretrieve(url, VENDOR / (name + '.js'))
urllib.request.urlretrieve('https://cdn.jsdelivr.net/npm/three@0.180.0/LICENSE', VENDOR / 'THREE-LICENSE.txt')
native = HERE / 'native'
native.mkdir(exist_ok=True)
for p in CORE.glob('rt_*'):
    if p.suffix in ('.h', '.ch'):
        shutil.copy2(p, native / p.name)
for name in ['LzHuf.cpp', 'rt_lzo1x_d2.cpp']:
    text = (CORE / name).read_text(encoding='utf-8-sig')
    (native / name).write_text(text.replace('#include "stdafx.h"', '#include "standalone.h"'), encoding='utf-8')
(native / 'standalone.h').write_text('''#pragma once
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
using u8=uint8_t; using u32=uint32_t;
#define IC inline
#define xr_malloc malloc
#define xr_realloc realloc
#define xr_free free
''')
(native / 'codec.cpp').write_text('''#include "standalone.h"
#include "rt_lzo1x.h"
void _decompressLZ(u8**,unsigned*,void*,unsigned);
extern "C" __declspec(dllexport) int unpack_lzh(void* src,unsigned size,void* dst,unsigned capacity) {
 if(size<4 || capacity==0 || capacity>64*1024*1024) return -1;
 if(*static_cast<unsigned*>(src)!=capacity) return -2;
 u8* out=nullptr; unsigned count=0; _decompressLZ(&out,&count,src,size);
 if(count==capacity) memcpy(dst,out,count); free(out); return count==capacity ? 0 : -3;
}
extern "C" __declspec(dllexport) int unpack_lzo(void* src,unsigned size,void* dst,unsigned capacity) {
 lzo_uint count=capacity;
 int result=lzo1x_decompress_safe((lzo_bytep)src,size,(lzo_bytep)dst,&count,nullptr);
 return result==0 && count==capacity ? 0 : -1;
}
''')
vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
build = native / 'build.cmd'
build.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /O2 /MT /LD /EHsc codec.cpp LzHuf.cpp rt_lzo1x_d2.cpp /link /OUT:../vendor/xray-codecs.dll\n')
subprocess.run(['cmd', '/c', str(build)], cwd=native, check=True)
print('Renderer and archive codecs ready.')
