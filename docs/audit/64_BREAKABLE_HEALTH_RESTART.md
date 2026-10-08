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
