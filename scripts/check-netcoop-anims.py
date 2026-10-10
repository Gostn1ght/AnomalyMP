"""Third-person animations (owner 2026-10-10, doc 90 §4): the overlay's OMF
files (GAMMA's motions with xAGNA/xrMPE motion data merged in by
scripts/tools/merge-player-anims.py) are well-formed: every motion
definition has its motion data at its index, under its name; stalker_animation
keeps GAMMA's device, PDA, binocular and eating motions; partitions are the
stalker skeleton's. xAGNA's configs do not change NPC behaviour: no movement
speeds, no fire/shell points (NPC shots stay GAMMA's)."""
from pathlib import Path
import importlib.util
import re

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("merge", root / "tools/merge-player-anims.py")
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)

actors = root / "netcoop-overlay/client/meshes/actors"
files = sorted(actors.glob("*.omf"))
assert files and (actors / "stalker_animation.omf") in files
for f in files:
    o = merge.parse(str(f))
    assert len(o["defs"]) == o["count"] == len(o["blobs"]), f.name
    assert [p[0] for p in o["parts"]] == ["legs", "torso", "head"], f.name
    for d in o["defs"]:
        name, blob = o["blobs"][d["motion"]]
        assert name == d["name"] and blob, (f.name, d["name"])
main = {d["name"] for d in merge.parse(str(actors / "stalker_animation.omf"))["defs"]}
assert len(main) == 1652
for kept in ("norm_torso_0+detector_aim_0", "norm_torso_pda_idle_1", "binoculars_draw_0", "banka_anim_use_medkit",
             "norm_torso_0_walk_1", "norm_escape_0", "cr_torso_5+detector_aim_0"):
    assert kept in main, kept

for role in ("client", "server"):
    cfg = root / f"netcoop-overlay/{role}/configs"
    step = (cfg / "mod_system_zzzzzzzzzzzzzz_xagna_m_stalker.ltx").read_text(encoding="latin1")
    wpn = (cfg / "mod_system_zzzzzzzzzz_xagna_wpn_pos.ltx").read_text(encoding="latin1")
    assert "[stalker_step_manager]" in step and not re.search(r"^!?\[stalker_movement_speeds\]", step, re.M)
    assert not re.search(r"^\s*(fire_point|shell_point)", wpn, re.M | re.I)
    assert len(re.findall(r"^!\[wpn_", wpn, re.M)) > 100
print("netcoop anims: OK")
