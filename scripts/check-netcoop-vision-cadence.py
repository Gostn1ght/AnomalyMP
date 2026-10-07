"""Verify restoration of the actual pre-budget freeplay vision function.

Source equivalence, not a geometric ray-query simulation or visual acceptance.
"""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
reference = root / "scripts/fixtures/freeplay-vision/o_trace.cpp"
reference_text = reference.read_text(encoding="utf-8") # normalize checkout CRLF
assert hashlib.sha256(reference_text.encode("utf-8")).hexdigest() == (
    "bf4bdfa2ff83bba7ee52ee07928f2bd434fd08aafa18b55b6cf7ed9a50118017"
), "Historical reference changed"
expected = reference_text.rstrip("\n")
source = (root / "src/xrEngine/Feel_Vision.cpp").read_text(encoding="utf-8")
start = source.index("\tvoid Vision::o_trace(")
opening = source.index("{", start)
depth = 1
end = opening + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
assert source[start:end] == expected, "Vision differs from pre-budget freeplay"
assert "m_trace_cursor" not in (root / "src/xrEngine/Feel_Vision.h").read_text(encoding="utf-8")
print("PASS source equivalence: actual pre-budget freeplay vision; all target classes/distances retain original trace order, caches and fuzzy updates")
