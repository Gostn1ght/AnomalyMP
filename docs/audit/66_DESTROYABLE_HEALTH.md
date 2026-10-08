# 66. Destroyable physics-object health (2026-10-08)

Status: qualified native baseline failure reproduced; source/CI/package and
scoped native health restart and previous-engine format compatibility PASS.
L30 remains partial; the 22 fully
accepted stages have not increased. No primary-runtime rollout.

## Problem and compatibility

`CDestroyablePhysicsObject` keeps health only in `m_fHealth`, initialized to
1. Its existing server type `CSE_ALifeObjectPhysic` has no health member.
The previous physics checkpoint restored poses but lost partial damage.
This class differs from both `CBreakableObject` (doc64) and the separate
`CPhysicsSkeletonObject` fragment class (doc65).

The adapter writes a versioned owned footer in the existing serialized
`m_ini_string`. The original INI prefix, including `[logic]`, `[drop_box]`,
comments and line endings, is retained exactly. Health is represented by
eight hexadecimal IEEE binary32 bits, avoiding locale or decimal rounding.
Repeated captures replace the same footer without growing it. Existing
records without a footer keep the stock initial health of 1.

This does not change the CSE/network/character format or `client_data`, and
does not call an uninitialized Lua binder's save routine. Cached CSE INI
pointers are not deleted. Spawn reads the raw serialized string rather than
the possibly cached CSE INI. Freeplay continues to use its original health
path; cooperative spawn restores health only after the base spawn succeeds.

Capture rejects wrong type/identity, pending deletion, attachment, missing
shell/bodies, nonfinite health, malformed/reserved metadata and insufficient
packet space. All variable strings, client bytes and compressed body bytes
are budgeted with conservative fixed-field space and the engine's strict
packet bound. Malformed cooperative spawn is refused before base mutation;
capture failure refuses the world commit and retains the previous committed
world pointer through the existing checkpoint error path.

## Reproduction and controls

All probes use private appdata/scripts with validated GHA source
`c8716c4c1f70d1a96e6a5e6aff549c82a5bd38bb`, stock Cordon objects and the
unmodified `dynamics\box\box_wood_01` model. No worlds/accounts/characters
were copied from the owner's runtime. Trusted server `obj:hit` with zero
impulse is used; this is not a graphical weapon or RPC test.

- `_build/live/destroyable-health-baseline-c8716c4c1`: first strike attempt
  did not break the same-session pair control. Its nominal powers did not
  account for model immunity. It is an unqualified attempt, not evidence
  that health persistence passed or failed. Its logs are retained.
- `_build/live/destroyable-health-calibrated-c8716c4c1`: the actual visual
  userdata reports root bone `link`, default/root scale 1, fire and strike
  immunity 0.5, and a destroyed section. Fire-wound raw power is calibrated
  to produce health damage 0.4 and 0.7 (raw 0.8 and 1.4).
- Target 15778 gets 0.4, then 0.7 after restart. Target 15779 gets 0.7,
  then 0.4 after restart. Same-session control 15781 gets 0.4 + 0.7 and
  is deleted before checkpoint; it stays absent after restart.
- Both split-order targets survive their follow-up hits after loading the
  SAME retained world. The same-session pair control is destroyed. This
  qualifies the partial-health persistence failure in both damage orders.
- Both baseline phases finish with 1/1 playing, zero terminal, Lua, fatal,
  shader or save/capture errors. Two admission timeouts recover in phase1;
  none in phase2. Two previous GAMMA `blackops_secondary / wpn_usp_match`
  loadout diagnostic records are reported separately.
  Raw snapshots, full original INI bytes and four pre-stop logs are sealed
  in `health-acceptance.json` by SHA256.

## Source and CI

Source change: `a4b1931db820003ba491e5220c258dfc7d7315ff`.
Foundation [37732630257](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37732630257)
passed Linux GCC/ASan/UBSan. Windows rejected a new test-double member named
`count` shadowed by the extracted actual method under `/W4 /WX`. DX11
[37732630255](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37732630255)
likewise stopped at that fixture before building the engine. Logs retained
under `_build/live/destroyable-ci-113165007812.log` and
`destroyable-ci-113165088549.log`.

Fixture-only correction: `4b74ba7f2b958ec1d4fad26ec68140bc97154816`,
renaming the double's field to `simulated_count`. Actual engine methods,
test assertions and bounds are unchanged. Final Foundation
[37732900872](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37732900872)
completed successfully on both GCC/ASan/UBSan and Windows MSVC.
Both actual-method and actual-traversal PASS records are sealed with job-log
hashes in `_build/live/destroyable-source-ci-proof.json`. DX11
[37732900805](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37732900805)
completed successfully, including full engine build, package and upload.
Artifact `11531705521`, ZIP SHA256
`9db5c78b51039219da3522a521344e6c0fd06d4ffe23c40113d6607c99c3251f`,
both executable hashes
`E4EDE44A70CAEEB43DC9CA00968ECDAE0CF838BDF7D44F4E35341E2EC15FE7A0`.
The downloader validated source revision, GitHub archive digest, archive
paths and the executable manifest before private installation.

