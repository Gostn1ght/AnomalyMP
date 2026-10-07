# 62. Physics prop restart acceptance (L29 scope)

Current result (2026-10-08): **scoped table pose restart PASS** on ba82c7734
GHA binaries. Old baseline returns to initial pose, 3.811m from its save;
fixed retained restart differs from its save by0.000701m and0.004414rotation
coefficient. Whole L29 remains partial: real doors/locks/destruction/offline
routes and moving velocities are not accepted by this one-object test.

2026-10-07, Codex. After owner's bounded64 instruction:64smoothness remains
open (doc61); continue remaining tasks without changing normal runtime.

## Native baseline in progress

Private `_build/live/prop-restart-before-ff78b4197`, matching ff78 exes
801763D6..., current patched server Lua and full existing GAMMA archives.
Fresh private appdata, only valid user.ltx copied. No retained world/account
deleted and no primary file changed. Server/bot processes hidden, bot below
normal. Fsgame files written UTF8 without BOM and normal GAMMA working dir.

One real network bot joins. Pick movable nonbreakable obj_physic within150m;
capture global transforms of EVERY body through actual physics Lua API, push
the shell, wait30s, call actual netcoop_world_save, capture at checkpoint,
restart SAME saved world with the same character, then capture all bodies.
Wait for actual clock and healthy bot state before probing. No cleanup/reseed.
Pre-stop logs retained separately; compare real movement and restored pose
before accepting. A matching object origin alone does not prove an opened
hinged door's bone orientation. No native compilation locally.

This first probe checks whichever eligible prop is selected, not all doors,
destroyed objects, ground item gameplay state or offline pathfinding. Those
remain separate unless directly tested. Baseline acceptance still pending.

## Native baseline failure confirmed (2026-10-08)

Selected ID16773, sectionphysic_object, namemar_physic_object_0008, one body.
Force changed position AND orientation, then actual netcoop_world_save returned
SAVE committed. Immediate post-commit pose equals the settled moved pose.
Restart explicitly loaded selftest_prop_restart_b; same object ID/section/body
count returns EXACTLY its initial transform. Position error3.811287m,
maximum transform coefficient error2.659576. No persistence PASS.
All evidence retained in snapshots.json, acceptance.json (passed=false), both
phase logs and pre-stop copies. Both server/bot processes stopped.

Reason: world checkpoint intentionally bypasses whole single-player ClientSave
(dedicated previously crashed there and rejects M_SAVE_PACKET). Runtime physical
bones never reach the ALife entity's saved_bones before its snapshot. Prop
replication does not itself persist the pose. New scoped adapter must call only
the existing physics serializer/decoder, update coherent root position/angles,
and let any capture failure preserve the old world commit. It must not call
inherited game-object/Lua net_Save hooks or alter simulation/AI/cadence. Fixed
CI/build and identical native restart acceptance remain pending.

## Scoped implementation pending CI/native acceptance

2026-10-08: CPhysicObject adapter calls CPHSkeleton::SaveNetState only,
then the existing SPHBonesData decoder into temporary storage. Full decode/EOF
and body count checked before replacement; current root position/angles copied.
Entity identity, section, parent, startup animation and fracture source retained.
37+8*body_count strict packet bound checked before serialization. Existing
engine quantized pose codec retained; this scope does not preserve velocities
beyond the stock physics-save codec. No whole object/Lua net_Save hooks.

Checkpoint captures live props before ALife save; skips removed/attached,
shell-less/zero-body, unrelated objects and explicit flNotSave props. Offline
entities unchanged. Capture refusal/exception keeps previous committed slot.
GHA fixture executes actual adapter/traversal with API doubles and tests metadata,
repeat replacement, malformed decode, overflow and selection. World-store fixture
executes actual checkpoint with injected capture refusal/exception. Real native
pose/restart proof still required; no runtime promotion or L29 completion yet.

