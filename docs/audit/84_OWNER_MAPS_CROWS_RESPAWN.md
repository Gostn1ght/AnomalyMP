# Owner changes 2026-10-09: full maps, story retirement, crow/respawn/perception

## Current owner policy (supersedes earlier native acceptance sequencing)

Do NOT launch new in-game/exe tests. Finish source/cluster/chunk/functionality work
across 188 stages first; owner acceptance is deferred. Unit/source and GitHub
Actions checks remain allowed. Build only GitHub Actions. Keep current owner
client/Cordon/Garbage and accounts/worlds; do not replace active binaries.

Remove the five previously retained mini story contacts, including Lukash.
Keep ordinary traders and the scientist at the old Marsh church (owner clarified
church, NOT Doctor in his hut / NOT a generic Yantar exception). Church location
comes from shipped GAMMA dynamic_news_helper: 285.02,1.8,-160.7. The exception
requires ecolog community and the actual Marsh graph level within40m. Generic
population remains untouched. Explicit remove/old mini wins over old cached trade
profiles. Entry to CS/Freedom/Duty now goes through player leadership rather than
unfinishable removed-NPC contract gates. Existing contracts/progress are retained;
no new story NPC created. Scientist exact named profile/native acceptance pending.

New requested work: ALL map traders; no important story spawning; Garbage wrong
extra zone/instant return to Cordon; hostile faction reaction; mutant aggression;
respawn death; crow origin teleport; full visual hoster map list/start/stop/restart;
all maps including labs; latest: NPC/mutant visible view/attack direction mismatch.
These are NOT all closed by this patch. Do not substitute changed status for proof.

## Concrete source fixes

- Full installed map plan33, including10 previously closed maps. Existing address
  assignments preserved; new ports1343..1361. Start locations for missing maps use
  existing changer arrival dump; power_station with no comma now parsed correctly.
  Never overwrite live owner's private2-map config during play.
- Actual CAI_Crow::net_Import previously read Position then called setHPB, which
  resets matrix translation to0. Position applied AFTER rotation. Scheduler binds
  nearest real player; cached corpse pointer list rebuilt for each new query.
- CMonsterEnemyManager::enemy_see_me_now previously tested Actor()==enemy before
  server_player_copy. ServerActorScope makes that true, reading empty server Actor
  visual memory instead of multiplayer perception. Authority test now first;
  ordinary NPC/SP memory kept. Does not claim all mutant aggression fixed.
- Lua death capture no longer writes lethal radiation/psy into a new body. Restore
  receives Character.respawn explicitly for legacy saves, resetting only these
  conditions; living saved conditions and task/pstor progress preserved.

Exact native import/perception fixture is CI-only; actual Lua sandbox/respawn,
faction policy, planner33/stable ports/exclusions, scope checks pass locally.
Native character restore fixture records the respawn argument, progress untouched.
No in-game qualification performed per owner. No increase to188 completion count.

## Previous package qualified; no active rollout

HEAD baseline3885a656ce2ccfdad170aad727c3c06701af7170: full DX11 run37937400053
SUCCESS, Foundation37937399521 Linux/Windows SUCCESS. Artifact11620297828 cached
_build/gha/gameplay-3885a656c. ZIP085e3e61f2de5bede6cc6cf70d53afe3d61d41722cd7664f86f7563d458e22d0;
EXEs547F5C99AD7CAFABE4E311C12719C165661FE34126851420EE72D24FA5D365C6.
Previous qualified native source fixes are described in83. Owner live binaries
remainbd5; old behavior may persist there. Do NOT claim source fixed active game.

## Mass feature preserved, not shipped in this batch

Unfinished tracked edits snapshotted with full files+binary patch at
_build/wip/box-mass-20261009. Untracked netcoop_box_contents.script and
netcoop_prop_mass.h remain. Stock xr_box one-roll content plan and mass APIs
need actual GAMMA item alias/ammo/multiuse fixture, rollback/retained loot failure
handling, complete SDK mass fixture, then GHA. No speculative crate100kg loot.
No content mass installed into owner's game. Resume without losing this work.

Counters remain27complete/33partial/69unverified/59notstarted (161notclosed).

First b7868cf2b qualification: Linux113869710869 PASS; Windows/DX11 runs37945243728/37945243704 refused before native engine compilation: fixture CAI_Crow.health shadowed actual local health (C4458/W4/WX). Rename fixture_health; no production function changed. Retain failed runs.
