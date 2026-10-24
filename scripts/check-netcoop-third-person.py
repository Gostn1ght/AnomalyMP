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
engine = (ROOT / "src/xrGame/ActorAnimation.cpp").read_text(encoding="utf-8", errors="replace")
for k in keys:
    assert '"%s"' % k in engine, k
print("PASS third-person items: %d sections, every motion in the actor OMFs, all keys the engine reads" % len(sections))
