# 77. Skip12 unused inventory bonus texture loads

2026-10-08, Codex. Scoped GAMMA client-script cleanup accepted and installed.
No new188 row: counts remain27/33/69/59,161 unclosed.

The qualified GAMMA inventory script initializes P/N bonus icon textures for
all15 stats. Six added rows (thirst, sleep, br_class, br_mitigation, strike,
explosion) have no such atlas regions. The updater hides their bonus controls
and never shows them; it still displays their actual values/progress/bonus
text. CUITextureMaster falls back from an absent region to a literal DDS
lookup, producing12 misleading missing-texture warnings at GUI construction.
These names do not justify inventing or substituting unrelated DDS icons.

Owned `netcoop_inventory_compat.script` skips ONLY those12 texture loads.
Two call-site changes in the existing ui_inventory script delegate to it.
All15 rows, controls, text, bars, original update code and Show(false) calls
remain;18 existing P/N textures for nine original stats are retained.
No changes to NPCs, AI cadence, physics, inventory contents, stat calculation
or layout. This is not an inventory/trade redesign.

Installer `install-netcoop-inventory-compat.py` accepts only the qualified
whole-script version (original SHA16CCF35A...) or its exact patched SHA.
It preserves custom/new versions, preflights helper conflicts, backs up
original bytes and atomically replaces the caller after supplying its helper.
Helper hashes use canonical LF for consistent Git checkouts. Repeat preview
reports no change. Server scripts have a different version and are not patched.

The Lua5.1 differential test imports the actual stats constructor block from
this known source. All widget creation/parents/visibility traces remain
identical except12 nonexistent texture initializations. All18 existing names
match. Local PASS and GitHub Actions `checks` PASS in run37785253553/source64e7.
The full C++ engine build also succeeds; the native test uses the already qualified GHAbe30 engine.

Private native acceptance, retained correlated world and ordinary synthetic
account961: Actor20020, native first-window-frame-presented, actual inventory
constructor and ui_inventory.start('inventory'). All15 native stat-control
groups exist, the six unused bonus pairs remain hidden, inventory IsShown=true,
another20s admitted. No fatal/exception, SCRIPT ERROR, failed handler,
caught probe or loadout error. All12 target texture warnings are absent.
Other warnings remain:27 texture and10 sound records in this open-inventory
session; resource loading also depends on weather/scene, so total warning
counts alone are not an exact paired A/B metric.

Proof `_build/live/inventory-compat-be30/qualified-acceptance.json`, two
sealed pre-stop logs, original script backup/manifest and Lua trace test.
Nonce `INVICONS_2af29cad87554f46837dc886b6e32147`.
First controller failed before client launch because it retained an irrelevant
server INI query from a prior probe; its log/qualification are preserved.
Corrected driver verifies the actual client GUI and actual server admission.

Screenshot is NOT accepted: the probe requested the native renderer command,
but the existing console policy rejected player `screenshot` and
`r_screenshot_mode`. Its printed marker means request only; no image was saved.
Pixel layout/human input/trade interaction remain unproved. Fixing that
separate local-capture policy issue is a possible next small change.

After native acceptance, install only the two call-site changes plus owned
helper into gamma-runtime/client/scripts and LostZone-3D-Hideout/client/scripts.
Exact original backups under inventory-compat-be30/primary-backups;
installed bytes match the tested private scripts, repeat previews0.
Server scripts, primary EXEs and world/account/character files unchanged.
All88 protected fingerprints still match; changed client scripts are outside
that baseline. All native test processes stopped and shared debug empty.

Separate read-only scan of101 local archive indices found no candidates for
the48 prior warning names under directly normalized entry paths; no payload
extraction/profile activation/runtime replacement. Header alias mappings and
loose files need their own analysis before concluding an asset is unavailable.
The initial apostrophe-parser error is retained separately as unqualified.
Atlas XML/script evidence above, not that scan alone, supports the12-load fix.

Subsequent capture-permission repair passes doc78, but its PNG shows the
loading backbuffer, not this inventory. Constructor/open-state acceptance
above remains scoped; no inventory pixel-layout acceptance is inferred.
