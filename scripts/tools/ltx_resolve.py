"""Minimal X-Ray LTX + DLTX resolver (system.ltx and mod_system_*.ltx) for config analysis tools."""
import fnmatch
import os
import re
from pathlib import Path

SECTION = re.compile(r"^\s*(!!|!|@)?\[([^\]]+)\]\s*(?::\s*([^;]*))?")
INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"', re.I)


def read_lines(path):
    data = Path(path).read_bytes()
    return data.decode("cp1251", errors="replace").splitlines()


class Ltx:
    def __init__(self):
        self.raw = {}      # section -> {"parents": [...], "keys": {}}
        self.order = []

    def _parse(self, path, mods, base_dir):
        current = None
        for line in read_lines(path):
            m = INCLUDE.match(line)
            if m:
                pattern = (Path(path).parent / m.group(1).replace("\\", "/"))
                parent = pattern.parent
                if parent.exists():
                    for f in sorted(parent.iterdir(), key=lambda p: p.name.lower()):
                        if fnmatch.fnmatch(f.name.lower(), pattern.name.lower()) and f.is_file():
                            self._parse(f, mods, base_dir)
                continue
            body = line.split(";", 1)[0]
            m = SECTION.match(body)
            if m:
                mark, name, parents = m.group(1), m.group(2).strip(), m.group(3)
                plist = [p.strip() for p in parents.split(",") if p.strip()] if parents else None
                if mark == "!!":
                    self.raw.pop(name, None); current = None; continue
                if mark == "!" and name in self.raw:
                    current = self.raw[name]
                    if plist is not None:  # DLTX adds the parents an override names
                        current["parents"] += [p for p in plist if p not in current["parents"]]
                elif mark == "!" and name not in self.raw:
                    current = None  # DLTX: override of a missing section is ignored
                else:
                    if mark == "@" and name in self.raw:
                        current = self.raw[name]
                        if plist is not None: current["parents"] = plist
                    else:
                        current = self.raw[name] = {"parents": plist or [], "keys": {}}
                        self.order.append(name)
                continue
            if current is None:
                continue
            s = body.strip()
            if not s:
                continue
            if s.startswith("!") and "=" not in s:
                current["keys"].pop(s[1:].strip(), None); continue
            if "=" in s:
                k, v = s.split("=", 1)
                k = k.strip()
                if k.startswith("!"):
                    current["keys"].pop(k[1:].strip(), None); continue
                current["keys"][k] = v.strip()
            else:
                current["keys"][s] = ""

    def load_system(self, root, skip_mods=()):
        root = Path(root)
        self._parse(root / "system.ltx", None, root)
        mods = sorted((p for p in root.iterdir() if p.is_file() and p.name.lower().startswith("mod_system_") and p.suffix.lower() == ".ltx"), key=lambda p: p.name.lower())
        for p in mods:
            if p.name in skip_mods:
                continue
            self._parse(p, None, root)
        return self

    def get(self, section, key, _seen=None):
        sec = self.raw.get(section)
        if sec is None:
            return None
        if key in sec["keys"]:
            return sec["keys"][key]
        for parent in reversed(sec["parents"]):
            if _seen is None: _seen = set()
            if parent in _seen: continue
            _seen.add(parent)
            v = self.get(parent, key, _seen)
            if v is not None:
                return v
        return None

    def own(self, section, key):
        sec = self.raw.get(section)
        return sec and key in sec["keys"]


def vec(s):
    if s is None: return None
    try:
        return [float(x) for x in s.split(",")[:3]]
    except ValueError:
        return None
