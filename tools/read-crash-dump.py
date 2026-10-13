"""Read a Lost Zone crash dump: the exception, then every address on the
crashing thread's stack that points into the game exe, named from its PDB.

    python tools/read-crash-dump.py <dump.mdmp> <exe with its .pdb next to it> [--all-threads]

A heuristic stack scan (no unwinding): frames appear innermost first; stale
return addresses left on the stack can show up between the real ones."""
import ctypes
import struct
import sys
from ctypes import wintypes
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

sys.path.insert(0, str(Path(__file__).parent))
import symaddr  # noqa: E402  (dbghelp structures)


def symbolizer(exe):
    # The exe names its PDB as linked; the package ships it as <exe>.pdb.
    import re, shutil
    linked = re.search(rb"RSDS.{20}([^\x00]+\.pdb)", Path(exe).read_bytes(), re.S)
    pdb = Path(exe).with_suffix(".pdb")
    if linked and pdb.exists():
        target = Path(exe).parent / linked.group(1).decode(errors="replace").split("\\")[-1]
        if not target.exists():
            shutil.copy2(pdb, target)
    dbghelp = ctypes.WinDLL("dbghelp.dll")
    process = ctypes.c_void_p(0x1234)
    dbghelp.SymSetOptions(0x2 | 0x10)
    dbghelp.SymInitialize.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.BOOL]
    dbghelp.SymLoadModuleEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                                        ctypes.c_uint64, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dbghelp.SymLoadModuleEx.restype = ctypes.c_uint64
    dbghelp.SymFromAddr.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(symaddr.SYMBOL_INFO)]
    dbghelp.SymGetLineFromAddr64.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.POINTER(symaddr.IMAGEHLP_LINE64)]
    dbghelp.SymInitialize(process, str(Path(exe).parent).encode(), False)
    base = dbghelp.SymLoadModuleEx(process, None, str(exe).encode(), None, symaddr.BASE, 0, None, 0)
    if not base:
        raise SystemExit("cannot load symbols for " + str(exe))

    def name(address):
        info = symaddr.SYMBOL_INFO()
        info.SizeOfStruct = ctypes.sizeof(symaddr.SYMBOL_INFO) - 512
        info.MaxNameLen = 511
        displacement = ctypes.c_uint64(0)
        if not dbghelp.SymFromAddr(process, address, ctypes.byref(displacement), ctypes.byref(info)):
            return None
        text = f"{info.Name.decode(errors='replace')}+0x{displacement.value:x}"
        line = symaddr.IMAGEHLP_LINE64()
        line.SizeOfStruct = ctypes.sizeof(symaddr.IMAGEHLP_LINE64)
        line_displacement = wintypes.DWORD(0)
        if dbghelp.SymGetLineFromAddr64(process, address, ctypes.byref(line_displacement), ctypes.byref(line)):
            text += f"  {Path(line.FileName.decode(errors='replace')).name}:{line.LineNumber}"
        return text
    return name


def main():
    dump = MinidumpFile.parse(sys.argv[1])
    exe = Path(sys.argv[2])
    name = symbolizer(exe)
    exe_module = next(m for m in dump.modules.modules if m.name.lower().endswith(exe.name.lower()))
    low, high = exe_module.baseaddress, exe_module.baseaddress + exe_module.size
    to_pdb = lambda a: a - low + symaddr.BASE
    reader = dump.get_reader()
    exc = dump.exception.exception_records[0] if dump.exception else None
    crashed = exc.ThreadId if exc else None
    if exc:
        rec = exc.ExceptionRecord
        code = getattr(rec.ExceptionCode, "value", rec.ExceptionCode)
        print(f"exception {rec.ExceptionCode} ({code}) at 0x{rec.ExceptionAddress:x} thread {crashed}")
        if low <= rec.ExceptionAddress < high:
            print("   ", name(to_pdb(rec.ExceptionAddress)) or "(no symbol)")
    for thread in dump.threads.threads:
        if crashed is not None and thread.ThreadId != crashed and "--all-threads" not in sys.argv:
            continue
        stack = thread.Stack
        try:
            data = reader.read(stack.StartOfMemoryRange, stack.MemoryLocation.DataSize)
        except Exception as error:
            print("thread", thread.ThreadId, "stack unreadable:", error)
            continue
        print(f"--- thread {thread.ThreadId}")
        last = None
        for offset in range(0, len(data) - 7, 8):
            value, = struct.unpack_from("<Q", data, offset)
            if low <= value < high and value != last:
                text = name(to_pdb(value))
                if text:
                    print(f"  {to_pdb(value):x}  {text}")
                    last = value


if __name__ == "__main__":
    main()
