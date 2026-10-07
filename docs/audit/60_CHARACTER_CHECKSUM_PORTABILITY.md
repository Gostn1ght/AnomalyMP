# 60. Character checksum portability (NCH8)

2026-10-07, Codex. Medium follow-up to doc59; migration PASS, strict retained-world
restart FAILED on an item-restoration timing window. Follow-up fix in progress.

## Problem and scope

Actual xrCore/crc32.cpp returns raw CRC32C on SSE4.2 and IEEE CRC32 with final
XOR on its software path. The old character loader compared only the current
CPU's result: valid saves from the other path failed admission. Empty data
also differs (FFFFFFFF vs0). World manifests/authority use independent FNV
checksums already; no world/archive/global crc32 changes are needed here.

## Format and migration

NCH8 keeps the NCH7 body/layout and explicitly pins raw CRC32C for actor,
inventory spawn packets, progress and safe/storage spawn packets. All old
NCH3..7 versions remain readable with either legacy checksum. NCH8 accepts
only canonical CRC32C; it does not silently admit an IEEE-tagged new file.
Normal durable save upgrades an admitted old snapshot through the existing
temp/flush/atomic-replace path. Merely reading the old file never rewrites it.

SSE4.2 keeps the previous xrCore hardware call; CPU fallback uses a scoped
portable CRC32C table. Legacy IEEE fallback is checked only after a canonical
mismatch and only for old versions. Global xrCore CRC and archive layouts
remain byte-for-byte unchanged. Profiles, places/parents, item state/UIDs,
progress, safe items and storage revision/signature retain their layout.
Item-state/profile metadata lacked independent checksums before this change;
NCH8 pins existing checksum regions and is not a whole-file integrity redesign.

Older exes do not recognize NCH8. New exes stay private until migration and
restart acceptance; a later production rollout needs a save backup for rollback.
No primary character/world files are changed by this development probe.

## Validation

`scripts/check-netcoop-character-checksum.py` compiles only in GitHub Actions.
It extracts actual complete reader/durable writer and actual xrCore CRC CPU
paths, with engine filesystem/commit dependencies stubbed. Independent Python
binary fixtures cover NCH3..8, both old polynomials, opposite CPU, empty
legacy progress (NCH3), CP1251 profile bytes, nested inventory, safe/storage,
exact migration bytes, corrupt packets/progress/safe, unknown version,
oversized packet/count, every truncated prefix and trailing bytes.
Canonical software results are compared with actual SSE4.2 CRC operations;
global crc32 source is pinned unchanged. Native fixtures and full build passed
on GitHub Actions. Local checks only validate Python syntax; native migration
and retained-world restart acceptance are in progress.

## CI and staged real-save migration

Source ed08716d35ddbede33389e5d8f9e0785c405ef6c. Foundation37660141678
SUCCESS GCC sanitizers/MSVC, including actual reader/durable writer and both
actual xrCore CPU branches. DX1137660141680 full engine/checks/package SUCCESS.
Native compilation happened only on GitHub Actions.

Artifact11501217814 is validated against the run's exact source SHA and ZIP
digest. ZIP SHA256:
`4f5739d22e4a890d52cd5ec2ba562d7f26997e10730fc49b3e9d6e0bf12dd730`.
Both private client/server exe SHA256:
`F0B1D93FA88E61AE9CDD50371134BCA4C6230F71E54910DEDD25A058D7E1D9A9`.
Package cache: `_build/gha/checksum-ed08716d3/validated.json`.

Private `_build/live/checksum-ed08716d3` copies doc59's committed two-map
world/account/character state and keeps all six items per bot. Inputs are real
NCH7 files. Only checksum fields of bots002/004 are converted to legacy IEEE;
bots001/003 remain raw CRC32C. Original bytes backed up in legacy-before/;
legacy-inputs.json records hashes/regions and asserts no non-checksum byte
changed. No new seed/loot, no primary world or account changes. Both legacy
variants must admit, upgrade during ordinary saves to canonical NCH8, retain
UID/state and survive a second restart. Native acceptance still pending.

