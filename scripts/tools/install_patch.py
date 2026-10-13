"""Install CI build + patch 000009 into the client master copy, the friend's server
folder and the local srvtest runtime. Every replaced file is backed up first;
targets are removed before copying so hardlinked copies are never edited in place."""
import os
import shutil
import sys
import time
from pathlib import Path

ART = Path(sys.argv[1])          # unpacked CI artifact
VERSION = sys.argv[2]
PATCH = Path(r"J:\LostZone_Work\_work") / f"patch_{VERSION}"
REPO = Path(r"C:\Users\Mahito\Desktop\NetAnomaly_Engine_Console_2026-09-10\NetAnomaly_Full\engine-steamnet")
CLIENT = Path(r"J:\LostZone\Lost Zone")
SERVER = Path(r"J:\LostZone_Work\Lost Zone Server")
SRVTEST = Path(r"J:\LostZone_Work\_work\srvtest")
STAMP = time.strftime("%Y%m%d_%H%M")
BACKUP = Path(r"J:\LostZone_Work\_work") / f"before_{VERSION}_{STAMP}"
count = {"files": 0}


def put(src, dst, backup_root, target_root):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        keep = backup_root / dst.relative_to(target_root)
        if not keep.exists():
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, keep)
        os.remove(dst)  # break a hardlink instead of writing through it
    shutil.copy2(src, dst)
    count["files"] += 1


def tree(src_dir, dst_dir, backup_root, target_root, skip=()):
    for src in Path(src_dir).rglob("*"):
        if src.is_file():
            rel = src.relative_to(src_dir)
            if any(str(rel).lower().startswith(s) for s in skip):
                continue
            put(src, Path(dst_dir) / rel, backup_root, target_root)


# Client master copy (published by the launcher).
b = BACKUP / "client"
tree(ART / "bin", CLIENT / "bin", b, CLIENT)
put(PATCH / f"archives/client/99_lz_patch_{VERSION}.db0", CLIENT / f"resources/99_lz_patch_{VERSION}.db0", b, CLIENT)
tree(PATCH / "loose/client/configs", CLIENT / "client/configs", b, CLIENT)

# Server addon folder (the friend copies it over the game) and srvtest.
for name, root in (("server", SERVER), ("srvtest", SRVTEST)):
    b = BACKUP / name
    tree(ART / "dedicated", root / "dedicated", b, root)
    tree(ART / "hoster", root / "hoster", b, root, skip=("master",))
    put(REPO / "scripts/dist/Start Locations.cmd", root / "Start Locations.cmd", b, root)
    put(PATCH / f"archives/server/99_lz_patch_{VERSION}_server.db0", root / f"resources/99_lz_patch_{VERSION}_server.db0", b, root)
    tree(PATCH / "loose/server/configs", root / "server/configs", b, root)

print(f"installed {count['files']} files; old files in {BACKUP}")
