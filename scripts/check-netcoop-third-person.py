"""New Way's third-person item use (owner 2026-10-24): every section of
configs/mod_system_zzzz_lz_third_person.ltx has all the keys the engine reads
(ActorAnimation.cpp netcoop_tp_*), its motion is in one of the client's actor
OMFs and its bone is a stalker bone; the models New Way supplied are in
the overlay."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "scripts/netcoop-overlay/client"
spec = importlib.util.spec_from_file_location("merge", ROOT / "scripts/tools/merge-player-anims.py")
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)

motions = set()
for omf in list((CLIENT / "meshes/actors").glob("*.omf")) + list((CLIENT / "meshes/actors/modded_stalker_animations").glob("*.omf")):
    motions.update(d["name"] for d in merge.parse(str(omf))["defs"])

text = (CLIENT / "configs/mod_system_zzzz_lz_third_person.ltx").read_text(encoding="cp1251")
sections, cur = {}, None
for line in text.splitlines():
    line = line.split(";", 1)[0].strip()
    m = re.match(r"^!\[([a-z0-9_]+)\]$", line)
    if m:
        cur = sections.setdefault(m.group(1), {})
        continue
    m = re.match(r"^([a-z_]+)\s*=\s*(.+)$", line)
    if m and cur is not None:
        cur[m.group(1)] = m.group(2)
keys = ("third_person_motion", "third_person_item_visual", "third_person_attach_bone",
        "third_person_attach_position", "third_person_attach_rotation")
assert len(sections) >= 10, len(sections)
for name, values in sections.items():
    assert name.endswith("_hud"), name
    assert all(k in values for k in keys), (name, values)
    assert values["third_person_motion"] in motions, (name, values["third_person_motion"])
    assert values["third_person_attach_bone"].startswith("bip01_"), name
    for k in ("third_person_attach_position", "third_person_attach_rotation"):
        assert len([float(x) for x in values[k].split(",")]) == 3, (name, k)
# New Way's tracks (the cigarettes): the file is there, reads as the engine
# reads it (netcoop_tp_track_load) and names bones the item model has.
import struct
tracks = 0
for name, values in sections.items():
    if "third_person_track" not in values:
        continue
    data = (CLIENT / "anims" / values["third_person_track"].replace("\\", "/")).read_bytes()
    assert data[:4] == b"NWT3", name
    bones, frames, again = struct.unpack_from("<3I", data, 4)
    assert 0 < bones <= 64 and 0 < frames <= 20000 and again == frames, name
    at, names = 16, []
    for _ in range(bones):
        end = data.index(b"\0", at)
        names.append(data[at:end])
        at = end + 1 + frames * 49
    assert at == len(data), name
    model = (CLIENT / "meshes" / (values["third_person_item_visual"].replace("\\", "/"))).read_bytes()
    assert all(n + b"\0" in model for n in names), (name, names)
    tracks += 1
assert tracks >= 6, tracks
engine = (ROOT / "src/xrGame/ActorAnimation.cpp").read_text(encoding="utf-8", errors="replace")
for k in keys + ("third_person_track",):
    assert '"%s"' % k in engine, k
print("PASS third-person items: %d sections (%d with New Way's track), every motion in the actor OMFs, all keys the engine reads" % (len(sections), tracks))
