r"""Server add-on for a player's Lost Zone folder (owner 2026-10-10).

"Сделай сервер чисто всё что надо накинуть на игру": a friend who has the
game (Lost Zone) gets a small folder and copies its contents next to bin\.
The add-on holds only what the game folder does not have:

  dedicated\                 the server exe and its libraries
  server\configs\            server configs (loose, GAMMA mods write them)
  server\scripts\            empty: the scripts are in the sealed archive
  resources\95_server_*.db*  server-only archives (the server's scripts);
                             every other archive is the game's own
  hoster\                    location panel, watchdog, cluster plans
  fsgame_server.template, Start Server Panel.cmd, Admin Rights.cmd,
  README-server-addon.txt

The game's resources\ already has everything else (levels, meshes, sounds,
GAMMA, Lost Zone data). An archive with the same name in both is compared by
content: identical ones are not copied; a different one must be the server's
own scripts (entry point server\scripts, never read by the game) and becomes
95_server_<name>; anything else stops the build. Files are copied, not linked:
the folder can be sent as it is. Nothing is executed.
"""
from pathlib import Path
import argparse, hashlib, os, shutil, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lzpack

ADDON_README = """Lost Zone - сервер для папки с игрой

Скопируйте СОДЕРЖИМОЕ этой папки в папку игры Lost Zone (туда, где лежат bin,
resources и Play Lost Zone.cmd). Совпадающих файлов игры нет, ничего не заменяется.

Запуск: Start Server Panel.cmd. Карты по умолчанию: Болота, Кордон, Свалка,
Поляна, Бар и Агропром; подземелье Агропрома запускается, когда туда идёт игрок
(appdata/server/netcoop_cluster.ltx, создаётся из hoster/netcoop_cluster.ltx.six
при первом запуске). Для игры через интернет замените 127.0.0.1 на внешний
адрес и откройте UDP-порты карт из этого файла.

Админка: Admin Rights.cmd показывает аккаунты, спрашивает логин и роль
(admin или player). Игрок сначала регистрируется на сервере; права действуют
со следующего входа. Выдавайте права, пока игрок не в игре: его сервер может
записать старую роль при сохранении. Админ в игре: меню отладки и спавна
(F7 или Num3), режим бога, телепорт, одобрение новых регистраций.

Сервер берёт ресурсы игры из resources/; свои архивы - resources/95_server_*.
Миры, аккаунты и персонажи создаются в appdata/server/. Не удаляйте эту папку.
"""


# Examples and dumps the panel never reads (it needs the .six/.full plans and
# the panel/watchdog/controls scripts only).
HOSTER_EXTRAS = shutil.ignore_patterns('*.example', 'changers_dump.txt')


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def plain_digest(path, key):
    """SHA256 of the archive's content: each folder is sealed with its own
    random salt, so the same content differs byte for byte when sealed."""
    with open(path, 'rb') as f:
        sealed = f.read(8) == lzpack.MAGIC
    if not sealed:
        return digest(path)
    reader, h, pos = lzpack.Reader(path, key), hashlib.sha256(), 0
    while pos < reader.size:
        n = min(1 << 22, reader.size - pos)
        h.update(reader.read(pos, n))
        pos += n
    return h.hexdigest()


def same(a, b, key):
    try:
        if os.path.samefile(a, b):
            return True
    except OSError:
        pass
    if a.stat().st_size == b.stat().st_size and digest(a) == digest(b):
        return True
    return key is not None and plain_digest(a, key) == plain_digest(b, key)


def is_archive(path):
    return path.is_file() and path.suffix.lower().startswith('.db')


def build(game, server, addon, key=None):
    game, server, addon = Path(game), Path(server), Path(addon)
    if not (game / 'resources').is_dir() or not (server / 'resources').is_dir():
        raise ValueError('Both folders need the one-folder layout (resources\\): run flatten_resources.py first')
    if addon.exists():
        raise FileExistsError(addon)
    addon.mkdir(parents=True)
    copied, shared = [], 0
    (addon / 'resources').mkdir()
    for path in sorted((server / 'resources').iterdir()):
        if not is_archive(path):
            continue
        twin = game / 'resources' / path.name
        if twin.exists() and same(path, twin, key):
            shared += 1
            continue
        if path.name.lower().startswith('99_lz_patch_') and path.stem.lower().endswith('_server'):
            name = path.name                     # a server patch: server\scripts only
        elif 'lz_scripts' in path.name.lower():
            name = '95_server_' + path.name.split('_', 1)[1] if path.name[:2].isdigit() else '95_server_' + path.name
        else:
            raise ValueError('Server archive differs from the game and is not the server scripts: ' + path.name)
        shutil.copy2(path, addon / 'resources' / name)
        copied.append(name)
    if not copied:
        raise ValueError('No server scripts archive found in ' + str(server / 'resources'))
    for folder in ('dedicated', 'hoster'):
        if (server / folder).is_dir():
            shutil.copytree(server / folder, addon / folder, ignore=HOSTER_EXTRAS)
    # notices and build stamps the game already has are not repeated
    for path in sorted((server / 'notices').glob('*')) if (server / 'notices').is_dir() else []:
        if path.is_file() and not (game / 'notices' / path.name).exists():
            (addon / 'notices').mkdir(exist_ok=True)
            shutil.copy2(path, addon / 'notices' / path.name)
    shutil.copytree(server / 'server' / 'configs', addon / 'server' / 'configs')
    (addon / 'server' / 'scripts').mkdir()
    for name in ('fsgame_server.template', 'Start Server Panel.cmd', 'Admin Rights.cmd'):
        if (server / name).exists() and not (game / name).exists():
            shutil.copy2(server / name, addon / name)
    (addon / 'README-server-addon.txt').write_text(ADDON_README, encoding='utf-8')
    # nothing of the add-on may replace a file of the game
    clash = [str(p.relative_to(addon)) for p in addon.rglob('*') if p.is_file() and (game / p.relative_to(addon)).exists()]
    if clash:
        raise ValueError('Add-on would replace game files: ' + ', '.join(clash[:5]))
    return copied, shared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='folder with "Lost Zone" and "Lost Zone Server"')
    parser.add_argument('--key', type=Path, help='owner key: compares sealed archives by content')
    args = parser.parse_args()
    key = lzpack.master(args.key) if args.key else None
    game, server = args.out / 'Lost Zone', args.out / 'Lost Zone Server'
    for folder in (game, server):
        if (folder / 'UPDATING.lock').exists():
            raise RuntimeError('Release is still being assembled: ' + str(folder))
    copied, shared = build(game, server, args.out / 'Lost Zone Server Addon', key)
    print(f'PASS server add-on: {len(copied)} server archive(s) {copied}; {shared} archives are the game\'s own')


if __name__ == '__main__':
    main()
