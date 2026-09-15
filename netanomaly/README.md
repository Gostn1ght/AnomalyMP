# GAMMA on NetAnomaly — experimental integration

GAMMA remains the content/modpack. NetAnomaly supplies the engine. This directory
contains a reproducible engine patch and separate MO2 profiles; it does not turn
the current single-player GAMMA scripts into a finished multiplayer game.

**Not release-ready.** In particular, NetAnomaly disables remote actor Lua binders.
GAMMA crafting, repair, body-part health, quests and persistent inventories still
need server-owned network transactions and runtime testing. Do not interpret a
successful compilation or the 128-player setting as multiplayer acceptance.

## What is changed

- Allow the coop `single` server to export world snapshots, at 30 Hz by default.
- Respect client readiness and network backpressure; do not retransmit stale
  movement as reliable traffic between the server and its internal host.
- Accept 1–128 human players; reserve one additional game-state slot for a
  dedicated ALife host. Fix the remaining spectator array and demo boundary.
- Validate merged packet boundaries and decompressed size before dispatch.
  Correct compressed CRC bounds and use safe LZO decompression. This changes the
  protocol: **every peer must use this same build**, enforced by a separate GUID.
- Reject remote attempts to update another actor or replace/save/load the world.
  Disable the inherited remote Lua admin channel, which logged plaintext secrets
  and gave administrator status to the first account.
- Fix disconnect tutorial null dereference, remote actor becoming the global host
  actor, spawn logging after the temporary descriptor may have been destroyed,
  remote world-clock null dereferences, and timestamp rollover ordering.
- Preserve GAMMA/MCM menu content while blocking SP save/load/new-game menu operations for both roles.
  Add the missing `imgui_on_render` callback without replacing global `table.sort`.
- Generate profiles disabling the specifically listed single-player save, sleep,
  time-skip, travel and loot snapshot mods; report each change in JSON.

## Build — GitHub Actions only

Push checks run on GAMMA branches. An explicit `GAMMA on NetAnomaly`
workflow dispatch, or an authorized push whose head commit message contains
`[gamma-engine]`, also builds the engine. Ordinary pushes do not cancel a build
unless they target the same branch while it is running. It runs Python regression checks and C++ packet-policy tests under
ASan/UBSan on Linux, then builds DX11 x64 on `windows-2022`. No local engine build
is needed. Build logs, profile bundles and runtime are separate artifacts.
Matching PDB symbols are included in the runtime artifact and published compressed
beside the EXE on `codex/gamma-runtime` for debugging through SSH-only Git access.

For an isolated runtime without MO2, extract the original GAMMA
`db/configs/configs.db0` and `db/scripts.db0` using an X-Ray archive converter,
then pass their extracted roots to `materialize_gamma.py --base-data PATH`
(repeat for separate roots). These files have lower priority than GAMMA's loose
files and enabled mods. Separate role config/script aliases need these base
files on disk. The generated filesystem config explicitly defines `$fs_root$`
before archives are indexed, using the same native path separators as the
runtime's data aliases. `--finalize-only` reapplies mounts and role adapters.

`engine/source.json` pins the archived NetAnomaly tree and the matching Monolith
SDK. The original NetAnomaly checkout is shallow and its public remote is
unavailable, so its unchanged tree was archived as a parentless commit in
`codex/netanomaly-engine-base`. Its original commit remains recorded in the lock.
SDK libraries omitted from that snapshot are restored from Monolith 2026.8.17.
Original engine and third-party licenses remain applicable.

## Install into an existing GAMMA setup

1. Download artifacts from a **successful** workflow run. Use a separate test
   installation and a new world: multiplayer persistence is not implemented.
2. Copy `bin/AnomalyGammaNetDX11.exe` and packaged runtime DLLs to the Anomaly
   game's `bin` directory. Keep the existing EXE available for the SP profile.
3. Install `NetAnomaly Engine Data` as an MO2 mod. Enable it below GAMMA patches
   and above the ordinary base game data. Install the generated role addon last
   (highest priority). Do not mount both the client and server role addons.
4. Copy the chosen artifact's `mods` and `profiles` folders into the MO2 instance.
   The templates refer to the standard GAMMA mod names; all GAMMA mods must
   already be installed. Select the new profile, enable profile-specific INI
   and saves, and enable `NetAnomaly Engine Data` in that profile.
5. For a customized installation, generate from its actual `modlist.txt`, using
   the *winning* GAMMA `axr_main.script` and `ui_main_menu.script` as `--axr` and
   `--menu`. Unknown mods are preserved but are not certified compatible:

   ```powershell
   python netanomaly/tools/prepare_profile.py --role client --modlist "D:/GAMMA/profiles/My GAMMA/modlist.txt" --output "D:/GAMMA-net-client"
   python netanomaly/tools/launch_settings.py --role server --nickname Host --players 128
   python netanomaly/tools/launch_settings.py --role client --address 192.168.1.10 --nickname Stalker --client-port 1241
   ```

6. Create the corresponding executable entry in MO2 using the generated JSON
   settings. Run through MO2 so the virtual mod filesystem is mounted. A server
   currently runs as a rendered ALife host: headless GAMMA callbacks require
   separate acceptance. For multiple instances use distinct client UDP ports,
   profile names, log suffixes and **separate appdata paths** in copied
   `fsgame.ltx` files (`-fsltx <file>`); log suffixes alone do not isolate saves.
7. Start the server before clients. The generated command starts a fresh shared
   world. It does not configure persistent storage or safely resume 128 players.

## Verification and remaining acceptance

Local checks are limited to file generation, patch applicability and Python
regressions. C++ compilation and sanitizers run in GitHub. The sanitizer test
uses 100,000 generated malformed frames; it is **not** a 128-client load test.

Before treating this as playable, test: two peers joining/spawning/moving and
disconnecting, reconnect after actor destruction, death/respawn, loot contention,
craft/repair/heal transactions, server saves, shared weather/emissions, menu and
pause behavior, mismatched mods and maps, late join and level changes. Then run
8/32/64/128 actual clients with 50–150 ms RTT, jitter and 1–5% loss; capture server
frame time, bytes/sec, send queue, memory growth and player correction errors for
at least two hours. No claim of successful acceptance is made by this patch.

Known architectural limits: one active simulation map, host-centered ALife,
unfinished remote binders, no authoritative per-player progression/transactions,
no content fingerprint handshake (the inherited coop build skips map/auth checks),
and incomplete validation of legacy event payloads. Public-server deployment
requires those areas to be completed and tested, not merely a higher slot limit.
