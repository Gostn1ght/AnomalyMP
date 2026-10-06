"""Main-thread time by function from a server log with -netcoop_sample_profile.

    python tools/profile-report.py <exe with its .pdb> <log>

Takes the last [sample-profile] block, names the addresses with the PDB
(tools/symaddr.py) and sums the percentages per function (several return
addresses of one function become one line)."""
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def main():
    exe, log = sys.argv[1], sys.argv[2]
    lines = Path(log).read_text(encoding="cp1251", errors="replace").splitlines()
    starts = [i for i, l in enumerate(lines) if "[sample-profile]" in l and "samples of the main thread" in l]
    if not starts:
        raise SystemExit("no [sample-profile] block in " + log)
    block = [lines[starts[-1]]]
    for l in lines[starts[-1] + 1:]:
        if "[sample-profile]" not in l:
            break
        block.append(l)
    tmp = Path(log).with_suffix(".profile.tmp")
    tmp.write_text("\n".join(block), encoding="cp1251")
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("symaddr.py")), exe, str(tmp), "[sample-profile]"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    tmp.unlink()
    totals = {"self": defaultdict(float), "incl": defaultdict(float)}
    current = None
    for l in out:
        m = re.search(r"\[sample-profile\] (self|incl)\s+([\d.]+)% (\S+)", l)
        if m:
            current = (m.group(1), float(m.group(2)), m.group(3))
            if not re.fullmatch(r"14[0-9a-fA-F]{7}", m.group(3)):
                totals[current[0]][m.group(3)] += current[1]
                current = None
            continue
        n = re.match(r"\s+\S+ = (.+)$", l)
        if n and current:
            name = re.sub(r" \(.*\)$", "", n.group(1))
            totals[current[0]][name] += current[1]
            current = None
    print(block[0])
    for kind, title in (("self", "SELF (on top of the stack)"), ("incl", "INCLUSIVE (anywhere in the stack)")):
        print("\n" + title)
        for name, pct in sorted(totals[kind].items(), key=lambda x: -x[1])[:40]:
            print("%6.1f%%  %s" % (pct, name[:150]))


if __name__ == "__main__":
    main()
