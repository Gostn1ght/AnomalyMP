"""Portable world master for the server folder (owner 2026-10-12: the master
must be visible and start from the location panel on a PC without Python).

    python make_master_runtime.py --python <Python 3.13 install> --out <Lost Zone Server>\\hoster\\master

Writes <out>\\python (python.exe, its DLLs, the standard library zipped,
python313._pth) and <out>\\lostzone (the backend package). The private
runtime\\config.json and the world DB are created on the hoster's PC by the
panel's first start and are never part of the release.
"""
import argparse
from pathlib import Path
import shutil
import zipfile

SKIP_LIB = {"test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "site-packages", "lib2to3",
            "pydoc_data", "venv", "__pycache__", "unittest", "distutils"}
SKIP_DLLS = {"_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "_testcapi.pyd", "_testinternalcapi.pyd",
             "_testbuffer.pyd", "_testimportmultiple.pyd", "_testmultiphase.pyd", "_testsinglephase.pyd",
             "_testconsole.pyd", "_testclinic.pyd", "_testclinic_limited.pyd", "_testlimitedcapi.pyd", "_ctypes_test.pyd"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    src, out = Path(args.python), Path(args.out)
    version = next(src.glob("python3??.dll")).stem  # e.g. python313
    runtime = out / "python"
    if runtime.exists():
        shutil.rmtree(runtime)
    (runtime / "DLLs").mkdir(parents=True)
    for name in ("python.exe", "pythonw.exe", "python3.dll", f"{version}.dll", "vcruntime140.dll", "vcruntime140_1.dll",
                 "LICENSE.txt"):
        if (src / name).exists():
            shutil.copy2(src / name, runtime / name)
    for item in (src / "DLLs").iterdir():
        if item.is_file() and item.name not in SKIP_DLLS and item.suffix in (".pyd", ".dll"):
            shutil.copy2(item, runtime / "DLLs" / item.name)
    lib = src / "Lib"
    with zipfile.ZipFile(runtime / f"{version}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(lib.rglob("*.py")):
            relative = path.relative_to(lib)
            if relative.parts[0] in SKIP_LIB or "__pycache__" in relative.parts or "tests" in relative.parts:
                continue
            archive.write(path, relative.as_posix())
    # Paths relative to python.exe; ".." is the master folder with lostzone.
    (runtime / f"{version}._pth").write_text(f"{version}.zip\n.\nDLLs\n..\n", encoding="ascii")
    package = Path(__file__).resolve().parents[2] / "backend" / "lostzone"
    target = out / "lostzone"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"master runtime: {out} ({size / 1048576:.1f} MiB, {version})")


if __name__ == "__main__":
    main()
