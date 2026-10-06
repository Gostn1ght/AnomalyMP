"""Overlay Lua: a top-level local used above its declaration is a nil global.

    local function later() end      -- line 50
    function early() later() end    -- line 10: calls the GLOBAL 'later' (nil)

Lua resolves the name when the using function is compiled, so the call fails
at run time ("attempt to call global"). That broke the server's per-frame
loop (owned_objects_update, 2026-10-06). A forward declaration
(`local later` above the use) is the fix this check accepts.
"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "scripts/netcoop-overlay"
decl = re.compile(r"^local\s+function\s+([A-Za-z_]\w*)|^local\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?:=|$)")
problems = []
for path in sorted(root.rglob("*.script")):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Strip string literals, then comments: a name inside quotes is not a use.
    strings = re.compile(r'"(?:[^"\\]|\\.)*"|' + r"'(?:[^'\\]|\\.)*'")
    code = [re.sub(r"--.*$", "", strings.sub('""', l)) for l in lines]
    declared = {}  # name -> first top-level declaration line
    for n, line in enumerate(code):
        m = decl.match(line)
        if not m:
            continue
        names = [m.group(1)] if m.group(1) else [x.strip() for x in m.group(2).split(",")]
        for name in names:
            declared.setdefault(name, n)
    for name, at in declared.items():
        use = re.compile(r"(?<![\w.:])" + re.escape(name) + r"\b")
        for n in range(at):
            if use.search(code[n]):
                problems.append(f"{path.relative_to(root)}:{n + 1}: '{name}' used before its local declaration on line {at + 1}")
                break

# GAMMA's printf substitutes only %s; %d/%u/%.2f were logged literally.
printf_call = re.compile(r'\bprintf\s*\(\s*"((?:[^"\\]|\\.)*)"')
bad_spec = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[dfiuxXgGe]")
for path in sorted(root.rglob("*.script")):
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        for m in printf_call.finditer(line):
            if bad_spec.search(m.group(1)):
                problems.append(f"{path.relative_to(root)}:{n + 1}: printf format other than %s (GAMMA prints it literally)")

# Every overlay script must at least compile (a broken string or a stray
# `end` disables the whole module in the game without a test noticing).
try:
    from lupa.lua51 import LuaRuntime
    lua = LuaRuntime()
    compile_chunk = lua.eval("function(code, name) local f, err = loadstring(code, name); return err end")
    for path in sorted(root.rglob("*.script")):
        err = compile_chunk(path.read_text(encoding="utf-8", errors="replace"), str(path.name))
        if err:
            problems.append(f"{path.relative_to(root)}: does not compile: {err}")
except ImportError:
    print("lupa missing: syntax check skipped")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print("Overlay Lua scope: no top-level local is used above its declaration; printf formats only %s PASS")
