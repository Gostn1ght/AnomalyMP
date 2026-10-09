# 82. Continuous weather display clock and fixed-replica contact effects

2026-10-09. Owner reports teleporting shadows during emissions and abrupt
weather/evening after the requested time-factor60 test. Continue earlier bugs,
then original188. Original counts27/33/69/59 remain unchanged.

Last completed source4e70cc1a493b60bfc05be838f66d147c3f65b664:
Foundation37841294377 both SUCCESS; DX1137841294449 fullSUCCESS. Native relation/
visibility, burer/controller God and teleport fixtures passed. No package installed
in the running owner session. Its private retained lab still uses qualified904:
server6532/client25468; owner is now playing that client. Do not stop/update it.
The last commit accidentally stored CRLF for previously normalized files; staged
normalization is byte-format only (ignore-space-at-eol diff empty). Include it
in the next source commit without rewriting already published history.

Live904 results: normal native g_god on confirmation + actual server hit power10
health1->1 PASS; normal OFF + power0.2 health1->0.940058 PASS. RP native Stop
callback exactly1/pose exit PASS again. Retained worlds/accounts preserved.
One private wood box15783 destroyed with native power10/impulse40. Its short
client observer captured no fragments; keep failed observation, do not reseed.
Second retained box15852: coordinator arms client before native hit, seven model
parts observed. Fixed client elements still acquire small solver velocities
(e.g. vertical0.0835m/s) despite zero snapshot dynamics. Server fixed=false;
ordinary wooden destroyed parts are CDestroyablePhysicsObject, not solely the
CPhysicsSkeletonObject class added earlier. Do not credit that filter change
with solving all fragments. Wall penetration/full flight acceptance remains open.

Concrete effects defect: CPHElement::Fix -> FixBody sets ODE mass100000000.
ContactShotMarkGetEffectPars multiplies contact speed by sqrt(ODE body mass).
0.05m/s on a replica therefore yields criterion500 and repeated loud sounds/
particles. New game-side correction uses retained element physical mass divided
by ODE mass ONLY for pure-client, live, buffered, fixed replicas. Existing contact
selection, thresholds and effects stay; SP/server/unbuffered/dynamic bodies stay
unchanged. Missing/stale holder, element bounds, body and invalid mass guarded.
Actual helper fixture extends physics test with physical mass cases and guards.
No server force/friction/geometry/impulse edits; full native effects acceptance pending.

Concrete weather defect: game_cl_GameState::net_import_GameTime previously clamps
small display-clock corrections to +/-100ms per packet. A negative correction
still reaches CEnvironment::SetGameTime while WFX active; its TimeDiff interprets
even0.1sec backward as86399.9sec forward and consumes the entire remaining WFX.
The environment cache was not invalidated, but the effect clock still jumped.
Native exact function regression includes this old behavior as evidence.

New pure-client display clock uses Device.dwTimeContinual (unsigned wrap-safe
elapsed), independent of discontinuous network timeServer_Async. Small packet
drift changes only the rate, max10% correction over5seconds, retaining current
phase. Initial sync and explicit +/-60sec calendar jumps retain existing snap/
invalidation behavior. Server/SP getters unchanged; authoritative game calendar
still receives the exact packet value. No AI/player simulation/time-budget edits.
Actual base clock methods + full packet importer + actual environment WFX clock
fixture:7200 jittered frames, midnight, WFX lifetime, rate change continuity,
explicit jumps,32-bit mono wrap and SP path. GHA-only compilation pending.

ADMIN God hint rebind: per-connection field remains ON across respawn but cached
Actor ID did not follow new ownership. Central Process_spawn ASPLAYER owner bind
now updates hint, removes old Actor ID, preserves role/local/connection guards.
Actual binding block + native God helper fixture cover next body, same body,
non-player bind, revoked role and new connection without God. Ordinary players
still do not scan connections on each condition query. Native acceptance pending.

Three actual live mutants22747/22757/22758 observed near70-90m for231 samples:
bone3/8 and positions progress; no permanent freeze in that scoped observation.
Do not call all mutant smoothness fixed. Observer reads cached bone transforms;
does not force CalculateBones or animation/AI behavior. Other distance/target/
species/load cases remain open.

Owner weather probe requested at07:08 is queued, but later player entries are
dead63755/63758 and the alive-only control reader has not armed it. Preserve this
limitation instead of claiming live weather baseline/new-build acceptance.
Current client/server stay running. Original test factor60 was overwritten by
normal emission restoration; confirm current rate from native logs when needed.

Next: GHA qualification, native weather/WFX/contact effects and respawn God on
qualified EXEs, floor hover/drop/restart/late-join, admin demo, mutant freeze,
owner map restoration including requested Darkscape, then remaining188 easy first.

Source5100c7a2735f420df2a0ac0970116c40faa9c4f7: Foundation37883591444
both FAILED; DX1137883591603 engine113668604054 FAILED before engine compile.
Weather fixture extraction referenced a destructor not defined in game_base.cpp;
use next actual getCLASS_ID boundary instead. Generation-only preflight now
extracts all three fixtures (no local compiler/executable). Earlier native God,
physics and relation fixtures ran before this extraction failure; full build
still required. Retain _build/live/destroyable-ci-113668604054.log. No deployment.
