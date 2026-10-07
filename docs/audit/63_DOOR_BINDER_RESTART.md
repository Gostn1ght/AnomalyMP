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
