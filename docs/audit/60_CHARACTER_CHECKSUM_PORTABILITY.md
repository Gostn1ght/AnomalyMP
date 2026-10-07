# 60. Character checksum portability (NCH8)

2026-10-07, Codex. Medium follow-up to doc59; native acceptance pending.

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
global crc32 source is pinned unchanged. Native fixtures/full build/live probe
are still pending; local Python syntax check only, no local native compilation.

## CI and staged real-save migration

Source ed08716d35ddbede33389e5d8f9e0785c405ef6c. Foundation37660141678
SUCCESS GCC sanitizers/MSVC, including actual reader/durable writer and both
actual xrCore CPU branches. DX1137660141680 checks SUCCESS; full engine pending.
Native compilation happened only on GitHub Actions.

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
