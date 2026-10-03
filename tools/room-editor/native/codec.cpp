#include "standalone.h"
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
