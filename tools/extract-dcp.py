"""Extract the Definitive Car Pack's vehicles (owner 2026-10-24: "the
Definitive pack, cut all the old cars") from the owner's Lost Alpha DCP
download into a plain folder: the vehicle models (meshes\\physics\\vehicles),
their physics/handling profiles (config\\models\\vehicles -> configs\\...),
the patch's vehicle sections (config\\items\\vehicles.ltx) and exactly the
textures the models name (with .thm and bump maps). Nothing is installed and
no foreign binary is touched (see docs/audit/121).

The DCP volumes mod_zzz_dcp.xdb0..4 and mod_zzz_dcp_patch.xdb0 are first
copied out of the ZIPs (they are deflated); a later volume overrides an
earlier one, the patch overrides all. Entries are LZO-compressed with a CRC.

usage: extract-dcp.py --out <folder> <zip> [<zip> ...]
"""
import argparse
import importlib.util
import json
import mmap
import re
import shutil
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audit", HERE / "audit-vehicle-sources.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

VOLUMES = ["mod_zzz_dcp.xdb0", "mod_zzz_dcp.xdb1", "mod_zzz_dcp.xdb2", "mod_zzz_dcp.xdb3", "mod_zzz_dcp.xdb4",
           "mod_zzz_dcp_patch.xdb0"]
MODEL_PREFIXES = ("meshes\\physics\\vehicles\\", "meshes\\dynamics\\vehicles\\")
CONFIG_PREFIXES = ("config\\models\\vehicles\\",)
CONFIG_FILES = ("config\\items\\vehicles.ltx", "config\\text\\rus\\string_table_enc_vehicles.xml",
                "config\\text\\eng\\string_table_enc_vehicles.xml")
SOUND_PREFIXES = ("sounds\\car\\",)  # engines, doors, horns of the cars


def copy_volumes(zips, archives):
    archives.mkdir(parents=True, exist_ok=True)
    for path in zips:
        with zipfile.ZipFile(path) as package:
            for member in package.infolist():
                name = member.filename.split("/")[-1]
                if name not in VOLUMES:
                    continue
                target = archives / name
                if target.is_file() and target.stat().st_size == member.file_size:
                    continue
                with package.open(member) as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out, 16 * 1024 * 1024)
                print("copied", name, member.file_size // 1048576, "MB", flush=True)


def index(archives):
    entries = {}  # lower name -> (volume, entry); later volumes override
    for volume in VOLUMES:
        path = archives / volume
        if not path.is_file():
            raise SystemExit("missing DCP volume " + volume)
        with open(path, "rb") as stream:
            for entry in audit.xdb_entries(stream, path.stat().st_size):
                entries[entry["name"].lower()] = (volume, entry)
    return entries


def read(archives, maps, volume, entry):
    mm = maps.setdefault(volume, None)
    if mm is None:
        handle = open(archives / volume, "rb")
        mm = maps[volume] = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    raw = mm[entry["offset"]:entry["offset"] + entry["packed"]]
    if entry["packed"] != entry["size"]:
        import lzokay
        raw = lzokay.decompress(raw, entry["size"])
    if len(raw) != entry["size"] or zlib.crc32(raw) != entry["crc"]:
        raise ValueError("DCP entry length/CRC mismatch: " + entry["name"])
    return raw


def target_name(name):
    # Lost Alpha keeps configs in "config"; this game in "configs".
    return ("configs" + name[6:]) if name.startswith("config\\") else name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("zips", nargs="+", type=Path)
    args = parser.parse_args()
    archives, tree = args.out / "archives", args.out / "gamedata"
    copy_volumes(args.zips, archives)
    entries = index(archives)
    print("DCP entries:", len(entries))
    maps, written = {}, []

    def put(name):
        volume, entry = entries[name]
        if name.endswith("\\") or not entry["size"] and "." not in name.rsplit("\\", 1)[-1]:
            return b""  # a folder record
        data = read(archives, maps, volume, entry)
        out = tree / target_name(name).replace("\\", "/")
        if out.is_dir():
            return data
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        written.append(target_name(name))
        return data

    textures = set()
    for name in sorted(entries):
        if name.startswith(MODEL_PREFIXES) and name.endswith((".ogf", ".omf")):
            data = put(name)
            for m in re.finditer(rb"([a-z0-9_\-]+\\[a-z0-9_\-\\]+)\x00(?:models|effects|def_shaders|vehicles|default)\\", data, re.I):
                textures.add(m.group(1).decode("latin1").lower())
        elif name.startswith(CONFIG_PREFIXES) or name in CONFIG_FILES or name.startswith(SOUND_PREFIXES):
            put(name)
    missing = []
    for texture in sorted(textures):
        found = False
        for suffix in (".dds", ".thm", "_bump.dds", "_bump#.dds", ".ltx"):
            name = "textures\\" + texture + suffix
            if name in entries:
                put(name)
                found = found or suffix == ".dds"
        if not found:
            missing.append(texture)
    (args.out / "extracted.json").write_text(json.dumps({"files": written, "textures_not_in_dcp": missing},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    print("extracted", len(written), "files;", len(textures), "textures named,", len(missing), "not in DCP (the game's own)")


if __name__ == "__main__":
    main()
