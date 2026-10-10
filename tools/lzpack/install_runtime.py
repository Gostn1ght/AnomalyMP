r"""Put the app-local runtime next to installed release executables.

A GHA package (scripts/package-m1-dx11.ps1) carries every DLL the client and
server import: transport, ICU, TBB, OpenAL, Discord, D3DX and the VC143
runtime. An older release folder may hold only the exe. This copies the
package's DLLs (never its exe or PDB, which stay the qualified ones) into
bin\ and dedicated\ and then reads the PE import tables
(scripts/check-portable-binaries.py). Nothing is executed.
"""
from pathlib import Path
import argparse, importlib.util, shutil

ROOT = Path(__file__).resolve().parents[2]


def install(package, game, server):
    copied = []
    for source, target in ((package / 'bin', game / 'bin'), (package / 'dedicated', server / 'dedicated')):
        if not target.is_dir():
            continue
        for dll in sorted(source.glob('*.dll')):
            dest = target / dll.name
            if not dest.exists():
                shutil.copy2(dll, dest)
                copied.append(str(dest))
    return copied


def verify(game, server):
    spec = importlib.util.spec_from_file_location('ports', ROOT / 'scripts/check-portable-binaries.py')
    ports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ports)
    errors = []
    for folder, exe in ((game / 'bin', 'LostZoneClientDX11.exe'), (server / 'dedicated', 'LostZoneServerDX11.exe')):
        if not folder.is_dir():
            continue
        files = {p.name.lower(): p for p in folder.iterdir() if p.is_file()}
        for name in (exe,) + ports.REQUIRED:
            if name.lower() not in files:
                errors.append(f'{folder}: missing {name}')
        for name, path in files.items():
            if path.suffix.lower() not in ('.exe', '.dll'):
                continue
            for dependency in ports.imports(path):
                if dependency in files or dependency.startswith(('api-ms-win-', 'ext-ms-win-')):
                    continue
                if dependency.endswith('.dll') and dependency[:-4] in ports.SYSTEM:
                    continue
                errors.append(f'{folder}/{path.name}: unresolved {dependency}')
    if errors:
        raise ValueError('\n'.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path, help='unpacked GHA LostZone-DX11-client-server')
    parser.add_argument('--out', required=True, type=Path, help='folder with "Lost Zone" and "Lost Zone Server"')
    args = parser.parse_args()
    game, server = args.out / 'Lost Zone', args.out / 'Lost Zone Server'
    copied = install(args.package, game, server)
    verify(game, server)
    print(f'PASS runtime next to the executables: {len(copied)} DLL(s) added; imports resolve; nothing executed')


if __name__ == '__main__':
    main()
