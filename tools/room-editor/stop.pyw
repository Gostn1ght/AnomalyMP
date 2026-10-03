from pathlib import Path
import ctypes, json, urllib.request
here=Path(__file__).resolve().parent
try:
    with urllib.request.urlopen('http://127.0.0.1:18743/api/config',timeout=2) as response:
        info=json.load(response)
    if info.get('tool')=='lostzone-room-editor' and Path(info['folder']).resolve()==here:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint]
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(1,False,info['pid'])
        if handle:
            kernel.TerminateProcess(handle,0);kernel.CloseHandle(handle)
except Exception:pass
