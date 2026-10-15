"""Bounded source-only archive readers: no supplied executable is run."""
import importlib.util
import io
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vehicle_audit', ROOT/'tools/audit-vehicle-sources.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def rejected(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return
    raise AssertionError('Malformed input accepted')


for path in ('../outside','/absolute','C:/absolute','a/NUL.txt','a/CON','a/b?c','a\0b','a/../b','bad\ufffd.c',''):
    rejected(audit.safe_path,path)
assert str(audit.safe_path('config\\models\\vehicles\\car.ltx')) == 'config/models/vehicles/car.ltx'
literal = b'\x07abc' + struct.pack('<I',sum(b'abc'))
assert audit.pbo_lzss(literal,3) == b'abc'
repeat = b'\x07abc\x03\x03' + struct.pack('<I',sum(b'abcabcabc'))
assert audit.pbo_lzss(repeat,9) == b'abcabcabc'
spaces = b'\x00\x01\x00'+struct.pack('<I',96)
assert audit.pbo_lzss(spaces,3) == b'   '
for raw, size in ((b'',3),(literal[:-1],3),(literal,0),(literal,2*1024*1024+1),
                  (b'\x00\x00\x00'+struct.pack('<I',0),3),(b'\x00\x01'+struct.pack('<I',0),3)):
    rejected(audit.pbo_lzss,raw,size)
bad = literal[:-4]+struct.pack('<I',999)
rejected(audit.pbo_lzss,bad,3)
# Minimal real PBO framing with two same-name entries, a normal Vers prefix,
# and an offset/size check. Nothing is extracted or executed by this check.
version = b'\0'+struct.pack('<5I',0x56657273,0,0,0,0)+b'prefix\0HelicopterTest\0\0'
entry = b'config.cpp\0'+struct.pack('<5I',0,3,0,0,3)
data = version+entry+entry+b'\0'+bytes(20)+b'abcxyz'
entries, props = audit.pbo_entries(data)
assert props['prefix']=='HelicopterTest' and len(entries)==2
assert data[entries[0]['offset']:entries[0]['offset']+3]==b'abc'
assert data[entries[1]['offset']:entries[1]['offset']+3]==b'xyz'
rejected(audit.pbo_entries,data[:-1])
rejected(audit.xdb_entries,io.BytesIO(struct.pack('<II',1,100)),8)
print('PASS vehicle source audit: paths/devices, bounded Cprs literals/references/spaces/checksum, duplicate PBO names, offsets and truncated XDB')
