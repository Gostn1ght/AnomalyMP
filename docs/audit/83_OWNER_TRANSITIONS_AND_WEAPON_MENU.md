# 83. Owner gameplay regression triage, 2026-10-09

Owner reports: blood on repeatedly shot crate fragments; absent weapon context
menus in inventory/corpse; unpushable ground objects/fragments/corpses; jerky
weather/shadows during emission; enemy kills reduce reputation; late hostile
recognition and squad response; walking/frozen NPC after lethal shots and delayed
corpse fall; inaccessible changer without confirmation; bypassed map boundary;
barrels embedded in walls with repeated contact noise. These are OPEN until
actual gameplay acceptance. Original 188 counters remain 27/33/69/59.

## Live session retained

Qualified bd5 client PID11540, Cordon PID18680 port1567, same retained world
`selftest_owner_gameplay_repro`, account test_admin ADMIN, actor20575. Garbage
PID16316 port1487 started at owner's request, loading retained
`playtest_l02_garbage` checkpoint copied byte-exact from inactive owner4 runtime
into this session's common appdata. Accounts/character/ticket/lease files remain
shared. No new world, automatic damage/teleport, restart or client replacement.
Normal time factor6 restored for transition play. Private automatic input probes
disabled on disk for subsequent map loads, with originals retained privately.

## Route failure reproduced and live repair verified

Actual nearest north changer15726 targets l02_garbage; stored/native destination
agree. Both dedicated processes ready with fresh capacity/status heartbeats.
The physically added `appdata/server/netcoop_cluster.ltx` was invisible to
X-Ray's startup filesystem catalog. Actual native `netcoop_cluster_maps()`
returned empty before SDK appdata rescan and `l02_garbage` after it. Follow-up
native read succeeded (`NATIVE_ROUTE_READY_20261009`); changer silent_mode=1,
enabled=true. No player movement or transfer was scripted.

The first diagnostic also used `ini_file(absolute_path)`, which prefixes
`$game_config$` in CScriptIniFile::update and therefore falsely reported no
locations even AFTER native lookup succeeded. That diagnostic assertion failed;
the corrected verification uses the real native cluster lookup. Do not represent
the first diagnostic as a clean pass or change DLTX cache globally for it.

Source repair: discover a newly created config only when its physical file exists
and the filesystem catalog entry is missing; nonrecursive appdata-only rescan.
Absent configs perform no scan; indexed configs perform no repeated scan.
Original parser, host/port validation, target admission and signed handoff stay.

Source repair: pure multiplayer client always presents the normal changer
confirmation, including silent changers and repeat invitations. Own live Actor
guard remains; server/remote actors cannot show it; SP silent behavior stays.
Actual complete changer methods and config/location helper are exercised in
GHA GCC sanitizers and MSVC W4/WX. Native transfer/dialog acceptance pending.
Map boundary enforcement and cancel-position authority remain separate OPEN work.

## Weapon context-menu blocker

Client log `_g_patches.script:817 pairs(nil)` arises in actual GAMMA
`zzzz_arti_jamming_repairs.has_parts_fieldstrip`: no local ALife record means
`item_parts.get_parts_con` is nil. It aborts construction of the entire menu.

Pure-client guard reads existing parts without evaluation/reroll and declines
only fieldstrip/maintenance predicates when authoritative metadata is absent.
Both registered function pointers are replaced, preserving original names,
actions, bag restrictions and valid-table predicates. Server/SP functions stay.
Exact stock predicate fixture reproduces original nil crash; Lua51 guard cases
PASS, including inventory/corpse modes, valid metadata, no reroll/mutation,
idempotence and SP/server gate. Existing inventory/items/emission/scope checks PASS.

Backed up and atomically replaced only private client's qualified-base compat
overlay; installed guard in already running client through private ADMIN debug
reader. Actual client reports `command true OWNER_MENU_GUARD_INSTALLED_20261009`.
Command file cleared after consumption. No UI input/world mutation performed.
Owner's actual menu retry remains acceptance evidence to collect.

This prevents whole-menu failure; FULL authoritative parts synchronization and
fieldstrip/maintenance/repair/disassembly are NOT qualified by this guard.
Do not invent condition100, random parts, or grant client ALife writes.

## Remaining investigation

Pose-only client shells use Fix with synthetic ODE mass1e8; original physical
mass is retained separately. This explains local unpushability, not real tons
on server. Restore pushes via validated authority contact, not arbitrary global
mass reduction or independent client simulation. Barrel wall contact still open.

Bullet decals select material-pair textures on server. Queued dynamic decals
identify objects by reusable u16 ID without lifetime identity. Blood source
(material/fragment vs late reused ID) not proven. Bounded server bullet_on_hit
observer armed for owner weapon21329, max40 records/120s, no scripted shooting.
Do not declare a decal cause or fix without captured evidence.

NPC records show slow sightings, weapon21329 no_active_item diagnostics and
real deaths; delay source still unproven. Do not throttle AI, change all faction
rewards or hide death symptoms with local kill/teleport guesses.

Weather recovery-tail805 GHA37927028538 fullSUCCESS, cached privately as
`_build/gha/gameplay-805074a69`, artifact11615358162,
ZIP0cb3ec7b76f140bd0cefebd152081952044cf02b1479d9c4721aac861628d4b5,
EXEs104A3A3711FBE2CFFCCF8731DEBC1EF0E1F31E6D494125526C7273472BE90D7D.
Current running bd5 still has prior extra StopWFX; do not interrupt owner to
replace active EXEs. 6114 native weather samples were normal cycle, no WFX;
they are not emission smoothness acceptance. Sun-position readings include
camera translation and cannot alone prove directional shadow jumps.

## 15:58 continuation: authority mass/relation evidence and push source repair

Read-only native server SDK: cupboards15775/15777 have actual25/35kg;
retained destroyable objects15841/15842/15843/15845 have100kg each; corpse22722
11 elements totals94kg. Actor20575 faction actor_stalker rank225 rep-1340.
Army19548/19574 and bandits22736/22713 are already native enemies (relation2,
community-2000); deadarmy22722 also enemy2. This disproves a blanket neutral
faction-table explanation for this session; reaction/perception and exact
reputation delta at hit/death require separate capture. No goodwill rewritten.
Bounded hit-material observer consumed/armed, no matching shot evidence captured.

Important correction: authoritative foot contact already EXISTS for floor items
and corpses in server_physics_update; it was not wholly absent. The actual bug
is props/fragments receive no_feet, and an as-yet-unreplicated sleeping prop is
skipped before any contact can wake it. Source now admits authority foot contact
for props/fragments; deferred awake test keeps untouched props off the network.
Actual masses, speed target/cap, limb-only corpse impulse, positional/directional
bounds, anchor/dead/jump/climb/attached/removed guards and network backpressure
remain. Complete native loop fixture added for GHA, not local compilation.
No wall penetration/contact noise, mass retuning, or full corpses acceptance claim.

830eef835 Foundation37932332920 LinuxPASS/WindowsFAIL and DX1137932332758 FAIL
before full build: session-ownership fixture boundary accidentally captured new
FS helper. a99c3ccd1 narrows extraction; next Foundation37932851682/DX1137932851602
FAIL only W4/WX transition-fixture global `level` shadowing actual argument.
Rename fixture-only global; retain both failure histories. Native push/checks
now awaiting next GHA; no active executable rollout.
