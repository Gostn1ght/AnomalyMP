# Marsh runtime findings, 27 September 2026

## Build tested

DX11 job `108625365251` in GitHub Actions run `36321244691` succeeded for commit `b3017f10d`. The packaged client and dedicated server were installed into `gamma-runtime/bin` and `gamma-runtime/dedicated`, respectively. The runtime overlay from `6c2ca22d8` was applied to the isolated `gamma-runtime` role folders. Both processes started on `k00_marsh`; the test account authenticated and its Actor spawned.

The new server log no longer contains `Invalid ogg-comment version`, the four incomplete Lua module load errors, or `pri_a28_school`'s undefined `spawn_isg`. Separate GAMMA content issues remain: invalid NPC weapon loadout references and unsupported IPv6 address parsing.

## Client freeze when opening PDA

The client log ended with `no data from the server for 15 s, leaving the session` and `- Disconnect`. A live minidump of the unresponsive client main thread (`gamma-runtime/appdata/p1/logs/xray_s37_p1_hang_2026-09-27.mdmp`, kept outside Git) showed a wait in `CLevel::ProcessGameEvents` while called from `CLevel::ClearAllObjects` during `net_Stop`. The stack also included `CUIPdaWnd::Reset`; its presence reflects disconnect cleanup and does not establish that the PDA itself deadlocked.

`ClearAllObjects` held `prefetch_lock` across calls to `ProcessGameEvents`, which acquires the same nonrecursive SRW lock. The fix narrows the lock to queue insertion. The netcoop receive watchdog now drains queued packets before checking the 15-second silence threshold, preventing a long GAMMA UI frame from treating buffered server packets as a dead connection. Both changes require a new build and runtime retest.

## Movement pullback

The earlier build showed input sequences being received and processed, but the user reports being pulled back to the spawn point. The code path is client `M_CL_INPUT` to `xrServer::OnMessage`, `ServerProcessInputs`, Actor physics, `M_CL_INPUT_ACK`, and client correction. The precise failure point is not yet established. New dedicated console rows expose the latest movement intent flags, simulated Actor movement state, and authoritative Actor position. During the next live test, hold forward movement and compare whether those flags become nonzero and whether the server position changes. This diagnostic does not return client position authority to the server.
