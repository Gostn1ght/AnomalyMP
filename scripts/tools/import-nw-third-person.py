"""Import New Way's third-person item use (owner 2026-10-24: eating, medicine,
cigarettes seen from the side; NW's developers authorized taking their work).

New Way adds to the Enhanced Animations sections (item_ea_*_hud, which GAMMA
has too: items\\anims_list.ltx names one per item) where another player
holds the item and how he moves: third_person_attach_bone / _position /
_rotation, third_person_item_visual and the actor's motion
(third_person_anm_ea_show or third_person_anm_use). Every such section that
GAMMA has, whose motion one of our actor OMFs holds and whose model exists,
goes to configs/mod_system_zzzz_lz_third_person.ltx as a DLTX override
(![section]); the engine reads it when the server says a player used an item
(netcoop_consumption).

usage: import-nw-third-person.py <NW unpacked> <GAMMA unpacked configs> <GAMMA unpacked meshes> <overlay client> <NW resources>
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("merge", HERE / "merge-player-anims.py")
merge = importlib.util.module_from_spec(spec)
sys.argv, argv = [sys.argv[0], "--import-only"], sys.argv
spec.loader.exec_module(merge)
sys.argv = argv

KEYS = ("third_person_attach_bone", "third_person_attach_position", "third_person_attach_rotation",
        "third_person_item_visual")


def sections(paths):
    out = {}
    for path in paths:
        cur = None
        for line in path.read_text(encoding="cp1251", errors="replace").splitlines():
            line = line.split(";", 1)[0].strip()
            m = re.match(r"^!*\[([^\]]+)\]", line)
            if m:
                cur = out.setdefault(m.group(1).strip(), {})
                continue
            m = re.match(r"^([A-Za-z_0-9]+)\s*=\s*(.*)$", line)
            if m and cur is not None:
                cur[m.group(1)] = m.group(2).strip()
    return out


NEEDED_TEXTURES = set()  # New Way textures the copied models use (extracted afterwards)


def take_model(nw, client, model):
    rel = model.replace("\\", "/")
    rel = rel if rel.lower().endswith(".ogf") else rel + ".ogf"
    src = nw / "meshes" / rel
    if not src.is_file():
        return False
    dst = client / "meshes" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(data)
    # texture names: zero-ended strings with a path separator, before a shader name
    for m in re.finditer(rb"([a-z0-9_]+\\[a-z0-9_\\]+)\x00(?:models|effects|def_shaders)\\", data, re.I):
        NEEDED_TEXTURES.add(m.group(1).decode("latin1").lower())
    # an animated item names its motion file: without it the model does not load
    for m in re.finditer(rb"((?:dynamics|actors|anomaly_weapons)\\[a-z0-9_\\]+)\x00", data, re.I):
        ref = m.group(1).decode("latin1").replace("\\", "/")
        omf = nw / "meshes" / (ref + ".omf")
        if omf.is_file():
            target = client / "meshes" / (ref + ".omf")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(omf.read_bytes())
    return True


def extract_textures(nw_resources, client):
    """The textures the copied models use, from New Way's archives (dds, thm, bump)."""
    sys.path.insert(0, str(Path(nw_resources).parent.parent))
    import mmap
    import zlib
    import zstandard
    from nw_unpack import entries, decrypt
    wanted = set()
    for name in NEEDED_TEXTURES:
        for suffix in (".dds", ".thm", "_bump.dds", "_bump#.dds", "_bump.thm"):
            wanted.add("textures\\" + name + suffix)
    dz, found = zstandard.ZstdDecompressor(), 0
    for archive in sorted(Path(nw_resources).glob("nw_textures.db*")):
        with open(archive, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            for name, size, packed, crc, ptr, flags in entries(str(archive)):
                if name.lower() not in wanted:
                    continue
                data = mm[ptr:ptr + packed]
                if flags & 2:
                    data = decrypt(data, ptr)
                if flags & 4:
                    data = dz.decompress(data, max_output_size=size)
                assert len(data) == size and zlib.crc32(data) == crc, name
                dst = client / name.replace("\\", "/")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                found += 1
    print("textures for the copied models:", found, "files for", len(NEEDED_TEXTURES), "names")


def main(nw, gamma_configs, gamma_meshes, client):
    nw, gamma_configs, gamma_meshes, client = map(Path, (nw, gamma_configs, gamma_meshes, client))
    theirs = sections(sorted((nw / "configs").rglob("*.ltx")))
    ours = sections(sorted(gamma_configs.rglob("items_anm_*.ltx")))
    motions = set()
    for omf in list((client / "meshes/actors").glob("*.omf")) + list((client / "meshes/actors/modded_stalker_animations").glob("*.omf")):
        motions.update(d["name"] for d in merge.parse(str(omf))["defs"])

    # A model GAMMA's own configs name ships with the game (its archives are
    # not unpacked here); others must be on disk.
    named = set()
    for keys in sections(sorted(gamma_configs.rglob("*.ltx"))).values():
        for k in ("visual", "item_visual"):
            if keys.get(k):
                named.add(keys[k].lower().replace(".ogf", ""))

    def model_exists(name):
        rel = name.replace("\\", "/")
        rel = rel if rel.endswith(".ogf") else rel + ".ogf"
        return (name.lower().replace(".ogf", "") in named or (gamma_meshes / rel).is_file()
                or (client / "meshes" / rel).is_file())

    out = ["; Third-person item use from New Way (owner 2026-10-24; NW's developers",
           "; authorized taking their work), by scripts/tools/import-nw-third-person.py.",
           "; Read by the engine when a player uses an item (netcoop_consumption).", ""]
    kept, dropped = 0, []
    for name, keys in sorted(theirs.items()):
        motion = keys.get("third_person_anm_ea_show") or keys.get("third_person_anm_use")
        if not motion or not all(keys.get(k) for k in KEYS):
            continue
        reason = None
        model = keys["third_person_item_visual"]
        if name not in ours:
            reason = "no such GAMMA section"
        elif motion not in motions:
            reason = "motion %s missing" % motion
        elif not model_exists(model):
            # New Way's own model: shipped with its textures
            if not take_model(nw, client, model):
                reason = "model %s missing in New Way too" % model
        if reason:
            dropped.append("%s: %s" % (name, reason))
            continue
        out += ["![%s]" % name, "third_person_motion = " + motion] + ["%s = %s" % (k, keys[k]) for k in KEYS] + [""]
        kept += 1
    (client / "configs/mod_system_zzzz_lz_third_person.ltx").write_text("\n".join(out), encoding="cp1251", newline="\r\n")
    print("third-person items:", kept, "| not taken:", len(dropped))
    for d in dropped:
        print("   ", d)
    if NEEDED_TEXTURES and len(sys.argv) > 5:
        extract_textures(sys.argv[5], client)


if __name__ == "__main__":
    main(*sys.argv[1:5])
