"""Summarize MSVC code analysis warnings (C6xxx/C26xxx) from an MSBuild log:
counts by warning and the warnings in Lost Zone's own code first.
    python report-code-analysis.py <msbuild log> <report>"""
import collections
import re
import sys

log_path, report_path = sys.argv[1:3]
pattern = re.compile(r"^\s*(?P<file>[A-Za-z]:\\[^(]+)\((?P<line>\d+)(?:,\d+)?\): warning (?P<code>C(?:6|26)\d{3}): (?P<text>.*?)(?: \[[^\]]+\])?$")
ours = re.compile(r"\\src\\xrGame\\(netcoop|Level|xrServer|Actor|ai\\|game_sv|game_cl|ui\\UIActorMenu)", re.I)
seen = set()
items = []
for line in open(log_path, encoding="utf-8", errors="replace"):
    m = pattern.match(line)
    if not m:
        continue
    key = (m["file"].lower(), m["line"], m["code"])
    if key in seen:
        continue
    seen.add(key)
    items.append(m)
by_code = collections.Counter(m["code"] for m in items)
with open(report_path, "w", encoding="utf-8") as out:
    out.write(f"{len(items)} unique code analysis warnings\n\n")
    for code, count in by_code.most_common():
        out.write(f"{count:6d} {code}\n")
    out.write("\n== Lost Zone code (netcoop, level, server, actor, AI, game, actor menu)\n")
    for m in items:
        if ours.search(m["file"]):
            path = m["file"].split("\\src\\", 1)[-1]
            out.write(f"{path}({m['line']}): {m['code']}: {m['text']}\n")
print(f"{len(items)} warnings, report in {report_path}")
