"""Actual CNG reader + stream-window methods. Compile only in GHA."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import sys
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native checks must run in GitHub Actions')
if os.name!='nt':raise SystemExit('CNG reader check needs Windows')
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools/lzpack'));import lzpack
stream=(root/'src/xrCore/stream_reader.cpp').read_text(encoding="utf-8")
inline=(root/'src/xrCore/stream_reader_inline.h').read_text(encoding="utf-8")

def function(text, signature):
    start=text.index(signature);brace=text.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

source=r'''
#include "lzpack_archive.h"
#include <algorithm>
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <thread>
#include <vector>
#include <cstdio>
#define IC
#define VERIFY(x) assert(x)
#define R_ASSERT2(x,m) do{if(!(x))throw std::runtime_error(m);}while(0)
#define FATAL(m) throw std::runtime_error(m)
using u8=unsigned char;using u32=std::uint32_t;
template<class T>T _max(T a,T b){return (std::max)(a,b);}
template<class T>T _min(T a,T b){return (std::min)(a,b);}
template<class T>T* xr_alloc(u32 n){return static_cast<T*>(std::malloc(n*sizeof(T)));}
template<class T>void xr_free(T*&p){std::free(p);p=nullptr;}
struct {u32 dwAllocGranularity=65536;}FS;
struct{void mem_copy(void*a,const void*b,size_t n){std::memcpy(a,b,n);}}Memory;
class CStreamReader{
 HANDLE m_file_mapping_handle=nullptr;u32 m_start_offset=0,m_file_size=0,m_archive_size=0,m_window_size=0;
 u32 m_current_offset_from_start=0,m_current_window_size=0;
 u8* m_current_map_view_of_file=nullptr;u8* m_start_pointer=nullptr;u8* m_current_pointer=nullptr;
 std::shared_ptr<LZPackArchive>m_protected_archive;
public:
 void construct(const HANDLE&,const u32&,const u32&,const u32&,const u32&,std::shared_ptr<LZPackArchive>);
 void destroy();void map(const u32&);void unmap();void remap(const u32&);
 void advance(const int&);void r(void*,u32);void seek(const int&);u32 tell()const;u32 elapsed()const;
};
'''
source += '\n'.join(function(stream,s) for s in (
    'void CStreamReader::construct(','void CStreamReader::destroy(','void CStreamReader::map(',
    'void CStreamReader::advance(','void CStreamReader::r('))
source += '\n' + '\n'.join(function(inline,s) for s in (
    'IC void CStreamReader::unmap(','IC void CStreamReader::remap(','IC u32 CStreamReader::elapsed(',
    'IC void CStreamReader::seek(','IC u32 CStreamReader::tell('))
source += r'''
int main(int argc,char**argv){
 assert(argc==5);
 std::ifstream input(argv[1],std::ios::binary);std::vector<u8>expected((std::istreambuf_iterator<char>(input)),{});
 HANDLE file=CreateFileA(argv[2],GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
 assert(file!=INVALID_HANDLE_VALUE);u32 physical=GetFileSize(file,nullptr);
 HANDLE mapping=CreateFileMapping(file,nullptr,PAGE_READONLY,0,0,nullptr);assert(mapping);
 auto archive=LZPackArchive::open(mapping,physical);assert(archive&&archive->length()==expected.size());
 auto run=[&](){std::vector<u8>buffer(90000);archive->read(65000,buffer.data(),90000);
  assert(std::equal(buffer.begin(),buffer.end(),expected.begin()+65000));};
 std::thread one(run),two(run);one.join();two.join();
 CStreamReader reader;reader.construct(mapping,0,archive->length(),archive->length(),65536,archive);
 std::vector<u8>whole(expected.size());reader.r(whole.data(),static_cast<u32>(whole.size()));
 assert(whole==expected&&reader.elapsed()==0);reader.r(nullptr,0);
 for(int offset:{0,65535,65536,130000,4,190000}){
  reader.seek(offset);std::vector<u8>part(37);reader.r(part.data(),static_cast<u32>(part.size()));
  assert(std::equal(part.begin(),part.end(),expected.begin()+offset));
 }
 CStreamReader child;child.construct(mapping,15,123456,archive->length(),65536,archive);
 std::vector<u8>part(123456);child.r(part.data(),static_cast<u32>(part.size()));
 assert(std::equal(part.begin(),part.end(),expected.begin()+15));child.destroy();reader.destroy();
 bool rejected=false;try{archive->read(archive->length(),whole.data(),1);}catch(const std::exception&){rejected=true;}assert(rejected);
 archive.reset();CloseHandle(mapping);CloseHandle(file);
 for(int index=3;index!=5;++index){
  file=CreateFileA(argv[index],GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);assert(file!=INVALID_HANDLE_VALUE);
  physical=GetFileSize(file,nullptr);mapping=CreateFileMapping(file,nullptr,PAGE_READONLY,0,0,nullptr);
  rejected=false;try{archive=LZPackArchive::open(mapping,physical);archive->read(65536,whole.data(),65536);}catch(const std::exception&){rejected=true;}
  assert(rejected);archive.reset();CloseHandle(mapping);CloseHandle(file);
 }
 std::puts("PASS actual CNG and stream reader: interoperability, parallel/random/cross-block/EOF/nested-window reads, bounds and authentication failures");
}
'''
with TemporaryDirectory() as tmp:
    temp=Path(tmp);raw=temp/'plain.db';encrypted=temp/'protected.db0';cpp=temp/'reader.cpp';exe=temp/'reader.exe'
    raw.write_bytes(bytes((i*13)%251 for i in range(3*lzpack.BLOCK+37)))
    lzpack.protect(raw,encrypted,bytes(range(32)))
    data=bytearray(encrypted.read_bytes());data[24]^=1;(temp/'bad-header.db0').write_bytes(data)
    data=bytearray(encrypted.read_bytes());data[48+lzpack.BLOCK+lzpack.TAG+1]^=1;(temp/'bad-block.db0').write_bytes(data)
    (temp/'lzpack_fixture_key.h').write_text('static const unsigned char lzpack_master_key[32]={'+','.join(str(i)for i in range(32))+'};')
    cpp.write_text(source,encoding="utf-8")
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/W4','/WX','/DLZPACK_STANDALONE','/DNOMINMAX',
                    '/I'+str(temp),'/I'+str(root/'src/xrCore'),str(cpp),str(root/'src/xrCore/lzpack_archive.cpp'),
                    '/Fe:'+str(exe)],cwd=tmp,check=True)
    subprocess.run([str(exe),str(raw),str(encrypted),str(temp/'bad-header.db0'),str(temp/'bad-block.db0')],cwd=tmp,check=True)
