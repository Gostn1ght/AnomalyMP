# 67. Destructible state across two actual world restarts

2026-10-08, Codex. Closes the original L30 requirement: important destructibles
retain INTACT / DAMAGED / DESTROYED. It does not close chunk hydration, moving
body velocities, client hit authority, graphical startup, or 64/512 capacity.

## Runtime and qualified oracle

Native source `4b74ba7f2b958ec1d4fad26ec68140bc97154816`, GitHub Actions only:
Foundation **37732900872** PASS GCC/ASan/UBSan and MSVC;
DX11 **37732900805** SUCCESS including full engine/package/upload.
Artifact **11531705521**, ZIP SHA256
`9db5c78b51039219da3522a521344e6c0fd06d4ffe23c40113d6607c99c3251f`;
both exes SHA256
`E4EDE44A70CAEEB43DC9CA00968ECDAE0CF838BDF7D44F4E35341E2EC15FE7A0`.
Source/package/manifest validation and the calibrated pre-fix failures are in
doc66. This continuation changes no engine source or package.

Private retained root `_build/live/destructibles-correlated-4b74ba7f2`;
world `selftest_destructibles_correlated`, full GAMMA Cordon population,
one synthetic native bot. Fresh private appdata initially contains user
settings only. The SAME world, accounts and characters survive all three
phases without deletion or reseeding. Save period30s is test-only; normal300s
unchanged. Each damage/destruction phase also has an explicit successful
checkpoint, so later deleted objects are not an uncommitted rollback oracle.

The initial catalogue finds154 physical/destructible objects. All three
observed eligible damageable model types are tested using their actual model
INI fire immunity/root scale and zero impulse; no model/section is fabricated:

- Glass15504, `dynamics\kitchen_room\bottle_3l`.
- Wood15778, `dynamics\box\box_wood_01`.
- Metal15791, `dynamics\box\box_metall_01`.

Actual native hits of0.4 damage each to binary32 `3f19999a`
(0.6000000238418579). After checkpoint and restart, all three retain this exact
health plus original INI prefix/name/class/visual/body count. The same0.7
follow-up hits destroy all three. After settling, another explicit checkpoint
and another restart, all three roots remain absent. The151 untargeted physical
objects retain their identities, stock types/visuals/body counts, original INI
and intact health across both restarts.

The broken bottle naturally produces eight persistent, one-body classD parts:
18980,19002,19003,19004,19037,19038,19039,19088, with the stock
`bottle_3l_part_0` through `_7` visuals. All eight preserve ID/name/visual/class,
body count, source15504, original INI and health after restart. Maximum saved
pose difference is **0.0023028732m** and **0.008642107** rotation coefficient,
within the original0.05m/0.04 bounds. These are real naturally separated parts,
unlike doc65's synthetic two-body fixture. No wood/metal fragment-persistence
claim: only the glass parts remain at the settled checkpoint.

This supplements doc64's actual CBreakable damaged/broken/deleted restart
cases and doc65's actual CPhysicsSkeletonObject pose case. L30 is accepted for
the persisted states and representative native classes/models above; it is
not a claim that every model on every map has been exercised.

## Error gates and retained failures

All three phases finish1/1 playing, zero terminal/fatal/Lua/shader/save/capture
errors. One admission timeout recovers in phase1; phases2/3 have none.
Seven existing GAMMA loadout diagnostic records remain: three missing
`blackops_secondary / wpn_usp_match` records, and four ammo-type fallback
records (dvl10_m1 once, ithacam37_stakeout_20x70 twice, ak74u_m1_isg once).
These are not suppressed or treated as a clean GAMMA configuration acceptance.

The preceding private root `_build/live/destructibles-full-4b74ba7f2` is
UNQUALIFIED: the old driver used journal character length to delimit responses
and matched the previous large catalogue instead of a fresh hit response.
Its pending command was copied, verified as our own, and cleared; logs/world
are retained. The qualified repeat wraps every command with a unique GUID and
requires the exact matching result, including explicit ERROR handling. The
world and failure evidence were not reused to invent a PASS.

Qualified `snapshots.json`, `full-acceptance.json`, `common-results.json`,
`run-full.ps1`, catalog/hit helpers, and six `*.before-stop.txt` journals retain
the complete native oracle and hashes. `check-destructibles-full.py` compares
the real object sets/metadata/health/parts/poses; the common strict driver
evaluator independently passes all three phases.

All88 primary exe/config/account/character/world fingerprints still match
the pre-test baseline. Four primary exes remain
`FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88`.
No primary rollout or owner account changes. An ordinary graphical-client
integration probe is separate and not yet accepted; its startup failures
must not erase this native persistence proof or be claimed as visual PASS.