## Original-exe negative control (expected failure reproduced)

Private `_build/live/checksum-before-5fdedbeed`, same staged real NCH7 input
state, verified original GHA5fded exes A0C3CAF6...; two-minute four-bot test.
General load gate correctly FAILED:2joined/2playing/2terminal failures,
8admission errors/6bounded retries,6departures/6arrivals,2auth redirects,
0Lua/fatal/shader/save errors. ONLY IEEE bots002/004 report cannot-read-character
and character-unavailable rejection. Their file SHA256 remain exactly the
prepared input hashes: no replacement with an empty character. CRC32C bots
001/003 play normally. This is a causal negative control, not a load PASS.
negative-acceptance.json and full logs retained. No probe processes remain.

## Native migration phase (PASS; restart pending)

Matching ed087 GHA exes, retained saved worlds, four bots/two maps,
three-minute workload, 5% loss/+120ms. All four old NCH7 characters admit;
24departures/24arrivals,3auth redirects,0admission errors/retries and
0terminal/Lua/fatal/shader/save/refusal/lease errors. Final report has3playing
and1joining: the cluster test permits an in-flight transfer at its snapshot.
This is four distinct admitted characters, not a claim of final4playing.

All four files are NCH8 with strict canonical checksums for actor, every
item spawn packet, progress and safe section. Fourteen captured observations
per character include one original NCH7 and thirteen NCH8 writes. Full
encoded state of all six carried items, including the ordinary PDA, matches
the original;24unique UIDs. All five profile fields are unchanged. Native
safe inventories are empty; populated safe/CP1251 profiles are CI coverage.

Actual character_save_actor increments storage_revision on every capture,
including transfers. Native revisions advance36→49,38→51,37→50,26→39;
empty request/signature remain unchanged. The probe initially required an
unchanged revision, then corrected that assertion after inspecting the
existing increment in src/xrGame/netcoop_characters.inc. The revision must
never reset; it must not be held fixed during ordinary gameplay.

Evidence: phase1-inventory-history.json, phase1-inventory-checks.json,
upgrade-checks.json, result.txt and distinct checksum_selftest_* logs.
Both servers are now restarting with those same NCH8 files and committed
worlds. No cleanup/reseed; this second phase is still pending.

## Strict restart comparison (FAILED; do not close acceptance)

The three-minute restart workload admitted all four NCH8 characters and
completed24departures/24arrivals with0terminal/admission/Lua/save errors.
The final bot reports had0playing/1joining/3connecting (transfers in flight).
Final on-disk files preserve all24UID/state. However the strict observer
FAILED: nbot_002 observation9, revision60, temporarily persisted all six
UIDs as0 and medkit condition65535/uses2 instead of40632/uses1. Observation10,
revision61, recovers the original state. Other characters/observations match.
One bad durable snapshot is a crash-loss risk even if the next save repairs it.

Evidence retained in restart-inventory-history.json and
restart-inventory-checks.json; final-acceptance.py correctly refuses a PASS.
No failed record is excluded. This is not a CRC mismatch: the bad snapshot's
NCH8 checksums are valid. It exposes an existing runtime restore/capture race.

Root cause: characters_restore_update checked runtime child/parent readiness
but not the budgeted item scan's application of queued saved UID/portions.
It could release the character save/gameplay guard while item records were
still absent. item_state_for_save then wrote UID0 and default runtime portions.

Follow-up: require a nonzero registered UID and no pending item-state restore
before character admission and inventory capture. Existing scan period/budget
and NPC/player movement/AI cadence stay unchanged. During pending restoration,
the original snapshot stays protected. Actual admission and inventory-preflight
fixtures exercise missing record, UID0 and queued restore, then successful
release; no native compilation locally. Fixed CI/native rerun remains pending.
