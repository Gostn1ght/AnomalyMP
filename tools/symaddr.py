"""Symbolise module+offset addresses in a log (e.g. [mem-profile] lines) with
the build's PDB through the system dbghelp.dll.

    python tools/symaddr.py <exe with its .pdb next to it> <log> [pattern]

Every "Name.exe+hex" in the matching lines (default "[mem-profile]") gets the
function and source line appended."""
import ctypes
import re
import sys
from ctypes import wintypes

BASE = 0x140000000


class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG), ("Reserved", ctypes.c_uint64 * 2),
                ("Index", wintypes.ULONG), ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
                ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64), ("Address", ctypes.c_uint64),
                ("Register", wintypes.ULONG), ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
                ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG), ("Name", ctypes.c_char * 512)]


class IMAGEHLP_LINE64(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.DWORD), ("Key", ctypes.c_void_p), ("LineNumber", wintypes.DWORD),
                ("FileName", ctypes.c_char_p), ("Address", ctypes.c_uint64)]


def main():
    exe, log = sys.argv[1], sys.argv[2]
    pattern = sys.argv[3] if len(sys.argv) > 3 else "[mem-profile]"
    # The exe names its PDB as linked (LostZoneDX11.pdb); the package ships it
    # as <exe>.pdb. dbghelp looks for the linked name next to the exe.
    import os
    exe = os.path.abspath(exe)
    folder, pdb = os.path.dirname(exe), os.path.splitext(exe)[0] + ".pdb"
    data = open(exe, "rb").read()
    linked = re.search(rb"RSDS.{20}([^\x00]+\.pdb)", data, re.S)
    if linked and os.path.exists(pdb):
        target = os.path.join(folder, linked.group(1).decode(errors="replace").split("\\")[-1])
        if not os.path.exists(target):
            os.link(pdb, target)
    dbghelp = ctypes.WinDLL("dbghelp.dll")
    process = ctypes.c_void_p(0x1234)  # any unique value works without a live process
    dbghelp.SymSetOptions(0x2 | 0x10)  # UNDNAME | LOAD_LINES
    dbghelp.SymInitialize.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.BOOL]
    dbghelp.SymLoadModuleEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                                        ctypes.c_uint64, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dbghelp.SymFromAddr.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYMBOL_INFO)]
    dbghelp.SymGetLineFromAddr64.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.POINTER(IMAGEHLP_LINE64)]
    if not dbghelp.SymInitialize(process, folder.encode(), False):
        raise SystemExit("SymInitialize failed")
    dbghelp.SymLoadModuleEx.restype = ctypes.c_uint64
    base = dbghelp.SymLoadModuleEx(process, None, exe.encode(), None, BASE, 0, None, 0)
    if not base:
        raise SystemExit("SymLoadModuleEx failed for " + exe)
    module = exe.replace("/", "\\").split("\\")[-1].lower()
    cache = {}

    def name(offset):
        if offset in cache:
            return cache[offset]
        info = SYMBOL_INFO()
        info.SizeOfStruct = 88  # sizeof(SYMBOL_INFO) with a 1-char name
        info.MaxNameLen = 511
        displacement = ctypes.c_uint64()
        text = "?"
        if dbghelp.SymFromAddr(process, base + offset, ctypes.byref(displacement), ctypes.byref(info)):
            text = info.Name.decode(errors="replace")
        line = IMAGEHLP_LINE64()
        line.SizeOfStruct = ctypes.sizeof(IMAGEHLP_LINE64)
        d32 = wintypes.DWORD()
        if dbghelp.SymGetLineFromAddr64(process, base + offset, ctypes.byref(d32), ctypes.byref(line)):
            text += " (%s:%d)" % (line.FileName.decode(errors="replace").split("\\")[-1], line.LineNumber)
        cache[offset] = text
        return text

    for raw in open(log, encoding="cp1251", errors="replace"):
        if pattern not in raw:
            continue
        out = raw.rstrip()
        for m in re.finditer(r"([\w.]+)\+([0-9a-fA-F]+)", raw):
            if m.group(1).lower() == module:
                out += "\n      " + m.group(0) + " = " + name(int(m.group(2), 16))
        print(out)


if __name__ == "__main__":
    main()
