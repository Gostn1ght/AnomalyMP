"""Import New Way's door and campfire gestures (owner 2026-10-24: "opening a
door and lighting a campfire, in first and third person"; NW's developers
authorized taking their work).

First person New Way plays a hands motion: nw_door_reach_return (the left
hand reaches for the door) and hand_ignit with the matches model (lighting a
fire). Their sections (mod_system_door_open.ltx, mod_system_campfire_ignition.ltx)
go to configs/mod_system_lz_nw_gestures.ltx with their motion files in the
hands' folder (anomaly_weapons\\hud_hands_animation\\*.omf, which every hands
model loads), the matches model with its textures and the camera shake.

New Way has no third-person motion for them; the other players see the
stalker's own gestures (GESTURES below), played like an item's use when
the server says a player did it (netcoop_consumption, section anim_door_open
or anim_campfire_ignition).

usage: import-nw-gestures.py <NW unpacked> <overlay client> <NW resources>
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tp", HERE / "import-nw-third-person.py")
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

GESTURES = {
    # section: (New Way's config, hands motion files, third-person motion)
    "anim_door_open_hud": ("mod_system_door_open.ltx", ["nw_door_reach_return.omf"], "norm_torso_0_gest_pointing_0"),
    "anim_campfire_ignition_hud": ("mod_system_campfire_ignition.ltx", ["matches_hud_hands_animation.omf"],
                                   "norm_torso_0_gest_pickup_0"),
}
# New Way's own keys our engine does not read, and the sound GAMMA already plays
SKIP = ("snd_using", "snd_using_volume", "preserve_weapon_hud", "keep_weapon", "hands_offset_snap",
        "single_handed_anim", "cam_sync_to_animation")


def main(nw, client, resources):
    nw, client = Path(nw), Path(client)
    hands = client / "meshes/anomaly_weapons/hud_hands_animation"
    hands.mkdir(parents=True, exist_ok=True)
    out = ["; New Way's door and campfire gestures (owner 2026-10-24; NW's developers",
           "; authorized taking their work), by scripts/tools/import-nw-gestures.py.",
           "; First person: game.play_hud_motion (netcoop_client_compat); third person:",
           "; third_person_motion when the server says a player did it (netcoop_consumption).", ""]
    for section, (config, omfs, motion) in GESTURES.items():
        keys = tp.sections([nw / "configs" / config])[section]
        for omf in omfs:
            (hands / omf).write_bytes((nw / "meshes/anomaly_weapons/hud_hands_animation" / omf).read_bytes())
        if keys.get("item_visual"):
            assert tp.take_model(nw, client, keys["item_visual"]), keys["item_visual"]
        for key, value in keys.items():
            if key.startswith("cam_anm"):
                anm = value.replace("\\", "/")
                target = client / "anims" / anm
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((nw / "anims" / anm).read_bytes())
        out.append("[%s]" % section)
        out += ["%s = %s" % (k, v) for k, v in keys.items() if k not in SKIP]
        out += ["third_person_motion = " + motion, ""]
    (client / "configs/mod_system_lz_nw_gestures.ltx").write_text("\n".join(out), encoding="cp1251", newline="\r\n")
    print("gestures:", ", ".join(GESTURES))
    if tp.NEEDED_TEXTURES:
        tp.extract_textures(resources, client)


if __name__ == "__main__":
    main(*sys.argv[1:4])
