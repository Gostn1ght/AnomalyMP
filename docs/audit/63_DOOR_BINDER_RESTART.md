# 63. Actual door binder restart (L29 continuation)

2026-10-08. Doc62 furniture-pose fix passed native acceptance on ba82c7734;
whole L29 remains partial. Continue real doors without main-runtime changes.

## Discovery and failing native control

Fresh private `door-discovery-cordon-ba82c7734` uses validated GHA ba82 exes,
full existing GAMMA data and matching private server scripts, only user.ltx
copied into fresh appdata. Actual Cordon start rookie_village; no owner world,
accounts, characters or executables changed. Three actual doors discovered:
15921/15922 wooden stalker-base doors initially open;15923 trader door closed.
Read-only discovery finished; process/debug cleanup complete.

Fresh private `door-restart-before-ba82c7734` selects15921 by ID/name/visual/
two bodies/one joint. Uses stock authoritative ph_door action use_callback
with the private Actor to close it. This is a binder/physics persistence test,
not a player use-distance/security test. No forced physics or section editing.

Predeclared gate: rotation coefficient change>0.2 (fixed hinge need not
translate), position error<=0.05m, rotation error<=0.04, logical and physical
closed/unlocked state identical after SAME-world restart. Both phases require
one healthy bot, four pre-stop logs, no Lua/fatal/save/capture errors.

Native FAIL: rotation change1.008357291, saved sectionph_door@close,
closed=true/locked=false, physically closed. World SAVE committed and restart
loads same pointer. After restart sectionph_door@open, closed=false,
physically open; rotation error1.008357351, position error0.000821m. Both phases
1/1playing, logs clean. Evidence/failed acceptance retained, no gate relaxed.

Root cause: existing physics-only capture restores bones, but ordinary
generic_physics_binder reconstructs its active section from defaults when
no CSE client_data binder payload exists, then its motor reopens the door.
Saving furniture pose alone cannot prove a real door state survives.

## Scoped implementation; CI/native acceptance pending

Classifier in zz_netcoop_world_rules admits only obj_physic with initialized
active ph_door action and config. Bootstrap/uninitialized doors, unrelated
schemes and Actors are excluded. Missing classifier on legacy script sets
retains physics-only behavior, so executable-only mixing does not block entry;
door logic fix requires its matching overlay.

Only classified doors build the stock CGameObject client-data chunk: shell
enable byte followed by that door's binder save payload. No Actor/game-object
net_Save, global Objects_net_Save or ClientSave. Direct binder->save propagates
exceptions without deleting the live binder; ordinary CScriptBinder::save
swallows exceptions and clears it. Existing stock generic binder markers,
active section, activation times and pstor are retained, using unchanged
CSE client_data format and ordinary loader before door initialization.

Full packet budget checked before appending physics; chunk framing/size,
bone count and EOF checked before atomically replacing target client_data,
bones/flags/root pose. Furniture keeps the accepted physics-only adapter and
existing client_data. No AI/population/player cadence or physics integration
changes. Stock save codec still quantizes poses and drops velocities.

Actual adapter/selection fixture extended for door data replacement, missing/
empty/oversized/throwing binders, no binder deletion, malformed decode and
legacy fallback. Actual Lua classifier and PowerShell error-gate tests pass
locally (no native C++ compilation). Capture refusal now counted by shared
production selftest result helper. GHA native fixtures/full build and actual
same-door restart plus furniture regression remain required. All primary
executables still FE829..., no broad rollout. Locked/destructible/offline-route
state and graphical64/max-view are not accepted by this scope.

## Locked trader-door control also fails

Private door-lock-before-ba82c7734 selects actual15923/esc_trader_door,
visualdynamics/door/door_trader, two bodies/one joint. Stock configured
xr_logic.switch_to_section ph_door@locked closes/locks it and sets the actual
is_door_locked_for_npc flag. This is a controlled state fixture, not faction
eligibility or player RPC proof. Predeclared gate requires state equality,
NPC lock equality and same0.05m/0.04body-pose tolerances; a lock has no
required translation/rotation. SAVE commits, SAME world loads, both bots1/1,
no Lua/fatal/save errors. After restart: sectionph_door@close, lockedfalse
and npc_lockedfalse. Native FAIL retained. No state threshold relaxed.

Source780f3a9d87855c1e2d81e85ca9beff7995a4f1e4 published. Foundation
37696320309 SUCCESS both OS (actual strict adapter/selection tests).
DX1137696320404 native/script checks PASS; full engine building.
Fresh door-restart-fixed-780f3a9d8, door-lock-fixed-780f3a9d8 and
prop-table-regression-780f3a9d8 staged with exact source classifier overlay
and unchanged predeclared comparators, no binaries yet. install-verified.py
will verify cache metadata/hashes and supplement unchanged stock GAMMA DLLs.
Fixed native results still pending. No primary promotion.

## First fixed native result and rotated-joint correction

780 Foundation37696320309 and DX1137696320404 SUCCESS. Artifact11516023907,
ZIP7dd0802f8f01160a53015618ca1fbc1fdfd9f4c46079213dba0b17b103f3ed32;
both exesE589A49A0EA31D01415D5362EC9A13897AE5ED8AD017CE0D691406BDEC7D5770.
Verified package installed only in fresh private roots with matching overlay
and stock supplementary DLLs. Actual wooden door15921 PASS: state remains
ph_door@close, physically closed, two-body pose error0.005344m/0.007873rotation;
bothphasebots1/1, no Lua/fatal/save errors.

Trader15923 locked repeat preserves ph_door@locked/lockedtrue/npc_lockedtrue,
but overall FAIL: leaf position1.991385m/rotation1.026359. Full failure retained
in door-lock-fixed-780f3a9d8, never counted as complete lock/physics acceptance.
Previous ba82 lock control also had a large leaf displacement1.969071m; this
was not purely a lost lock flag. Furniture regression780not started: fix
rotated-joint basis first, then rerun all same controls. All processes stopped.

Actual source cause: CGameObject::net_Spawn uses setXYZ(E->o_Angle), while new
pose adapter wrote getHPB. HPB puts yaw into x; setXYZ expects pitch there.
A yaw90 frame builds its joint axes around the wrong rotation; restoring
absolute bone transforms cannot repair those joint constraints. Change only
adapter to getXYZ. Actual xrCore setHPB/getHPB/getXYZ/setXYZ routines now used
in the capture fixture, plus actual adapter to existing spawn setXYZ roundtrip
for identity, yaw90, coupled/negative angles and gimbal case. No core math,
spawn, AI, physics integration or runtime layout change. New CI/native proofs
pending; primary unchanged.