2026-10-08 CI: first source1c1d4e383 Linux PASS, Windows fixture build
refused C4458 mock member shadowing and C4244 mock map key conversion under
/WX. Runtime implementation unchanged. Warning-clean fixture successor
ba82c7734a6b17796365d934cd9fad6fcb61a863: Foundation37688229874 SUCCESS
on both OS. DX1137688230023 fixtures/checks PASS, full engine building.
Private fixed root prop-restart-fixed-1c1d4e383 staged; its name references
initial source, probe.json pins successor. Before-run acceptance tolerances
0.05m per-body position and0.04 rotation-matrix coefficient (stock q8 codec).
Same evaluator rejects original baseline3.811m/1.0084 rotation; all4pre-stop
logs clean, bothphasebots1/1. Fixed native acceptance still pending.

## Fixed build and first native run (not accepted)

ba82 Foundation37688229874 and DX1137688230023 SUCCESS. Artifact11513411413,
ZIP06a5546ef1c279a44cf590d465a6e62373ebf51a0f96df27e69ecfbd2a80dc6a;
both exes844FA78596BDF3773F7CAEEED66936738505388004DCC7D60F74876B9D7657AF.
Verified built-from/ZIP/manifest. Cache physics-save-ba82c7734. First private
launch lacked stock GAMMA runtime libraries: no engine log/world reached,
process stopped by exact owned path check, result-first-launch.txt retained.
Missing discord/ICU/OpenAL/TBB DLLs copied unchanged from verified prior private
probe; hashes in runtime-libraries.json. Main files unchanged.

First fresh-world native run then ran both phases successfully. Nearest
selection picked16838/mar_physic_object_0074 (two bodies, one fixed), rather
than original16773table. Force yielded only0.000138m and0.071648rotation,
below predeclared movement proof0.1m AND0.1rotation. Evaluator correctly FAILS
overall (movement_proven=false), even though observed restart errors0.023828m
and0.039708rotation fall inside stock-codec tolerances. All4pre-stop logs
clean, bothphasebots1/1; phase1had1recovered initial disconnect/retry. Do not
accept this as controlled bug closure or all hinged-door state proof. No
threshold relaxed. Evidence/failed acceptance retained.

Repeat prepared in NEW prop-table-fixed-ba82c7734, exact original table16773
by ID/name/section/one movable nonbreakable body, same force/settle/checkpoint/
same-world restart and unchanged comparator. Fixed native PASS still pending.

## Controlled table restart PASS

Private `_build/live/prop-table-fixed-ba82c7734`, same verified ba82 package,
same GAMMA runtime/scripts/configs, fresh private appdata with user.ltx only.
No owner state or retained probe erased. Both phases finished; all processes
stopped and debug channel empty. Original failure and invalid nearest-prop
run remain intact. `pose-acceptance.json` passed=true and
`controlled-proof.json` records exact failed-baseline initial-pose equality.

- ID16773/name mar_physic_object_0008/section physic_object, one nonbreakable
  movable body. Initial FULL matrix equals old ff78 initial matrix byte for byte.
- Same force(8000,1500,0),30s settle, actual netcoop_world_save, immediate pose,
  SAME world/character retained restart,40s settle. No cleanup or reseeding.
- Force changes position3.509865m and matrix rotation coefficients1.191007.
  Moved/AtSave poses exactly equal. Checkpoint commits slot_b in178ms; restart
  explicitly loads slot_b before later periodic saves. Those are actual native
  checkpoints, not simulated IO fixtures.
- Restart position error0.000700716m (about0.7mm); maximum rotation coefficient
  error0.004413590, inside PREDECLARED0.05m/0.04stock-q8 tolerances. Every
  body component checked; identity/body count and all floats checked as well.
- Both phases final1/1playing, zero terminal failures. Phase1one recovered
  disconnect/retry, phase2none; do not call all admission records error-free.
  Four exact pre-stop logs:0fatal/Lua/shader/save/physics-capture failures.
- GHA Foundation Linux+Windows and full DX11 build/package succeed on exact
  ba82. Native adapter reuses the stock saved-bones codec; no world-format,
  AI behavior/population/cadence, player cadence or physics integration change.

Jointed model discovery shows the first16838 is a vise(tiski), not a door;
other nearby joints are buckets, laptop, radio and projectors. Therefore
neither native run proves an opened/locked actual door or route blocking.
Settled furniture pose persistence is accepted; wider moving-body state,
door binder/script state, destruction and offline routing remain separate.
Primary four executable hashes still FE829FF4..., no primary promotion.
