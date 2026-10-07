# 59. Two-map item state under loss and restart

2026-10-07, Codex. Follow-up to doc58, in easy/medium-first owner order.

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
