"""One self-contained server folder (owner 2026-10-12: "one folder with the
dedicated and everything; I send it as an archive to the hoster").

    python make_standalone_server.py --game "J:\\LostZone\\Lost Zone" --previous "J:\\LostZone_Work\\Lost Zone Server"
        --dedicated <CI artifact>\\dedicated --python <Python 3.13 install> --version "..." --out <folder>

* resources: every game archive except textures (the UI ones stay: fonts) and
  music, plus the server archives (95_server_*, 99_*_server) of --previous;
  hard links on the same drive, copies otherwise;
* dedicated: the CI build (no .pdb);
* server: the loose server configs/scripts of --previous;
* hoster: the panel, watchdog, master control, plans and the portable master;
* top level: the start scripts, fsgame_server.template and README.txt.
No appdata and no master runtime: worlds, accounts and keys stay on the
hoster's PC.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SKIP = ("90_lostzone_lz_textures", "50_textures_", "40_sounds_sounds_music")
KEEP = ("50_textures_textures_ui",)


def link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--game", required=True)
    p.add_argument("--previous", required=True)
    p.add_argument("--dedicated", required=True)
    p.add_argument("--python", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    game, prev, out = Path(a.game), Path(a.previous), Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists; remove it first")
    (out / "resources").mkdir(parents=True)
    size = 0
    for f in sorted((game / "resources").iterdir()):
        if f.name.startswith(SKIP) and not f.name.startswith(KEEP):
            continue
        link_or_copy(f, out / "resources" / f.name)
        size += f.stat().st_size
    for f in sorted((prev / "resources").iterdir()):
        if (f.name.startswith("95_server_") or f.name.endswith("_server.db0")) and not (out / "resources" / f.name).exists():
            link_or_copy(f, out / "resources" / f.name)
            size += f.stat().st_size
    shutil.copytree(a.dedicated, out / "dedicated", ignore=shutil.ignore_patterns("*.pdb"))
    shutil.copytree(prev / "server", out / "server")
    hoster = out / "hoster"
    hoster.mkdir()
    for f in (REPO / "scripts" / "netcoop-cluster").iterdir():
        if f.suffix == ".ps1" or f.name in ("netcoop_cluster.ltx.six", "netcoop_cluster.ltx.full"):
            shutil.copy2(f, hoster / f.name)
    subprocess.run([sys.executable, str(HERE / "make_master_runtime.py"), "--python", a.python,
                    "--out", str(hoster / "master")], check=True)
    for name in ("Start Server Panel.cmd", "Start Locations.cmd", "Admin Rights.cmd", "fsgame_server.template"):
        shutil.copy2(HERE / name, out / name)
    readme = (HERE / "README-server.txt").read_text(encoding="utf-8").replace("{VERSION}", a.version)
    (out / "README.txt").write_bytes(b"\xef\xbb\xbf" + readme.replace("\n", "\r\n").encode("utf-8"))
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"standalone server: {out} ({total / 2**30:.1f} GiB, resources {size / 2**30:.1f} GiB)")


if __name__ == "__main__":
    main()
