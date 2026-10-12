"""Attach only to the authorized srvtest dedicated; trace unhandled exceptions.

No dumps, locals or registers are printed: only symbol frames and known engine thread labels.
python tools/trace-srvtest-exit.py <pid> <CI dedicated directory>
"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import os
import re
import struct
import sys
import time
from symaddr import SYMBOL_INFO, IMAGEHLP_LINE64

if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
    raise SystemExit("Windows x64 only")
pid = int(sys.argv[1])
symbols = Path(sys.argv[2]).resolve()
allowed = r"J:\LostZone_Work\_work\srvtest\dedicated\LostZoneServerDX11.exe"
k = C.WinDLL("kernel32", use_last_error=True)
dbg = C.WinDLL("dbghelp", use_last_error=True)
ps = C.WinDLL("psapi", use_last_error=True)
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; k.OpenProcess.restype = W.HANDLE
k.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]; k.OpenThread.restype = W.HANDLE
k.CloseHandle.argtypes = [W.HANDLE]
ps.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
process = k.OpenProcess(0x1F0FFF, False, pid)
if not process:
    raise C.WinError(C.get_last_error())
name = C.create_unicode_buffer(4096)
if not ps.GetModuleFileNameExW(process, None, name, len(name)) or os.path.normcase(name.value) != os.path.normcase(allowed):
    k.CloseHandle(process)
    raise SystemExit("Refusing attachment outside the srvtest dedicated")

# Link the PDB's original name beside the already downloaded CI artifact.
exe = symbols / "LostZoneServerDX11.exe"
pdb = symbols / "LostZoneServerDX11.pdb"
linked = re.search(rb"RSDS.{20}([^\x00]+\.pdb)", exe.read_bytes(), re.S)
if linked and pdb.is_file():
    alias = symbols / linked.group(1).decode().split("\\")[-1]
    if not alias.exists():
        os.link(pdb, alias)

dbg.SymInitializeW.argtypes = [W.HANDLE, W.LPCWSTR, W.BOOL]
dbg.SymLoadModuleExW.argtypes = [W.HANDLE, W.HANDLE, W.LPCWSTR, W.LPCWSTR, C.c_uint64, W.DWORD, C.c_void_p, W.DWORD]
dbg.SymLoadModuleExW.restype = C.c_uint64
dbg.SymFromAddr.argtypes = [W.HANDLE, C.c_uint64, C.POINTER(C.c_uint64), C.POINTER(SYMBOL_INFO)]
dbg.SymGetLineFromAddr64.argtypes = [W.HANDLE, C.c_uint64, C.POINTER(W.DWORD), C.POINTER(IMAGEHLP_LINE64)]
dbg.SymCleanup.argtypes = [W.HANDLE]
dbg.StackWalk64.argtypes = [W.DWORD, W.HANDLE, W.HANDLE, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
k.GetThreadContext.argtypes = [W.HANDLE, C.c_void_p]
k.GetFinalPathNameByHandleW.argtypes = [W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD]
k.ReadProcessMemory.argtypes = [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
k.WaitForDebugEvent.argtypes = [C.c_void_p, W.DWORD]
k.ContinueDebugEvent.argtypes = [W.DWORD, W.DWORD, W.DWORD]
dbg.SymSetOptions(0x2 | 0x10 | 0x80000) # names/lines; no interactive symbol prompts.
if not dbg.SymInitializeW(process, str(symbols), False):
    raise C.WinError(C.get_last_error())

class Event(C.Structure):
    _fields_ = [("code",W.DWORD),("pid",W.DWORD),("tid",W.DWORD),("pad",W.DWORD),("data",C.c_ubyte*160)]


def symbol(address):
    info = SYMBOL_INFO(); info.SizeOfStruct=88; info.MaxNameLen=511
    displacement = C.c_uint64()
    text = f"0x{address:x}"
    if dbg.SymFromAddr(process, address, C.byref(displacement), C.byref(info)):
        text += " " + info.Name.decode(errors="replace") + f"+0x{displacement.value:x}"
    line = IMAGEHLP_LINE64(); line.SizeOfStruct=C.sizeof(line)
    delta = W.DWORD()
    if dbg.SymGetLineFromAddr64(process, address, C.byref(delta), C.byref(line)):
        text += " (" + line.FileName.decode(errors="replace").split("\\")[-1] + f":{line.LineNumber})"
    return text


def trace(thread_id):
    thread = k.OpenThread(0x48, False, thread_id)
    try:
        raw = C.create_string_buffer(1250)
        context_address = (C.addressof(raw)+15)&~15
        context = (C.c_ubyte*1232).from_address(context_address)
        struct.pack_into("<I", context, 48, 0x10000B)
        if not k.GetThreadContext(thread, context_address):
            print("GetThreadContext failed", C.get_last_error(), flush=True); return
        rip, rsp, rbp = (struct.unpack_from("<Q",context,offset)[0] for offset in (248,152,160))
        frame = C.create_string_buffer(4096)
        # STACKFRAME64 starts with five ADDRESS64 records (offset,segment,mode).
        for offset, address in ((0,rip),(32,rbp),(48,rsp)):
            struct.pack_into("<Q",frame,offset,address);struct.pack_into("<I",frame,offset+12,3)
        print("EXCEPTION PC", symbol(rip), flush=True)
        previous = None
        for _ in range(48):
            if not dbg.StackWalk64(0x8664,process,thread,frame,context_address,None,
                                  C.cast(dbg.SymFunctionTableAccess64,C.c_void_p),C.cast(dbg.SymGetModuleBase64,C.c_void_p),None): break
            address = struct.unpack_from("<Q",frame,0)[0]
            if not address or address == previous: break
            print("  ",symbol(address),flush=True);previous=address
    finally:
        if thread: k.CloseHandle(thread)


attached = False
thread_names = {}
known_threads = {b"X-RAY Discord thread", b"X-RAY Secondary thread", b"Freeze detecting thread", b"X-RAY Primary thread"}
try:
    if not k.DebugActiveProcess(pid): raise C.WinError(C.get_last_error())
    attached=True;k.DebugSetProcessKillOnExit(False)
    print("Attached to srvtest",pid,flush=True)
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        event=Event()
        if not k.WaitForDebugEvent(C.byref(event),1000): continue
        data=bytes(event.data); continuation=0x10002
        if event.code in (3,6):
            handle=struct.unpack_from("<Q",data,0)[0]
            base=struct.unpack_from("<Q",data,24 if event.code==3 else 8)[0]
            path=C.create_unicode_buffer(4096)
            if handle and k.GetFinalPathNameByHandleW(handle,path,len(path),0):
                filename=path.value.removeprefix("\\\\?\\")
                dbg.SymLoadModuleExW(process,None,filename,None,base,0,None,0)
            if handle:k.CloseHandle(handle)
        elif event.code==1:
            code=struct.unpack_from("<I",data,0)[0];first=struct.unpack_from("<I",data,152)[0]
            # MSVC's thread-name exception carries a public literal, not locals.
            # Only source-verified engine labels may appear in the output.
            if code==0x406D1388 and first and struct.unpack_from("<I",data,24)[0]>=3:
                kind,address,thread_id=struct.unpack_from("<QQQ",data,32)
                label=C.create_string_buffer(128);read=C.c_size_t()
                if kind & 0xffffffff==0x1000 and address and k.ReadProcessMemory(process,address,label,len(label),C.byref(read)):
                    value=bytes(label).split(b"\0",1)[0]
                    if value in known_threads:
                        thread_names[event.tid if thread_id & 0xffffffff==0xffffffff else thread_id & 0xffffffff]=value.decode()
            if code!=0x80000003:
                continuation=0x80010001
                if not first:
                    print(f"Unhandled exception 0x{code:x}",flush=True)
                    print("Exception thread:",thread_names.get(event.tid,"unclassified engine thread"),flush=True)
                    trace(event.tid)
        elif event.code==4:
            thread_names.pop(event.tid,None)
        elif event.code==5:
            print(f"Exit code 0x{struct.unpack_from('<I',data,0)[0]:x}",flush=True)
            k.ContinueDebugEvent(event.pid,event.tid,continuation); attached=False;break
        k.ContinueDebugEvent(event.pid,event.tid,continuation)
finally:
    if attached:k.DebugActiveProcessStop(pid)
    dbg.SymCleanup(process);k.CloseHandle(process)
