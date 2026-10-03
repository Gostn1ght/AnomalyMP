@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /O2 /MT /LD /EHsc codec.cpp LzHuf.cpp rt_lzo1x_d2.cpp /link /OUT:../vendor/xray-codecs.dll
