# 75. Native HUD inactive-state diagnostic acceptance

2026-10-08, Codex. Scoped diagnostic repair accepted. This is not a new188
row and does not fix visible character blinking or animation movement.

`script_anim_part` uses `u8(-1)=255` as the normal inactive state in both
the constructor and StopScriptAnim. GAMMA startup unconditionally calls
stop_hud_motion; the old method incorrectly reports255 as an invalid part.
The new warning condition excludes only this sentinel. All reset fields,
movement/resynchronization callbacks and genuine3..254 warnings remain.

The fixture imports the actual engine method and compares2048 combinations
of all256 part values, four attachment masks and both warning flags against
the previous method. Only the expected old255 warning/stack is removed
from the reference trace; every cleanup callback and field remains checked.
GCC with ASan/UBSan and MSVC pass in Foundation37773463706. Initial b182
CI failed in the fixture itself: control rename also changed its diagnostic
literal, and Windows used an incompatible default source decoder. The
declaration-only rename/latin1 byte-preserving read repairs the fixture
without weakening assertions. Both earlier failures remain recorded.

Qualified source `be30a8bb2bef31452eed26d2e945b6fad2f41778`:

- DX11 run37773463776 SUCCESS including full engine/package/upload.
- Artifact11549278414; ZIP SHA256
  `6f02b5cd8bd3a0f798f4d1d6195b4e161655d167d742b4524e1886b14677605b`.
- Client/server EXE SHA256
  `4BA7566067A0B457AA5C40AAC3C0EDDEDE08DDEE8D37597A7FCB780C51968711`.

Private native acceptance restores the SAME correlated world, admits
ordinary synthetic account961 as Actor20608/PID13152, records the native
first-window-frame-presented marker, and retains original actor updates.
After normal GAMMA startup it calls native game.stop_hud_motion three times.
No invalid-part255 warning or genuine invalid-part warning appears. The
client remains admitted another20s, with no fatal/exception, SCRIPT ERROR,
failed handler, caught probe error or NPC-loadout error in either sealed log.

The private FS aliases mount NO extra rain archive. Actual sound constructors
load all14 PRIMARY-installed rain assets with their original nonzero512–838ms
durations. Both native INI readers also verify the nine corrected loadout
section/key pairs and calibers from doc74. Proof:
`_build/live/hud-be30a8bb2/qualified-acceptance.json`, sealed pre-stop logs,
native fixture logs, source/package/ZIP/EXE provenance.

This remains a scoped acceptance, not a completely clean GAMMA startup:
the client reports38 other missing-texture and10 other missing-sound
warnings, plus separate MCM diagnostics. The previous rain and loadout
probes also had these native asset warnings. Earlier shorthand
"zero missing-sound errors" meant the14 target Lua rain exceptions,
not every native missing-bank warning; docs73/74 now make this explicit.

All test processes stopped and shared debug empty. All88 protected primary
EXE/FS-alias/account/character/world fingerprints remain unchanged. No
primary engine promotion;14 sound files and20 targeted loadout LTX changes
are the accepted primary delta from docs73/74. Native main-window presentation
does not prove human Firebase entry, 3D menu design or visible NPC smoothness.
Counters remain26/34/69/59,162 unclosed. Source44730 adds only the config
installer/manifest/docs; it does not alter the validated native HUD code.
