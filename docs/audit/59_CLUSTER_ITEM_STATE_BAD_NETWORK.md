# 59. Two-map item state under loss and restart

2026-10-07, Codex. Follow-up to doc58, in easy/medium-first owner order.

Latest outcome: fixed native four-bot/two-map loss+restart test PASS,
32completed handoffs, all24item UIDs/state retained. Bounty timer fix installed
in primary server scripts; new native exes remain private. Full64/max-view
smoothness and the remaining doc43 stages are still open.

## Scope and setup

Private probe `_build/live/state-loss-c6525f885`; original probe/results in
`_build/live/roundtrip-c6525f885` remain intact. Native binaries are the verified
GitHub Actions c6525f885 package from doc58, not a local native build:
source `c6525f885a7c4c5c562b65e543a1f76610686be8`, both executable SHA256
`7E616CA2282D5FCAF162B9C140FE8A0B6F03EC645CFC46DEC242BC1F7BE677A9`.

Marsh1367/Cordon1377, four authenticated bots in two BelowNormal processes.
Client-only `-netcoop_fake_loss=5 -netcoop_fake_lag=120`; SteamNet simulation
sets 5% send/receive loss and send reordering, split60/60ms lag, global to
every connection of each bot process including reconnects. Server command
uses test-only30s world-save interval; production300s default is unchanged.
Archive/config root and Lua working directory remain the GAMMA runtime;
executables, scripts, accounts, character/world saves and logs are private.

Early seed is armed before either bot process launches, and finishes before
the first handoff. Five ordinary items per bot, plus its regular PDA:

- bandage condition0.43;
- bread condition0.71;
- medkit condition0.62, remaining uses1 (maximum must be greater than1);
- wpn_pm condition0.57, selected ammunition type3, five cartridges of type3;
- ammo_9x18_fmj condition0.83, stack7.

State is set through actual exported game-object methods after each spawned
item has a live server object. Setter readbacks assert portions, ammunition
type/count and stack. No weapons are fired or consumables used in this test.

Observer reads atomic NCH7 files, validates native packet checksums on this
host, decodes all item-state fields (mask, UID, quantized condition, portions,
magazine runs/types/counts, addon flags, ammunition stack). Expected initial
conditions allow one quantization unit, then every captured configured
snapshot must match the first configured snapshot EXACTLY. Object IDs and
parent indices can change between maps; persistent identity/state cannot.
Zero addon flags are checked; attached nonzero addons and mixed magazines
are not covered. GAMMA per-weapon Lua part tables/upgrades are not decoded.

## Acceptance

First native phase FAILED the overall gate: all4 joined, final2playing/
2terminal disconnected,12departures/10arrivals,0admission retries,1caught Lua
time-event error. Both bot logs confirm the configured5%/+120ms network.
All four inventories were configured before the first departure.6/7/8/7
NCH7 snapshots per bot; every configured snapshot preserves all five seeded
items' exact state/UID, including condition, medkit1/2, PM type3 magazine5,
addons0 and ammo stack7. This inventory result does not turn the failed
overall network test into a PASS.

Source map logs record nbot001/004 leaving for Cordon, but their bot logs end
with ClosedByPeer/disconnected and never process that target. Bot update
checked transport disconnect BEFORE receive(), discarding an already queued
handoff when a long bot frame/network delay lets the source close arrive too.
Fix drains received messages first and lets a valid queued target reconnect
outside the queue lock. Ordinary disconnect/malformed target remain failures;
bounded admission retries remain unchanged. Actual update method added to the
native CI fixture alongside start/auth/transfer/retry code.

Empty source map error is `ranks.script:61 ... obj ... nil` from GAMMA's
300s bounty spawn timer. Creation of bounty squads was already disabled by
owner policy, but its actor-dependent spawn timer still ran. World guard now
retires ONLY cycle/bounty_squad_spawn, including an original callback captured
before installation, and makes late registrations retire themselves. Existing
bounty squad state/cleanup timer remains enabled; no population or AI cadence
change. Lua5.1 fixture PASS captured/late/replaced timer, empty map, unrelated
timers and original single-player callback. No blanket ranks nil/error masking.

Fixed native/restart acceptance remains pending. Historical doc48 counts remain unchanged.
Main executables are not promoted, and graphical/max-view64 smoothness remains
open regardless of the result of this four-bot test.

## Original-exe restart and installed timer fix

Restart reused the same worlds/accounts/characters and seeded inventories,
with no cleanup/reseeding; distinct restart log names retain first-phase logs.
Exe remains c652; private world-rules Lua now5fded. Overall gate again FAILED
for the known bot close issue: final3/4playing,1terminal disconnect,
19departures/17arrivals,4auth redirects,0admission retries,0Lua/fatal/shader/
save/refusal/lease errors.13/14/13/3 new NCH7 snapshots: all four inventories,
including their regular PDA, match the original fully configured inventory's
complete state/UID in EVERY snapshot.24unique UIDs across all four inventories;
none duplicated. This is inventory/restart evidence, not a network PASS.

