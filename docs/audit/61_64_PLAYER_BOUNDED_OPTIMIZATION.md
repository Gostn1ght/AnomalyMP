# 61. Bounded 64-player investigation and normal-client startup

2026-10-07, Codex. Owner prioritizes64, then explicitly limits the attempt:
if no safe solution is available, leave it open and continue other work;
preserve normal game startup/login. Do not reduce NPC population/AI cadence
or player movement speed. No visible frozen/jittering NPC acceptance by bots.

## Scope

Doc60's ff78 source passed strict mixed-save migration/restart and40transfers
with24item UIDs/state preserved. That is reliability, not a64performance PASS.
All four primary exes remain FE829FF4...; tested ff78 exes are801763D6... in
private copies. Do not replace the normal game or change owner account data.

Normal graphical startup probe `_build/live/menu-smoke-primary-fe829` uses
the original primary client exe/config/scripts and original user.ltx settings.
Only appdata is redirected to a fresh private folder. No auth credentials,
character drafts or saved worlds are copied; primary netcoop state hashes
captured before launch. This can verify process/menu rendering startup;
it cannot certify Firebase authentication or entry to the owner's character.
Native compilation remains GitHub Actions only. Startup acceptance pending.

First smoke FAILED on a probe-preparation error: PowerShell's Encoding.UTF8
added EF BB BF before the first `$fs_root$` alias. Primary fsltx begins24 66
and is unchanged. The probe reached CLocatorAPI::get_path fatal `$fs_root$`;
this is a concrete test-config bug, not evidence that the primary game broke.
Failed BOM config/log retained. Private config rewritten with UTF8Encoding(false),
asserted first bytes24 66, then relaunched with distinct menu_smoke_fixed log.
Fixed startup result still pending; no authentication acceptance claimed.

The owner's accidental power-off interrupted the first corrected attempt.
After reboot, existing primary account/draft state hashes still match the
pre-launch snapshot, and the primary exe is still FE829FF4.... Repeated
ordinary graphical startup completed initialization of netcoop_login_ui,
created a responding game window and logged no fatal/script/caught errors.
Probe stopped after checking the same primary state hashes again. Evidence:
menu-smoke-primary-fe829/startup-acceptance.json and menu_smoke_after_power log.
This is process/login-UI initialization acceptance only: no first3Dpresented
marker was observed, no credentials were copied and no Firebase/character
admission was tested. Do not claim full visual menu or owner login acceptance.

Next: one isolated64baseline with unchanged GAMMA population, ordinary spawn
then dense friendly-NPC placement, actual process-liveness/load result gate,
callback/main-frame gaps and main-thread samples. Preserve all logs. Shared
four-core host contention and profiling overhead must be stated. Only optimize
pure repeated work with an equivalence check; no parallel Lua or speculative
cross-NPC sight-ray reuse. Historical188audit counts unchanged.

Private `_build/live/64-baseline-ff78b4197` uses matching801763D6... ff78
client/server exes and private patched server scripts, full existing GAMMA
data/archive roots and working directory. Appdata starts fresh, only valid
user.ltx settings copied; no existing owner or earlier probe state removed.
Current strict retained-world harness waits for actual clock, checks process
liveness and64distinct joined logins/final64playing, freezes bot reports before
shutdown and retains separate pre-stop copies of all logs. Four headless bot
processes below normal, one map, eight-minute measurement, main-thread sampling.
No population/AI/player-movement/cadence changes. Baseline still in progress.

## Bounded64 result: reliability PASS; smoothness OPEN

Eight-minute ff78 probe completed64distinct/final64playing,0terminal failures,
0fatal/Lua/shader/save failures;4initial admission timeout/retry events recovered.
Both ordinary-spawn and dense phases retained. All64players placed by the server
beside9friendly NPCs at -142.09,0.63,-287.58. No NPC moved/removed; map45NPC/27mutants
before/after. Online34→38NPC and23→25mutants through ordinary player activation.

Last six dense reporting windows: p5013–14ms,p9570–96ms,p99122–182ms,max207–409ms;
traffic16.0–18.7MB/s. These are per-window percentiles, not pooled raw frames.
Pre-stop bot reports still have multi-second queue/main-frame gaps (e.g.
3.78s update/3.61s main frame), callback gaps over1s. Shared four-core machine
and16connections per client process materially limit interpretation; no64remote
PC, controlled A/B, graphical max-view or gameplay smoothness acceptance.

Last30s/2705sample report highlights scheduler58.2, stalker41.6, Lua pcall35.5,
script binder15.2, vision12.3, sight rays10.2, visibility hook9.6 and planner8.9.
These are overlapping inclusive address/function aggregates, not additive CPU
percentages; merging multiple return PCs can overcount repeated function frames.
No claim of improvement against older worlds/populations or actual frame costs.

The GAMMA visual hook mutates NPC state; do not memoize its returned value or
parallelize Lua. Rays from different eyes do not have equivalent results.
Public entity UPDATE_Write is already shared per server tick; duplicating an
existing optimization cannot solve these measurements. No quick, proved lossless
solution found in this bounded investigation. Per owner's instruction leave64
OPEN and continue remaining tasks; no primary runtime promotion or AI downgrade.

Two existing GAMMA warnings report missing ammo_class value for
wpn_ithacam37_stakeout_20x70 during NPC loadouts. They are outside the strict
Lua/fatal gate; the entire run must not be called warning-free. No source/config
change was made to conceal them. Initial observer sharing-read error and its
corrected rerun retained separately. Evidence: acceptance.json, profile.txt,
crowd.json, result.txt and exact *.before-stop.txt logs. All processes stopped,
local debug channel empty. Primary account/draft data and exes remain unchanged.
