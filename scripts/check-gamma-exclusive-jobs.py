"""Check MLR exclusive jobs against real logic sections after the DLTX fixes.

Default uses pinned GAMMA inputs in CI. --configs <gamedata/configs> also
checks their installed source without modifying any files.
"""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SMARTS = ("military/smart/mil_smart_terrain_7_7", "military/smart/mil_smart_terrain_7_4",
          "dead_city/smart/cit_killers_vs_bandits")


def sections(path):
    result = {}
    section = None
    for raw in path.read_bytes().decode("latin-1").splitlines():
        line = raw.split(";", 1)[0].strip()
        match = re.match(r"[!@]?\[([^]]+)\]", line)
        if match:
            section = match[1]
            result.setdefault(section, {})
        elif line and section and not line.startswith("#"):
            key, _, value = line.partition("=")
            result[section][key.strip()] = value.strip()
    return result


def jobs(configs, smart, overlay=None):
    base = configs / "scripts" / (smart + ".ltx")
    paths = sorted(base.parent.glob("mod_" + base.stem + "_*.ltx"))
    if overlay:
        paths += sorted((overlay / "scripts" / Path(smart).parent).glob("mod_" + base.stem + "_*.ltx"))
    result = {}
    # These pinned inputs focus on MLR's added jobs; existing game jobs do not
    # belong to this patch. A complete GAMMA tree may include the base too.
    if base.exists():
        result.update(sections(base).get("exclusive", {}))
    for path in paths:
        for key, value in sections(path).get("exclusive", {}).items():
            if key.startswith("!"):
                result.pop(key[1:], None)
            else:
                result[key] = value
    return result


def missing(configs, overlay=None):
    errors = []
    checked = 0
    for smart in SMARTS:
        for name, relative in jobs(configs, smart, overlay).items():
            if "xcvb" not in name:
                continue
            logic = configs / "scripts" / relative.replace("\\", "/")
            checked += 1
            if not logic.is_file() or "logic@" + name not in sections(logic):
                errors.append((smart, name, relative))
    return checked, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", type=Path, default=ROOT / "scripts/fixtures/gamma-exclusive/configs")
    args = parser.parse_args()
    _, before = missing(args.configs)
    expected = {"mil_7_7_xcvb_day_9"}
    expected.update(f"mil_2_2_xcvb_{period}_{i}" for period in ("day", "night") for i in range(1, 7))
    expected.update(f"cit_killers_vs_bandits_xcvb_night_{i}" for i in range(1, 8))
    assert {e[1] for e in before} == expected, before
    for side in ("client", "server"):
        count, errors = missing(args.configs, ROOT / "scripts/netcoop-overlay" / side / "configs")
        assert not errors, errors
        # 7_4's twelve valid jobs replace the twelve mistyped names, rather
        # than dropping working NPC schedules to quiet a warning.
        repaired = jobs(args.configs, SMARTS[1], ROOT / "scripts/netcoop-overlay" / side / "configs")
        assert all(f"mil_7_4_xcvb_{p}_{i}" in repaired for p in ("day", "night") for i in range(1, 7))
        print(f"PASS {side}: {len(before)} missing MLR jobs reproduced; {count} remaining jobs resolve to real logic sections")


if __name__ == "__main__":
    main()
