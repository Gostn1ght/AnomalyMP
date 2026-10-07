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
