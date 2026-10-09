# Hoster controls, fresh monster snapshots, arrival guard and portable release request

## Baseline qualification

e283321d0a6304ef99fb769506502ea0d4e2c6c6 qualified: Foundation37945979928
Linux/Windows SUCCESS, full DX1137945979886 SUCCESS. Artifact11625015288
LostZone-DX11-client-server189590852bytes. Current live owner game stillbd5.
No native/exe/in-game tests started per newest owner policy.

## Current source batch (native qualification pending)

- Native hoster stop IPC is local appdata only, exact process PID. Saves
  each admitted character synchronously, protects committed handoff records,
  flushes background character commits, saves wallet accounts and world before
  quit. Admission/restore/checkpoint failure holds exit for retry. After saved
  exit, packet mutation gate stops movement/events while shutdown is pending.
- Watchdog no longer force-kills an empty world for memory budget. Requests saved
  exit and waits for actual completion before reclaiming memory. Manual on/off/
  auto survive controller restart; restart waits for previous process exit;
  pending stop requests cleared before a new process. Exact runtime/port process
  adoption and a per-runtime mutex prevent duplicate local controllers. Local
  status view is per computer, so shared appdata hosts do not overwrite each
  other's UI. NoAutoStart affects new automatic maps, preserves live processes.
- WinForms panel lists entire configured33map/lab catalog, local/remote ownership,
  server address, state, player count and mode. Start/stop/restart/automatic
  buttons use only the watchdog-owned maps. Offline controller disables actions;
  connect management runs hidden controller without automatically loading maps.
  Read native3 scripts with parser; actual IPC tests passed. GUI visuals NOT yet
  accepted; no game/server processes started for this feature.
- Full GHA artifact now carries hoster scripts and1-Cluster.cmd. Launcher creates
  the default full plan only when missing; never replaces an existing host plan.
- Mutant CCustomMonster snapshots use current frame time, Position and actual
  matrix heading/current body rotation in smooth mode rather than NET.back()
  from slower AI schedule. Same13-field packet; SP scheduled pose retained.
  This helps rotation/motion display; does NOT prove all NPC attack/view bugs
  resolved. Stalker sniper mode can use target rather than current head, and
  interpolation/shot FX timing still need review. Owner reports view mismatches
  for both NPC/mutants; do not reduce AI frequency or use omniscient targeting.
- Changer arrival overlap is held until own new Actor exits true contact shape,
  including Actor ID change at respawn. Later deliberate re-entry invites normally;
  SP/remote/server copies untouched. Server transfer validates actual CFORM
  contact instead of bounding radius+10m. Do not delete unproven stock garbage
  alternate route: dumped GAMMA has8Garbage exits, including2Cordon; owner's old
  bd5 still performs silent changes. Extra-zone graphical acceptance deferred.
- New-body actor load clears old client_data condition/body inventory state and
  resets creature health1 only on Character.respawn. Saved faction/name/money/
  progress restored separately. Living reconnect states remain unchanged.

New actual native fixtures: monster snapshot, saved host stop, new-body reset;
existing actual invitation fixture covers overlap/re-entry/respawn/SP and strict
server contact wiring. Actual character restore fixture covers shutdown packet
mutation gate, ready ACK preservation. All native compilation onlyGitHub Actions.

## Owner request after current fixes: two runnable folders on J:

Prepare client/player game and separate complete dedicated host runtime with
visual map control/start launchers; relocate compressor fromengine-src/compressor.
Do not describe incomplete source/gameplay as final or install active binaries.
J: currently127465619456bytes free (~118.7GiB), rootexistingGames/Mahito/Softs stay.
Merged GAMMA loose data metadata63529367819bytes; two full copies alone consume
127058735638bytes before base archives/binaries. Must measure actual archive+
loose data and pack per-category, use source-readable compatible archive format,
verify portable fsRoot/appdata/db paths and hashes, no junctions back to C:.
Existing compressor xrCompress.exe66048bytes/xrCore.dll831488bytes. Documentation
supports-pack/-strong/-1024/-db; -strong is stronger COMPRESSION, not encryption.
Default xrCompress.ltx excludes levels; map packing needs its dedicated header.
Do not invent unbreakable crypto or change archive format without a matching
GHA-built loader. Any client can be reverse engineered; client distribution must
omit admin credentials, appdata account/session files, private debug probes,
server secrets and PDBs. Public Firebase API config is not an admin secret.
User was told absolute prevention of reverse engineering cannot be promised.
No copying/compressing yet: requested after current fixes, source qualification
and distribution size/compatibility checks still pending. Preserve existing game.

## Remaining mandatory work

All-map trader spawning/coverage; fully preventing important story spawns;
complete hostile faction/mutant retaliation/attacks; actual NPC view/attack
alignment; weapons pickup/context server part data; crate contents-weight plan,
barrel/wall physics; visible weather/shadow smoothing;188 cluster/chunk stages.
Mass WIP remains safely _build/wip/box-mass-20261009 + untracked two source files,
not activated or included in this batch. Do not restore/install it before real
loot rollback/retained spawn transaction and exact stock item cases are qualified.
No live gameplay acceptance now. Audit counters27/33/69/59 retained,161notclosed.

## Latest explicit owner stop (supersedes keep-live instructions)

Owner: turn servers OFF, launch NOTHING for gameplay tests until he writes.
Both exact owned servers18680Cordon/16316Garbage received local trusted saved-quit
requests; both processes now absent. Client was already absent. No watchdog
running. Cordon log confirms selftest_owner_gameplay_repro_b saved(owner requested
shutdown),852ms, world savedtrue. Both command channels consumed/empty. Garbage
save log not independently captured; do not claim a separate native checkpoint
acceptance from consumed-channel status. Original pending channel bytes retained
lab/retained_probes/owner_shutdown_20261009. No force-kill/no new game process.
Continue source stages/GHA builds only; no native game tests, keep worlds/accounts.

ac7d32442 GHA37949783305/37949783349 failed before full engine compilation:
Linux fixture's xr_sprintf(path,"request") instantiated no-argument nonliteral
snprintf underformat-security; change fixture literal%s argument, no production
change. Windows new native host stop/reset/monster/invitation checks PASS, then
lupa missing. A check added after purePowerShell IPC script treated null native
LASTEXITCODE as nonzero and exited the earlier stepSUCCESS before pip install/
PDA checks. Remove that check afterpurePSscript (throws already propagate).
Retain failures. Qualification retry next; no failure installed in player's game.