Native BountyRetireProbe inspected the actual RemoveTimeEvent closure queue:
captured cycle/bounty_squad_spawn absent, late registration executed and
retired, cycle/bounty_squad_state retained the original callback and node.
PASS line in the restart Marsh log. Existing squad state timer kept running.

After that proof, installed only the repo world-rules Lua in primary
gamma-runtime and LostZone-3D-Hideout server/scripts; checked both were exactly
the previous repo version before replacement. Backup and installed.json in
`_build/live/quick-bounty-5fdedbeed/primary-backup` (metadata one level above).
Before SHA256 `68c6214bd635f0c99ba22a330238e5fe43aeadd25efdcbdb861d938d513f3648`;
after `4009eb8435eea5677f80cf44baf2d9ded4729c856ed9d8755eee4bcc11bc6ca1`.
All four primary exe hashes remain FE829FF4... as in doc58.

Fixed source5fdedbeedde4c8a2d0f54caba5f378dc0ad45cca:
Foundation37653762284 SUCCESS GCC sanitizers/MSVC, DX1137653762280 checks SUCCESS;
full engine/package still pending at this entry. Fixed-build probe staged in
`_build/live/state-loss-fixed-5fdedbeed`, copied committed state, no new loot.

## Medium follow-up after this native acceptance

Portability of saved character/world checksums needs migration-aware work.
Actual xrCore/crc32.cpp uses raw CRC32C with SSE4.2, but IEEE CRC32 plus final
XOR in its fallback; even the empty-buffer checksums differ. Character packet
and progress readers compare only the current host's crc32(). This probe's
raw CRC32C decoder is correct for this host and does not prove cross-hardware
recovery. Do not change global engine CRC casually: existing archives and save
formats also consume it. Explicit format/compatibility fixtures come before
any scoped migration. This issue remains open, separate from the bot fix.

## Fixed package verification

DX1137653762280 full engine/checks/package/upload SUCCESS.
Artifact11497984354,189604134bytes, cache `_build/gha/queued-close-5fdedbeed`.
ZIP SHA256 `4212f4a3e7b549e782c4f3a89d2e4b2cafa39777cdb19bb4bb96f61462b1f3cc`;
both exe SHA256 `A0C3CAF6E439F31839F4ACE56D7E34CCC7F91E436A50F40C00C6C913C8ABFFD2`.
Built-from, manifest and GitHub artifact digest verified. Missing third-party
DLLs supplied only in the private probe from the previous verified runtime.
Four-minute fixed-exe bad-network continuation started with copied committed
world/account/character state; no cleanup or reseeding. Acceptance pending.

## Fixed native acceptance (PASS)

Four-minute continuation on matching5fded GHA exes: final4/4playing,
0joining/connecting/terminal failures,32departures/32arrivals,3auth redirects,
0admission errors/retries. EACH bot has4arrival records on EACH map. Both
bot logs confirm5% loss/reorder/+120ms. Zero Lua/fatal/shader/save/refusal/
lease errors. No client ClosedByPeer record in this successful run; the
specific queued-target-plus-close race is deterministic in the actual-method
GCC sanitizers/MSVC fixture, while native integration verifies the workload.
Do not claim a controlled native race or graphical-client reproduction.

18NCH7 observations per bot (includes starting committed state): ALL six
items per bot, including regular PDA, exactly match the original pre-restart
inventory in EVERY captured observation.24unique UIDs, no duplication; all
condition/portions/ammo type+magazine/addon0/stack fields preserved. These are
static inventories; client wear/fire/consumption, nonzero addons, mixed
magazines and GAMMA Lua weapon-part state remain outside this acceptance.

Both servers loaded saved worlds; no bootstrap. World-save counts:
Marsh periodic8/last-player-left5; Cordon periodic6/last-player-left4.
Native BountyRetireProbe recovered the ORIGINAL GAMMA spawn timer from the
guard closure and reproduced ranks.script nil-actor failure under pcall,
then verified fixed late-callback retirement and the unchanged state timer.
This confirms the causal diagnosis, without muting unrelated ranks errors.

Evidence retained: original failure+restart root acceptance.json/histories/
checks/logs; fixed root acceptance.json/result.txt/inventory-history.json/
inventory-checks.json and native logs. All probe processes stopped and debug
channel empty. All four primary exe SHA256 remain FE829FF4... unchanged.
Server/bot frame gaps and hitches still exist in logs; this is reliability
and inventory acceptance, not smoothness/performance acceptance or an A/B.
Historical doc48 counts remain frozen; no full188-stage completion claimed.
