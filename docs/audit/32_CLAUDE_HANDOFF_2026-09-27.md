# Handoff 32 (27 September 2026, continues 31)

Builds are done only by GitHub Actions (`Gostn1ght/call`, workflow `msbuild.yml`). Job logs and artifacts need an authenticated `gh`. Status below separates "written" from "verified by running".

## Commits of this session

- `aa0b4c201` NPC switching around every player, dedicated key-action filter, `CPda::Action` null UI guard, anomaly zone null control entity, client 15 s server-loss watchdog, compat hook `netcoop_client_compat.on_actor_spawned`, Lua overlay. **CI run 36309008038: ordinary build jobs failed with exit code 1 after ~9.5 min (compile error, log not readable without login).** First task: read the DX11 job log and fix.
- `f675b7994` accounts, server-owned money, server-executed trade, admin commands, login window (`src/xrGame/netcoop.cpp/.h`, registered in `xrGame.vcxproj`). CI run 36310133636 pending at handoff; it contains the same unknown error.

## Runtime findings (590 binaries, verified)

- Client inventory crash: `_g.script` loads after the Actor spawn, so the engine `_G.NetCoopClientActorSpawned` hook is not found and `db.actor` stays nil. There is no `level.actor()` binding (the old overlay referenced it). Fixed in the Lua overlay: `db.actor` falls back to `level.get_view_entity()`; `alife()` returns a read-only stand-in on a pure client.
- Settings (all tabs) opened without a crash with the overlay installed.
- Server crash 1: remote Actor jump/land ran GAMMA sound callbacks needing `db.actor` (`oleh_sound_utils.script:58`). Fixed by `netcoop_server_compat.script` (skips `actor_on_*` callbacks when the server has no local Actor). Verified: server logged the skips and stayed alive.
- Server crash 2: client key P is forwarded as `GE_INV_ACTION`; server `CPda::Action` dereferenced the missing game UI (dump symbolized with the 590 PDB). Fixed in `aa0b4c201` (not yet built).
- Client crash: `CCustomZone::shedule_Update` used `CurrentControlEntity()` before the Actor spawned (server was hung). Fixed in `aa0b4c201`.
- "No NPCs": ALife switched objects online only around the server host Actor at the start point. `netcoop_nearest_actor_distance` now uses every player Actor (`aa0b4c201`, not yet built).
- Clients kept playing after the server died (local prediction, long transport timeout). Watchdog added (`aa0b4c201`, not yet built).
- One server run showed a 200k-frame `mcm_log.script(0)` recursion; trigger not captured (log trimmed). Not reproduced in the next two runs.
- A visible idle figure at the spawn point is the server host (story) Actor; still replicated to clients. Not fixed.

## Design of the new features (written, not built)

- Login: client `netcoop_login(login, password, register)` derives PBKDF2-SHA256(password, "NetAnomaly/"+lower(login), 20000) and stores `login|key` in `appdata/<profile>/netcoop_login.txt`; `M_NETCOOP_AUTH` is sent before the profile. Server stores PBKDF2(key, random salt, 60000) in `appdata/server/netcoop_accounts.txt` (`login|role|salt|hash|money`). The key is a password equivalent for this server over the unencrypted transport; the password itself never leaves the client. 5 failures lock 60 s. Duplicate online login rejected. `GAME_EVENT_CREATE_PLAYER_STATE` from an unauthenticated remote client disconnects it.
- Roles: registration always creates `player`; `sv_account_role <login> admin|player` on the server console; `sv_accounts` lists.
- Money: remote `GE_MONEY` rejected; server `GE_MONEY` is broadcast and applied by clients (`inventory_owner_info.cpp`); pure clients ignore `set_money(..., true)`. Balance restored on spawn and saved on disconnect and every 100 server frames.
- Trade: remote `GE_TRADE_*`/`GE_OWNERSHIP_*` into or out of living NPCs or other players are rejected. The client trade window sends `M_NETCOOP_TRADE`; the server checks distance, ownership, prices (partner `CTrade::GetItemPrice`) and funds, then executes. Using an NPC on a pure client currently opens the trade window directly; **the user requires the normal dialogue window with quests** (see next steps).
- Admin: `netanomaly_server.script` (server overlay) — `spawn`, `spawn_at`, `give_money`, `find`, `cmd`, gated by the engine-provided role. On an admin client the GAMMA debug menu runs locally and `alife():create` is sent to the server.
- Saves: save/load/last-save buttons removed from all main menu layouts by the overlay; quick save/load blocked; engine commands were already blocked under `-netcoop`. The new-game button is renamed "Сетевая игра" and opens the login window.

## Runtime overlay

`scripts/patch-gamma-netcoop-overlay.ps1 -RuntimeRoot ..\gamma-runtime` installs `scripts/netcoop-overlay/{client,server}` (scripts and configs), appends `install()` calls to both `_g.script`, edits the menu XML and `ui_main_menu.script`. It has been applied to the current runtime. Test profile p1 `user.ltx` got `bind inventory kI` and `bind active_jobs kP` (backup `user.before-s31.ltx`).

## Next steps

1. Authenticate `gh`, read the failing DX11 log of run 36309008038/36310133636, fix, push, install the green DX11 package into `gamma-runtime/dedicated` and `gamma-runtime/bin` with matching PDB.
2. Runtime test on Marsh: register, login, admin grant, NPCs appear near the player, trader stock visible, buy/sell with server money, reconnect keeps money, P/inventory do not crash the server, killing the server returns the client to the menu.
3. Server-driven dialogue: run `CPhraseDialog`/dialog scripts on the server with the requesting player's Actor as `db.actor`, send phrase lists to the client UI, receive phrase choices; trade phrase opens the trade window; side tasks must be per-player. Main story chain stays removed.
4. First-person shadow: still unverified visually; capture on Marsh after the new build.
5. Hide or stop replicating the host story Actor to clients.
