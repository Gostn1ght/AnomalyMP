"""Portable fsgame templates for the J: release (owner 2026-10-09).

Every absolute path of the owner's working fsgame files becomes {ROOT}; the
launcher of the portable folder writes the real fsgame with the folder it runs
from. Lost Zone's packed GAMMA data is mounted from db\\lostzone after every
Anomaly archive (later registrations win) and before loose gamedata."""
from pathlib import Path

base = r"C:\Users\Mahito\Desktop\NetAnomaly_Engine_Console_2026-09-10\NetAnomaly_Full" + "\\"
subs = [
    (base + r"gamma-runtime\mp" + "\\", r"{ROOT}mp" + "\\"),
    (base + r"LostZone-3D-Hideout\appdata\p1" + "\\", r"{ROOT}appdata\player" + "\\"),
    (base + r"gamma-runtime\appdata\server" + "\\", r"{ROOT}appdata\server" + "\\"),
    (r"C:\Users\Mahito\Downloads\GAMMA\GAMMA\db" + "\\", r"{ROOT}db" + "\\"),
    (base + "LostZone-3D-Hideout\\", "{ROOT}"),
    (base + "gamma-runtime\\", "{ROOT}"),
]


def convert(src, dst):
    text = Path(src).read_bytes().decode("cp1251").replace("\r\n", "\n")
    for a, b in subs:
        text = text.replace(a, b)
    bad = [l for l in text.split("\n") if ":\\" in l]
    assert not bad, bad
    lines = text.split("\n")
    i = next(n for n, l in enumerate(lines) if l.startswith("$arch_dir_addons$"))
    lines[i + 1:i + 1] = [
        "; Lost Zone: GAMMA's merged data, after every Anomaly archive, before loose gamedata",
        "$arch_dir_lostzone$\t= false\t| false\t| $arch_dir$\t | lostzone\\",
    ]
    out = "\r\n".join(l.rstrip() for l in lines).rstrip() + "\r\n"
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_bytes(out.encode("cp1251"))
    print(dst, sum(1 for l in lines if "{ROOT}" in l), "rooted lines")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    convert(root / "LostZone-3D-Hideout/fsgame_p1.ltx", root / "engine-steamnet/scripts/dist/fsgame_client.template")
    convert(root / "gamma-runtime/fsgame_server.ltx", root / "engine-steamnet/scripts/dist/fsgame_server.template")
