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

2026-10-08 Euler source88d72cfeaa6ba9fce94175fbc8e61cfe82906c84 pushed.
Foundation37700338252 SUCCESS Linux+Windows, actual xrCore matrix+adapter
roundtrips PASS. DX1137700338212 script/native fixtures PASS, engine building.
Fresh door-restart-xyz-88d72cfea, door-lock-xyz-88d72cfea and
prop-table-xyz-88d72cfea staged with identical comparators and classifier
overlay. No binaries installed yet. New install-verified.py pins source88d,
cache door-xyz-88d72cfea and all three private roots, retains stock DLLs.
Primary not changed; game processes stopped and debug channels consumed.

## XYZ build and locked-door native acceptance

Source88d72cfeaa6ba9fce94175fbc8e61cfe82906c84: Foundation37700338252
and DX1137700338212 SUCCESS, including full engine/package upload.
Artifact11518765311 validated against source and exe manifest;
ZIP d5e4e3390c2bdda3552f0052bee31a10d6854445356a67883338e5412891834c,
both exes 0AF38FFF87F1EC4FE722E6500EF53B774C78737A93CE3F86E800AD487E5BCF04.
Matching binaries/classifier and retained stock supplementary DLLs installed
only into the three fresh private XYZ roots. No primary rollout.

door-lock-xyz-88d72cfea: native PASS. Original15923 full initial matrix
EXACTLY equals the failed ba82 control. Stock configured transition changes
ph_door@close/unlocked/NPC-unlocked to ph_door@locked/locked/NPC-locked.
Manual checkpoint commits, SAME selftest_door_lock_a loads after restart.
All script/physical/NPC flags match; both-body maximum position error
0.006922010m and rotation coefficient0.011048217 are within the ORIGINAL
0.05m/0.04 tolerances. No geometric movement required for this lock fixture.
Four pre-stop logs, processes alive before stopping, final1/1 both phases;
no retry/disconnect, Lua/fatal/shader/save/capture errors. Existing GAMMA
NPC Loadouts warnings remain (blackops_secondary/wpn_usp_match and missing
ammo_class variants); this is not a globally warning-free GAMMA acceptance.
Full earlier failed poses and lock results remain retained. No client use
distance/faction eligibility/destruction/offline-route acceptance.

door-restart-xyz-88d72cfea: wooden15921 native PASS. Stock authoritative
use_callback closes the initially open/unlocked door; physical rotation
movement1.000946442 is well above the original0.2 requirement. Checkpoint
commits, SAME selftest_door_restart_b loads; sectionph_door@close,
closed/unlocked and physical closed state all retained. Both-body maximum
position error0.007575226m/rotation0.00787269 satisfy the original tolerances.
Final1/1 both phases, no terminal/Lua/fatal/shader/save/capture errors;
one recovered disconnect/retry during phase1 admission, none phase2.
Existing NPC Loadouts warnings remain. This proof invokes a stock server
callback, not a graphical client RPC or player interaction-distance check.

prop-table-xyz-88d72cfea: original table16773 native regression PASS. Full
initial matrix EXACTLY equals the failed ff78 control. Same force moves
3.398434400m/rotation1.329825997, Moved==AtSave, manual SAVE commits.
SAME selftest_prop_restart_a loads; position error0.001266378m/rotation
0.008451282 satisfy the original0.05m/0.04 thresholds. Final1/1both phases,
no retries or terminal/Lua/fatal/shader/save/capture errors.

Three-case native-summary.json records exact source/package, installed exe
hashes, all12 pre-stop log and result hashes, original full initial matrix
equality for trader/table, individual acceptance and recovered retries.
All three cases PASS; one recovered admission retry total (wooden phase1).
Existing NPC Loadouts warnings retained, no broad all-GAMMA-clean claim.
No game processes remain, both debug channels empty, all four primary exes
still FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88.
Primary worlds/accounts/scripts unchanged in this iteration. No deployment.

Accepted scope at the three-case milestone: initialized real-door script closed-after-use and configured
lock/NPC-lock state plus settled physical poses across same-world restart,
with a nonbreakable furniture regression on the matching native GHA build.
Overall L29 remains partial: destruction/fracture, full moving velocities,
offline route enforcement, a separately saved open-door case, and actual
graphical player interaction/RPC are
still unverified.64/max-view/512 and historical188 audit totals unchanged.

## Complementary saved-open native case

door-open-xyz-88d72cfea: fresh world/appdata, same verified88d binaries reused
by explicit paths from the completed wooden-door root; settings only copied,
no saved world/character copied or reseeded. Before capture, stock configured
ph_door@close is selected and allowed30s to settle. Then the actual stock
use_callback opens15921; no forced poses, custom logic or spawn changes.
Predeclared closed-to-open physical rotation requirement remains0.2, with
the same0.05m/0.04 restart tolerances.

Native PASS: movement rotation1.003311251, saved sectionph_door@open,
unlocked/physically open; Moved==AtSave and manual SAVE committed. SAME
selftest_door_open_b loads, all script/physical flags remain equal. Both-body
position error0.000690544m/rotation0.00787269. Final1/1both phases,
no terminal/Lua/fatal/shader/save/capture errors. One recovered phase1
admission retry, none phase2; existing GAMMA NPC Loadouts warnings retained.
This complements closed/locked failure-to-fix controls: this door's stock
default is already open, so it is not a separate negative control proving
binder necessity. No graphical client/RPC/distance proof.

native-four-case-summary.json retains package/exe provenance, all16 pre-stop
log/result hashes and four strict PASS results; original three-case summary
also retained. Two recovered admission retries total, zero terminal failures.
All processes stopped, both debug channels empty, four primaryFE829 exe
hashes unchanged again. Closed, configured locked/NPC-locked and saved-open
door cases plus furniture pose regression are now verified. Destruction,
moving velocities and offline routing remain OPEN; L29 stays partial,
no primary rollout or64/max-view/512/188-total changes.
