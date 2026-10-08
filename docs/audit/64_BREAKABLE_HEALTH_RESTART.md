# 64. Native breakable health and destruction persistence

Scope: stock CBreakableObject / CSE_ALifeObjectBreakable in a private Cordon
world. Not all CDestroyablePhysicsObject models, joint fractures, moving
debris trajectories, client weapon/RPC authorization or offline routing.
Primary world/accounts/executables remain unchanged. Native builds only GHA.

## Baseline source88d fails damaged health persistence

Verified source88d72cfeaa6ba9fce94175fbc8e61cfe82906c84, GHA37700338212;
both exes0AF38FFF87F1EC4FE722E6500EF53B774C78737A93CE3F86E800AD487E5BCF04.
Private root: _build/live/breakable-restart-before-88d72cfea, fresh appdata
with settings only; verified binaries reused by explicit paths from the
completed wooden-door root. SAME world/characters retained between phases,
no deletion/reset/reseed. Server stopped before bot; four pre-stop logs and
process liveness checked, debug channel consumed.

Targets:15508 meshes/brkbl#0.ogf (damaged),15509 meshes/brkbl#1.ogf (destroyed),
15510 meshes/brkbl#10.ogf (same-session control). All initially native
breakable_object / obj_breakable, health1.0, no dynamic broken shell.
Stock server fire-wound events use the actual hit API and real private actor,
zero impulse. Configured immunity_factor1.3, first hit0.3 leaves health0.61;
follow-up0.5 should break it. Control15510 receives both hits in one session
and breaks;15509 breaks from2.0. Native shells1/5bodies prove both changes.
After20s stock removal,15509/15510 no longer exist in ALife or live world.

SAVE commits selftest_breakable_restart_b, SAME slot loads after restart.
15508's actual CSE STATE_Write health remains1.0 at save and after restart;
the same0.5 follow-up does not break it. Strict overall FAIL with healthy
common gates PASS. Removed15509/15510 remain absent and are not spawned
again. Final1/1both phases,0terminal/Lua/fatal/shader/save/capture errors;
one recovered admission retry in phase1, none phase2. Existing GAMMA
NPC Loadouts warnings are outside the narrow health/save acceptance.
Original snapshots/failed acceptance/logs retained, no threshold relaxed.

## Scoped fix; GHA and native acceptance pending

Live CBreakableObject health was never copied into its existing saved CSE
health. Capture it synchronously on the authority checkpoint path, alongside
existing physics prop capture. Reject wrong type/ID, removed/attached objects
and non-finite health; keep the previous committed world on refusal/error.
Only the existing scalar health is changed, with entity metadata untouched.
A dynamic broken shell maps to0 even when strike/collision broke it without
lowering fHealth. Existing removal behavior stays unchanged.

In -netcoop only, the actual net_Spawn restores saved health<=0 by calling
stock Break before completing spawn. Ordinary freeplay initialization stays
unchanged. No new wire/save version, Actor/global ClientSave, health multipliers,
NPC/population/AI/player cadence or physics integration changes.

GHA fixtures extract actual capture and full net_Spawn methods and actual
checkpoint selection. Cover partial damage, strike break with positive health,
zero/negative health, finite/type/ID guards, metadata, failed base spawn,
unchanged freeplay and selection without a dynamic shell. Shared selftest
evaluator rejects the new breakable-capture refusal log; actual PowerShell
tests pass locally, Python syntax checked. No local C++ compilation.

Required: Foundation/full DX11 GHA, verified matching package; SAME original
native damage/control/removal case with unchanged gates, plus a checkpoint
while still broken before stock removal. Door/furniture capture fixture
regressions remain in CI. Do not promote primary binaries from code-only
proof. L30 stays open pending native acceptance; wider destructibles remain
outside this scope even after these controlled cases pass.

Initial sourcebc61cbb39e1e111a4d27aa2bd6cdfefb1a9bd58f published. Foundation
37719218647 Linux rejected the new fixture before execution: its engine API
double omitted xr_new used by the actual net_Spawn. Actual physics/door/
selection fixture had passed. Add that allocator double; no runtime change,
no relaxed assertions or compiler warnings. Original failure log retained
as _build/live/breakable-linux-bc61.log. DX1137719222296 is superseded because
the same missing fixture allocator prevents full-build entry.

Successore839d45dcad6f821fe581cbc5bda9beb0e619edf, Foundation37719446583 /
DX1137719446579: fixture compiles and exercises the actual code, then FAILS
the failed-base-spawn assertion. Existing CBreakableObject::net_Spawn stored
inherited's false result but still replaced collision state/initialized
physics, only returning false at the end. This is an actual source-path
defect exposed by the fixture, not another missing API double. Add immediate
return FALSE before any model/physics mutation, matching other physics spawn
implementations. Preserve assertion and failure log breakable-linux-e839.log.
No main runtime changed, no native acceptance claim; new CI still required.

