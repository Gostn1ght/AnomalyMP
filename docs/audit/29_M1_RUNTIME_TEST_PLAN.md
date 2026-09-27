# M1 runtime test plan

Run against identical, hash-recorded binaries from the final green DX11 commit. Use the prepared `gamma-runtime` tree with the complete GAMMA resources; do not mix older executables and DLLs or modify source GAMMA data. Capture server and both client logs, map/save, timestamps, commit SHA, binary hashes and exact launch arguments. For each case record server/client position delta, latest received/processed input sequence, latest ACK, queue length, prediction history length, prediction error and correction frequency.

The user's source modpack is `C:\Users\Mahito\Desktop\Stalker_GAMMA-main\G.A.M.M.A` (`modpack_addons` plus partial `modpack_patches/gamedata`). The prepared runtime uses a merged GAMMA `gamedata` and the installed `C:\Users\Mahito\Downloads\GAMMA\GAMMA\db` archives through `fsgame_server.ltx`; it must not treat the source patch folder as a complete standalone game. Package the final DX11 build with `scripts/package-m1-dx11.ps1`: the dedicated server EXE and DLLs go directly in `dedicated`, and the client EXE and DLLs go in `bin`. Record hashes and use matching files for all participants.

Use `server(all/single/alife/new/portsv=1267/maxplayers=2)` with `-netcoop_start_location=hidden_base` for the marsh test. `all.spawn` is the GAMMA spawn archive; `k00_marsh.spawn` does not exist. The dedicated option reads `[hidden_base]` from `plugins/new_game_start_locations.ltx` before ALife chooses the initial level. Confirm the server log reports `k00_marsh` and the client loads marsh resources before movement cases. Do not count a `fake_start` smoke run as a marsh test.

## Startup and lifecycle

1. Boot the dedicated server and confirm it loads the map, Actor physics, network transport and Lua without renderer/UI failures. Confirm the visible status and log survive loading, focus changes and window overlap. Record memory and log errors.
2. Connect clients A and B. Confirm each creates a player state before `OnCL_Connected` and receives a valid game state, then verify each receives a unique Actor ID and maps to the correct server `xrClientData::owner`.
3. Disconnect A during movement and check its queued/current input is removed; reconnect A and confirm sequences and prediction history reset. Repeat after a location transition if available.

## Movement and prediction

4. Move A with W/A/S/D and diagonal input on flat ground. Compare speed and distance on server, A and B at fixed time intervals. More input packets must not increase movement distance.
5. Test walk/acceleration, sprint, backward sprint attempt, crouch and crouch-to-standing under a low ceiling. Check server speed limits and collision box changes.
6. Press, hold and release jump. Verify one jump per valid edge/cooldown. Repeat with multiple queued commands between server ticks, more than 64 accepted commands before a tick, and under 10% packet loss.
7. Move into a wall, up/down slopes and stairs, and onto a ladder if supported. Check that the authoritative Actor never tunnels through collision and its state stays finite.
8. Measure immediate local response, B's remote interpolation, and convergence after deliberately perturbing A's local predicted position and velocity.

## Network and abuse

9. Inject a legacy `M_CL_UPDATE` with an arbitrary far-away position/velocity; confirm the server Actor transform and remote snapshot ignore it.
10. Send 2×/10× normal `M_CL_INPUT` packet rates; compare server displacement per second. Send duplicate, old, far-future, wrapped and malformed sequences and truncated/non-finite packets. Verify rejection, bounded queue and no crash.
11. Have A try to name or control B's Actor; the server must only bind input to A's connection owner.
12. Drop 5%, 10%, then 20% of traffic; drop/reorder ACKs in `100,102,101,102,103` order. Verify monotonic ACK application and eventual convergence after loss ends.
13. Stop A's input transmission while keeping the connection open. Verify continuous movement ceases after the 500 ms timeout (allowing physics deceleration).

## Exit criteria

Record pass/fail with numeric movement error and logs for every case. A passing compile or a single-client visual check is insufficient. Keep M1 marked `RUNTIME VERIFICATION PENDING` until dedicated boot and two-client movement/security cases pass.