The native fixture extracts the actual capture/spawn methods and includes
the real portable codec. It checks exact IEEE bits (including signed zero,
subnormals and 10,000 generated bit patterns), unchanged original INI and
binder bytes, bounded idempotence, malformed/duplicate/reserved/truncated
data, NaN/Inf, identity/type/physics/packet guards, legacy/freeplay and
refused spawn. The existing physics fixture exercises the actual world
traversal for destroyable inclusion, no-save debris and failure refusal.
The actual PowerShell evaluator also rejects destroyable capture failures.
Local Python syntax and PowerShell harness checks pass. Native compilation
and execution run only in GitHub Actions.

## Native acceptance and limits

Fixed private root: `_build/live/destroyable-health-fixed-4b74ba7f2`.
Fresh appdata with user settings only, no world/account/character data copied.
The SAME world is retained across phase1 and phase2 without deletion/reseed.

The first new-package launch was unqualified: fresh staging omitted five
base GAMMA DLLs that were already present in previous working test roots
(`discord_game_sdk`, `icudt65`, `icuuc65`, `soft_oal`, `tbb`). The process
had no journal or world files; its executable path was verified before
stopping it. This is a staging failure, not a native PASS. The package is
an update for an existing GAMMA installation. Only missing DLLs were copied
privately from the previous working root, with hashes in
`runtime-dependencies.json`; package executables/DLLs were not overwritten.
`launch-unqualified.json` retains this attempt. No primary files changed.

The qualified fixed run passes the original damage oracle in both orders:

- Health saved/restored exactly as binary32 `3f19999a` (0.60000002384)
  for 15778 and `3e99999a` (0.30000001192) for 15779.
- Both original `[logic]` / `[drop_box]` prefixes and object names match the
  qualified baseline exactly; both stock classes/shells/body counts are
  confirmed after loading the SAME world.
- The same follow-up hits destroy both targets. The already committed,
  removed control 15781 is absent at save, after restart and after hits.
- Both phases finish with 1/1 playing, zero terminal, Lua, fatal, shader or
  save/capture errors. One admission timeout recovers in phase1, none in
  phase2. Three GAMMA loadout records remain: two `blackops_secondary /
  wpn_usp_match` and one `wpn_ak74u_m1_isg_exps3 / ammo_class` diagnostic.
  These are outside the health fix and are not counted as a full clean
  GAMMA/configuration acceptance.
- `health-acceptance.json` seals snapshots, drivers/configs, package proof
  and four pre-stop journals. The failed baseline's oracle is unchanged.

There is no explicit phase2 checkpoint after follow-up damage; it proves
runtime health restoration/destruction, not an additional post-death
restart case. The previous-engine compatibility probe therefore tests the
explicitly committed phase1 deletion and a separate undamaged stock box
with new INI metadata; it does not use uncommitted phase2 deaths as a
rollback oracle.

Previous validated GHA source `c8716c4c1f70d1a96e6a5e6aff549c82a5bd38bb`
loads the SAME fixed world successfully. Actual crate 15780
`esc_physic_destroyable_object_0001` has the new `3f800000` INI footer,
stock visual/class and one physical body; the explicitly committed removed
control 15781 stays absent. Final 1/1, zero retries/terminal/Lua/fatal/
shader/save errors. One previous GAMMA loadout record remains in this
compatibility phase (four records total including the fixed phases).
This proves format readability, not partial-health restoration on the old
engine: its original health-loss bug remains.

`native-summary.json` combines package/source proof, unchanged health
oracle, compatibility, warning records and hashes of six pre-stop journals.
All test processes stopped; shared debug channel empty. All 88 primary
exe/config/account/character/world files match the pre-test fingerprint.
All four primary exes remain `FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88`.
No primary rollout, world reseeding/deletion or account changes.

Natural fracture, trajectories/velocities, graphical hits/RPC, offline
hydration/routes and all destructible models/maps remain unaccepted.
The stock `CSE_ALifeObjectPhysic` constructor disables `flSwitchOffline`;
this change does not alter that policy. Explicit chunk hydration is separate
work, so ordinary spawn acceptance must not be presented as its validation.
64-player/max-visibility smoothness, chunking and 512-player capacity are
unrelated open work. The owner's primary exes/world/account data remain
untouched by this change.
