r"""One "resources" folder for every archive of a release (owner 2026-10-10).

The engine reads fsgame lines top to bottom and each folder in name order; a
file registered later replaces an earlier one. The old layout had one line per
db subfolder. Here every archive moves into resources/ with a prefix that keeps
the old order, and fsgame gets one line for it:

  00 db\*.db*          (files, shaders)    60 db\mods
  10 db\configs                            70 db\patches
  20 db\levels                             80 db\addons
  30 db\meshes                             90 db\lostzone (Lost Zone data, sealed scripts/overlay)
  40 db\sounds                             99 db\lostzone_updates (patches: 99_lz_patch_NNNNNN)
  50 db\textures

Only top-level archives of each folder were mounted (non-recursive lines), so
only those move. Files are renamed on the same disk: hardlinks between the
player and server folders stay one copy. Nothing is executed; archives are not
rewritten (LZPACK1 does not bind its file name). A mapping goes to _work.
"""
from pathlib import Path
import argparse, json, os, re, shutil, time

ORDER = (('', '00'), ('configs', '10'), ('levels', '20'), ('meshes', '30'), ('sounds', '40'),
         ('textures', '50'), ('mods', '60'), ('patches', '70'), ('addons', '80'),
         ('lostzone', '90'), ('lostzone_updates', '99'))

FSGAME_BLOCK = (
    "; Lost Zone: every resource archive in one folder, mounted in name order (a later\n"
    "; name overrides an earlier one): 00 base, 10 configs, 20 levels, 30 meshes,\n"
    "; 40 sounds, 50 textures, 60 mods, 70 patches, 80 addons, 90 Lost Zone,\n"
    "; 99 updates (99_lz_patch_NNNNNN: the higher number wins).\n"
    "$arch_dir$ = false | false | {ROOT}resources\\\n")


def is_archive(path):
    return path.is_file() and path.suffix.lower().startswith('.db') and path.name.lower() != 'thumbs.db'


def target_name(sub, prefix, name):
    if sub == 'lostzone_updates':
        name = re.sub(r'^99_', '', name)
        return f'99_{name}'
    return f'{prefix}_{sub}_{name}' if sub else f'{prefix}_{name}'


def plan(folder):
    db = folder / 'db'
    moves = []
    for sub, prefix in ORDER:
        source = db / sub if sub else db
        if not source.is_dir():
            continue
        for path in sorted(source.iterdir(), key=lambda p: p.name.lower()):
            if is_archive(path):
                moves.append((path, folder / 'resources' / target_name(sub, prefix, path.name)))
            elif sub == 'lostzone_updates' and path.is_file():
                moves.append((path, folder / 'resources' / ('99_' + re.sub(r'^99_', '', path.name))))
    names = [t.name.lower() for _, t in moves]
    if len(names) != len(set(names)):
        raise ValueError('Two archives would get the same name in ' + str(folder))
    return moves


def rewrite_fsgame(path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    out, inserted = [], False
    for line in lines:
        key = line.split('=', 1)[0].strip().lower()
        if key == '$game_arch_mp$':
            out.append('$game_arch_mp$ = false | false | {ROOT}resources\\mp\\\n')
            continue
        if key.startswith('$arch_dir'):
            if not inserted:
                out.append(FSGAME_BLOCK)
                inserted = True
            continue
        if line.lstrip().startswith('; Lost Zone: GAMMA') or line.lstrip().startswith('; Versioned fixes'):
            continue
        out.append(line)
    if not inserted:
        raise ValueError('No $arch_dir$ lines in ' + str(path))
    path.write_text(''.join(out), encoding='utf-8', newline='')


def flatten(folder, retained):
    folder = Path(folder)
    moves = plan(folder)
    resources = folder / 'resources'
    resources.mkdir(exist_ok=True)
    for source, target in moves:
        if target.exists():
            raise FileExistsError(target)
    mapping = []
    for source, target in moves:
        os.replace(source, target)
        mapping.append({'from': str(source.relative_to(folder)), 'to': str(target.relative_to(folder))})
    # whatever is left in db was never mounted (subfolders of non-recursive
    # lines, notes): keep it outside the distributable, do not delete it
    db = folder / 'db'
    if db.exists():
        leftovers = [p for p in db.rglob('*') if p.is_file()]
        if leftovers:
            keep = Path(retained) / folder.name / 'db_unmounted'
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(db), str(keep))
        else:
            shutil.rmtree(db)
    for template in folder.glob('fsgame*.template'):
        rewrite_fsgame(template)
    for live in folder.glob('fsgame*.ltx'):
        rewrite_fsgame(live)
    (Path(retained) / f'resources_{folder.name}.json').write_text(json.dumps(mapping, indent=2), encoding='utf-8')
    return mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='folder with "Lost Zone" and "Lost Zone Server"')
    args = parser.parse_args()
    folders = [args.out / 'Lost Zone', args.out / 'Lost Zone Server']
    for folder in folders:
        if (folder / 'UPDATING.lock').exists():
            raise RuntimeError('Release is still being assembled: ' + str(folder))
    retained = args.out / '_work' / ('resources_layout_' + time.strftime('%Y%m%d_%H%M%S'))
    retained.mkdir(parents=True, exist_ok=False)
    for folder in folders:
        if folder.exists():
            moved = flatten(folder, retained)
            print(f'{folder.name}: {len(moved)} archives -> resources', flush=True)
    print('PASS one resources folder per release; mapping in ' + str(retained), flush=True)


if __name__ == '__main__':
    main()