Source4fa43fe7d0231df3c5ff4fce4a6bb3c5af70342f: Foundation37719768733
SUCCESS both Linux/Windows, including actual capture/net_Spawn, selection,
strict failed-spawn assertion and prior physics/door fixtures. DX1137719768724
script/native checks PASS, full engine building. Do not push new source
changes while that build is active. Fixed roots breakable-fixed-4fa43fe7d and
breakable-pending-fixed-4fa43fe7d staged with matching classifier and original
oracles/gates, settings only/no world or character copied; binaries absent.
install-breakable-verified.py pins exact source/run/cache and both exe hashes,
then supplements unchanged stock runtime DLLs. Primary remains FE829...

First pre-removal baseline breakable-pending-before-88d72cfea: FAIL.15510
was broken with saved health1.0, then returned intact/health1.0 on SAME restart;
15509 also returned intact. But15509 expired between world commit and the
separate post-save observation, so this run does NOT satisfy a two-present-
objects-at-save gate. Full failure retained; original oracle not relaxed.
Fresh canonical breakable-pending-atomic-before-88d72cfea uses the same stock
timer/damage thresholds, shorter control observation, and combines world save
plus AtSave read into one main-thread Lua action. No intervening removal
frame can distort that observation. Canonical baseline currently running.

Canonical atomic baseline completed: strict FAIL/common gates PASS. Both
15509/15510 are present with genuinely broken shells at the committed save,
yet their CSE health is1.0; SAME world restart recreates both intact/no
broken shell before admission and after40s. Damaged15508 still heals and
survives the follow-up0.5. Final1/1both, no retries,0Lua/fatal/shader/save/
capture errors. Full snapshots/logs/failed acceptance retained. Fixed
pending-removal root uses this exact canonical driver/oracle; only binary
paths, appdata path and source pin differ. Stock10s timer and health gates
remain unchanged. Source4fa full engine build still required.

Source4fa Foundation37719768733 and full DX1137719768724 SUCCESS.
Artifact11525896846 validated: ZIP
cca186089612415e671ee031f9dc627627558d0aa502ba3c5f10f777f8ff6739;
both exesC5D8B3493769BFEF3724CBDECD0E5D34B368CD4010618ECF0224D420C6829395.
Matching binaries installed only in both fresh fixed roots; missing stock
DLLs supplemented with hashes. Fixed native tests started, results pending;
no primary rollout.

## Matching native tests PASS

breakable-fixed-4fa43fe7d: exact original initial typed IDs/names/health/shell
states equal the failed88d baseline. Same first0.3 hit, same0.3+0.5 control,
same2.0 destruction and stock20s removal wait. Manual SAVE commits; SAME
selftest_breakable_restart_b loads.15508 retains actual health0.610000014
at save and after restart; the same0.5 follow-up now breaks it.15509/15510
remain absent, with no recreated names. Strict native PASS, original health
tolerance0.00001 unchanged. Final1/1both,0terminal/Lua/fatal/shader/save/
capture errors; one recovered admission retry in phase1, none phase2.

breakable-pending-fixed-4fa43fe7d: exact original initial state equals the
canonical atomic88d baseline; same driver/oracle/gates apart from binary/
appdata paths and source pin. Both genuinely broken objects15509/15510 are
still present at SAVE; actual CSE health0 for both in the same main-thread
post-save read. SAME selftest_breakable_pending_b loads. They have already
completed stock removal before the first pre-admission observation, remain
absent after40s, and do not appear intact to the admitted test player.
15508 again retains health0.610000014 and breaks on the0.5 follow-up.
Strict native PASS, final1/1both,0terminal/Lua/fatal/shader/save/capture;
one recovered phase1 admission retry, none phase2. Loading logs contain
expected saved-broken entity spawns, not healthy-object acceptance.

native-summary.json records exact validated package/exe hashes, both failed
controls with healthy common gates, full initial-state equality, all8pre-stop
log/result/driver hashes and individual results. Two recovered admission
retries total. Existing GAMMA NPC Loadouts warnings remain; no globally
warning-free GAMMA claim. All processes stopped, both debug channels empty,
all4primary exes still FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88.
No primary promotion or Actor/global ClientSave. No new save/wire version.

Accepted scope: CBreakableObject accumulated damage and saved-broken state
plus existing natural removal across same-world restart. Actual failed-base-
spawn guard is verified in the extracted native method fixture, not a forced
live failure. CDestroyablePhysicsObject health, joint fractures, fragment
trajectories/velocities, graphical/client RPC and offline routing remain
unverified; whole L30 stays partial.64/max-view/512 remain open.
