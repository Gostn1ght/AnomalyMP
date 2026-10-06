"""Compile actual Windows transit mailbox functions only on GitHub Actions."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
if os.name != "nt":
    raise SystemExit("This fixture exercises Windows atomic durable file operations")
root = Path(__file__).resolve().parents[1]
queue = (root / "src/xrGame/netcoop_transit_queue.inc").read_text(encoding="utf-8")
source = r'''
#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#include <windows.h>
#include <io.h>
#include <cassert>
#include <cstdio>
#include <cstdarg>
#include <cctype>
#include <cstring>
#include <string>
#include <fstream>
#include <iostream>
#include <stdexcept>
using u8 = unsigned char; using u32 = unsigned int; using LPCSTR = const char*;
using xr_string = std::string; using string_path = char[260];
bool cooperative = true, fail_rename = false;
bool enabled() { return cooperative; }
size_t xr_strlen(const char* text) { return std::strlen(text); }
template <size_t N> void xr_sprintf(char (&s)[N], const char* format, ...) {
 va_list args; va_start(args, format); const int n = std::vsnprintf(s, N, format, args); va_end(args);
 if (n < 0 || size_t(n) >= N) throw std::runtime_error("format overflow");
}
bool random_bytes(u8* data, size_t size) {
 static unsigned int next = 0; ++next;
 for(size_t i=0;i<size;++i) data[i] = u8((next >> ((i % 4)*8)) & 255);
 return true;
}
std::string to_hex(const u8* data,size_t size) {
 static const char digits[]="0123456789abcdef";std::string result;
 for(size_t i=0;i<size;++i) {result+=digits[data[i]>>4];result+=digits[data[i]&15];}
 return result;
}
void cluster_dir(string_path& dir) { xr_sprintf(dir,".\\mailbox\\");CreateDirectoryA(dir,nullptr); }
bool cluster_name_valid(LPCSTR name) {
 if(!name || !name[0] || std::strlen(name)>63) return false;
 for(const char* c=name;*c;++c) if(!std::isalnum((unsigned char)*c) && *c!='_') return false;
 return true;
}
bool checked_move(const char* from,const char* to,DWORD flags) {
 return !fail_rename && MoveFileExA(from,to,flags)!=0;
}
#define MoveFileExA checked_move
'''+queue+r'''
void write_file(const char* name, const std::string& data) {
 std::ofstream file(name,std::ios::binary);file.write(data.data(),std::streamsize(data.size()));
}
int main() {
 const std::string id=script_transit_id();assert(id.size()==32 && transit_id_valid(id.c_str()));
 assert(!script_transit_put("../other",id.c_str(),"T0:"));
 assert(!script_transit_put("map","../../escape","T0:"));
 assert(!script_transit_put("map",id.c_str(),""));
 cooperative=false;assert(!script_transit_put("map",id.c_str(),"T0:"));cooperative=true;
 assert(script_transit_put("map",id.c_str(),"T0:"));
 const std::string expected=id+"\nT0:";
 assert(script_transit_take("map")==expected);
 assert(script_transit_take("map")==expected); // no read/claim deletion on crash
 assert(script_transit_put("map",id.c_str(),"T0:"));
 assert(!script_transit_put("map",id.c_str(),"different"));
 assert(std::string(script_transit_take("another")).empty());
 fail_rename=true;assert(!script_transit_ack("map",id.c_str()));
 assert(script_transit_take("map")==expected);fail_rename=false;
 assert(script_transit_ack("map",id.c_str()));
 assert(script_transit_ack("map",id.c_str()));
 assert(std::string(script_transit_take("map")).empty());
 assert(script_transit_put("map",id.c_str(),"T0:")); // tombstone survives source retry
 assert(!script_transit_put("map",id.c_str(),"different"));
 assert(std::string(script_transit_take("map")).empty());
 const std::string other=script_transit_id();
 fail_rename=true;assert(!script_transit_put("map",other.c_str(),"T0:"));fail_rename=false;
 assert(std::string(script_transit_take("map")).empty());
 assert(script_transit_put("map",other.c_str(),"T0:"));
 assert(script_transit_take("map")==other+"\nT0:");
 assert(script_transit_ack("map",other.c_str()));
 const std::string large=script_transit_id();
 assert(!script_transit_put("map",large.c_str(),std::string(transit_max_bytes+1,'x').c_str()));
 assert(script_transit_put("map",large.c_str(),std::string(transit_max_bytes,'x').c_str()));
 assert(std::strlen(script_transit_take("map"))==transit_max_bytes+33);
 string_path path;transit_path("map",large.c_str(),"record",path);
 write_file(path,std::string(transit_max_bytes+1,'x'));
 assert(std::string(script_transit_take("map")).empty());
 assert(GetFileAttributesA(path)!=INVALID_FILE_ATTRIBUTES); // don't discard corrupt records
 write_file(path,std::string("a\0b",3));
 assert(std::string(script_transit_take("map")).empty());
 write_file(path,"");assert(std::string(script_transit_take("map")).empty());
 write_file(path,"T0:");assert(script_transit_take("map")==large+"\nT0:");
 assert(script_transit_ack("map",large.c_str()));
 // Legacy destructive .lua/.claimed files and incomplete .tmp are never consumed.
 write_file(".\\mailbox\\transit\\map_legacy.lua","legacy");
 write_file(".\\mailbox\\transit\\map_legacy.lua.123.claimed","legacy");
 write_file(".\\mailbox\\transit\\map_incomplete.record.123.tmp","partial");
 assert(std::string(script_transit_take("map")).empty());
 // Cursor selection exposes corrupt ID without a truncated payload, then
 // rotates to a valid later record. Corruption remains for repair/inspection.
 const std::string poison(32,'0'), valid=script_transit_id();
 string_path poison_path;transit_path("map",poison.c_str(),"record",poison_path);
 write_file(poison_path,std::string("a\0b",3));
 assert(script_transit_put("map",valid.c_str(),"T0:"));
 assert(std::string(script_transit_take("map")).empty()); // legacy unchanged
 assert(script_transit_next("map","")==poison+"\n");
 assert(script_transit_next("map",poison.c_str())==valid+"\nT0:");
 assert(script_transit_next("map",valid.c_str())==poison+"\n");
 assert(std::string(script_transit_next("map","../invalid")).empty());
 assert(std::string(script_transit_next("../invalid",poison.c_str())).empty());
 assert(GetFileAttributesA(poison_path)!=INVALID_FILE_ATTRIBUTES);
 assert(script_transit_ack("map",valid.c_str()));
 assert(script_transit_next("map",valid.c_str())==poison+"\n");
 write_file(poison_path,"T0:");
 assert(script_transit_next("map",valid.c_str())==poison+"\nT0:");
 assert(script_transit_ack("map",poison.c_str()));
 assert(std::string(script_transit_next("map",poison.c_str())).empty());
 std::cout<<"PASS actual Windows mailbox: nondestructive reads, durable ack/tombstones, retry/collision, rename faults, map/path validation, exact size/NUL/corruption bounds, fair cursor selection/repair\n";
}
'''
with TemporaryDirectory(prefix="transit-mailbox-") as tmp:
    cpp = Path(tmp) / "check.cpp"
    exe = Path(tmp) / "check.exe"
    cpp.write_text(source, encoding="utf-8")
    subprocess.run(["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2", str(cpp),
                    "/Fe:"+str(exe), "/Fo:"+str(Path(tmp)/"check.obj")], check=True, cwd=tmp)
    subprocess.run([str(exe)], check=True, cwd=tmp)
