"""Read owner-provided DCP/DayZ packages without installing or executing them.

Writes a bounded catalogue and selected text/config sources into a separate
audit directory. No DLL, executable, model or texture is imported into a game.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xray_index', ROOT/'tools/read-xray-sound-archive.py')
xray = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xray)


def safe_path(name):
    name = name.replace('\\', '/')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('..', '.') or p.rstrip(' .') != p or
            any(c in '<>:"|?*\ufffd' or ord(c) < 32 for c in p) for p in path.parts):
        raise ValueError('Unsafe archive path')
    return path


def xdb_entries(stream, length):
    while stream.tell() < length:
        header = stream.read(8)
        if len(header) != 8:
            raise ValueError('Truncated XDB header')
        kind, size = struct.unpack('<II', header)
        if stream.tell()+size > length:
            raise ValueError('XDB chunk outside archive')
        if kind & 0x7fffffff != 1:
            stream.seek(size, 1)
            continue
        if size > 16*1024*1024:
            raise ValueError('XDB index exceeds audit budget')
        table = stream.read(size)
        if kind & 0x80000000:
            table = xray.decompress_lzhuf(table)
        result, pos = [], 0
        while pos < len(table):
            n, = struct.unpack_from('<H', table, pos)
            pos += 2
            if n < 16 or pos+n > len(table):
                raise ValueError('Malformed XDB entry')
            real, packed, crc = struct.unpack_from('<III', table, pos)
            name = table[pos+12:pos+n-4].decode('cp1251')
            offset, = struct.unpack_from('<I', table, pos+n-4)
            safe_path(name)
            if offset+packed > length:
                raise ValueError('XDB payload outside archive')
            result.append(dict(name=name, size=real, packed=packed, crc=crc, offset=offset))
            pos += n
        return result
    raise ValueError('XDB table missing')


def cstring(stream):
    result = bytearray()
    while len(result) <= 4096:
        char = stream.read(1)
        if char == b'\0':
            return result.decode('utf-8', errors='replace')
        if not char:
            raise ValueError('Truncated PBO string')
        result.extend(char)
    raise ValueError('PBO string too large')


def pbo_entries(data):
    stream, entries, properties = io.BytesIO(data), [], {}
    while True:
        name = cstring(stream)
        raw = stream.read(20)
        if len(raw) != 20:
            raise ValueError('Truncated PBO entry')
        method, original, reserved, timestamp, stored = struct.unpack('<5I', raw)
        if not name and method == 0x56657273:  # Vers: extended properties
            while key := cstring(stream):
                properties[key] = cstring(stream)
            continue
        if not name:
            break
        try:
            safe_path(name)
            unsafe = False
        except ValueError:
            unsafe = True  # catalogue obfuscated entries, never extract them
        if len(entries) >= 100000:
            raise ValueError('PBO catalogue too large')
        entries.append(dict(name=name, method=method, size=original or stored, packed=stored, unsafe_path=unsafe))
    offset = stream.tell()
    for entry in entries:
        entry['offset'] = offset
        offset += entry['packed']
    if offset > len(data):
        raise ValueError('PBO payload outside archive')
    return entries, properties


def wanted_text(name):
    name = name.lower().replace('\\', '/')
    return (any(term in name for term in ('license', 'readme', 'copyright', 'instruction')) or
            (name.endswith(('.ltx', '.script', '.xml', '.c', '.cpp', '.cfg', '.txt')) and
             any(term in name for term in ('car', 'vehicle', 'helicop', 'rotor', 'fuel', 'transmission'))))


def write_source(output, archive, member, name, raw):
    path = output/'text'/archive/member/Path(*safe_path(name).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('archives', nargs='+', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = []
    for archive in args.archives:
        item = dict(archive=archive.name, size=archive.stat().st_size, members=[])
        with archive.open('rb') as source:
            item['sha256'] = hashlib.file_digest(source, 'sha256').hexdigest()
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                if member.is_dir():
                    continue
                safe_path(member.filename)
                record = dict(name=member.filename, size=member.file_size, crc=member.CRC)
                base = PurePosixPath(member.filename).name
                if base.lower().startswith('mod_zzz_dcp') and '.xdb' in base.lower():
                    with package.open(member) as stream:
                        entries = xdb_entries(stream, member.file_size)
                    record['entries'] = entries
                    selected = sorted((e for e in entries if wanted_text(e['name']) and e['size'] <= 2*1024*1024), key=lambda e:e['offset'])
                    if sum(e['size'] for e in selected) > 32*1024*1024:
                        raise ValueError('Selected source budget exceeded')
                    with package.open(member) as stream:
                        for entry in selected:
                            stream.seek(entry['offset'])
                            raw = stream.read(entry['packed'])
                            if entry['packed'] != entry['size']:
                                import lzokay
                                raw = lzokay.decompress(raw, entry['size'])
                            if len(raw) != entry['size'] or zlib.crc32(raw) != entry['crc']:
                                raise ValueError('XDB payload length/CRC mismatch')
                            write_source(args.output, archive.name, base, entry['name'], raw)
                    record['selected_text_files'] = len(selected)
                elif base.lower().endswith('.pbo'):
                    if member.file_size > 512*1024*1024:
                        raise ValueError('PBO exceeds audit budget')
                    raw = package.read(member)
                    entries, properties = pbo_entries(raw)
                    record.update(entries=entries, properties=properties)
                    # Packed DayZ script/model formats need their own decoder.
                    # Keep only directly readable sources, without interpreting code.
                    for entry in entries:
                        if not entry['unsafe_path'] and wanted_text(entry['name']) and entry['method'] == 0 and entry['size'] <= 2*1024*1024:
                            data = raw[entry['offset']:entry['offset']+entry['packed']]
                            write_source(args.output, archive.name, base, entry['name'], data)
                elif member.file_size <= 100000 and base.lower().endswith(('.md', '.txt', '.ini', '.cpp')):
                    write_source(args.output, archive.name, 'package', member.filename, package.read(member))
                item['members'].append(record)
        report.append(item)
        print(archive.name, 'catalogued', len(item['members']), 'members', flush=True)
        (args.output/'catalogue.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
