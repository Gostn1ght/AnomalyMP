# Handoff 33 (27 September 2026, continues 32)

CI access: `gh` is authenticated as Gostn1ght. Read job logs with
`gh run view <run> -R Gostn1ght/call --job <id> --log | grep "error C"` and install the
`DX11_dedicated_client` + `DX11_pdb` artifacts into `gamma-runtime/dedicated` and `gamma-runtime/bin`
(PDB copied as `AnomalyGammaNet{Server,Client}DX11.pdb`). Overall run status is "failure" because of
the legacy MT jobs; only `build-job (DX11)` matters. Symbolize dumps with the scratch DbgEng tool
(`.ecxr; kn`) and the matching PDB.

## Verified by running (build `b44c617`, SHA-256 6F607A06..., then overlay `3f3fe48`)

- Account login: pre-created account `tester` (role admin) logs in; server logs `Logged in as tester
  (admin)`, the client receives role 2, player state and Actor are created only after login.
- Server FPS on Marsh is 30; slow movement was the client snapping back to older ACK positions, not
  server speed (fixed in `18f9105`, needs a visual check).
- `sim_squad_scripted.script` create_npc errors are gone with the overlay patrol fallback.
- New crashes found once NPCs came online, each fixed and pushed:
  - client `Level.cpp` spawn prefetch used ALife (`18f9105`);
  - server `Process_event_destroy` assert when removing a disconnected player's Actor (`18f9105`);
  - server `CMonsterEnemyMemory::update` with no Actor memory on dedicated (`17b3140`);
  - server `visual_memory_manager.script:61` db.actor nil (overlay `3f3fe48`);
  - client `ui_main_menu.script:142`: login module name clashed with the engine function
    `netcoop_login` (renamed to `netcoop_login_ui`, overlay `3f3fe48`);
  - client `CCustomMonster::net_Spawn` moving-object quad tree missing on pure clients and server
    `CGameTaskManager::MapLocationRelcase` without a task manager (`913ca1e`, CI pending at handoff).

## Written, not yet verified at runtime

- Server-driven NPC dialogue (`b47f03a`): the talk window shows the server's phrases; trade button uses
  the server trade. Quest tasks given by dialogue live in the server's task state only; client PDA task
  replication is not implemented.
- Legs bind-pose fix, ACK offset reconciliation, client-owned active slot (PDA), hidden host Actor.

## Next

1. Install `913ca1e` (or newer green DX11), run server + client, walk to the Clear Sky base, talk to a
   trader, trade, take a side task; fix crashes from dumps.
2. Replicate per-player tasks to the owning client PDA.
3. Persist inventory per account (only money is persisted now).

## Follow-up after build `513da0bf9`

- The `0x14090E606` dump is the **client** dump `gamma-runtime/appdata/p1/logs/xray_s36_p1_player_09-27-26_15-54-52.mdmp`, not a server dump. Matching DX11 PDB from run `36319015340` resolves it to `CCustomZone::UpdateWorkload`, `src/xrGame/CustomZone.cpp:563`. The function checked `CurrentEntity()` then dereferenced `CurrentControlEntity()`, which is null before the controlled Actor spawns. Commit `b3017f10d` checks the actual pointer. Runtime retest awaits its DX11 artifact.
- The console's white strip is the Win32 `EDIT` command child. `b3017f10d` removes its client edge and paints the edit control black with light text. This has not yet been visually verified on the new binary.
- The red `Invalid ogg-comment version` lines were produced by treating the first ordinary Vorbis text tag as X-Ray binary sound metadata. A sampled GAMMA OGG begins with `Subtitle=...`, `DATE=...`, etc. `b3017f10d` scans comments for a complete engine metadata record (versions 1–3) and otherwise retains constructor defaults. Audio was decodable; this was a metadata parser error, not evidence of a bad audio stream. Runtime sound check pending.
- Four server-side Lua load errors are from fragments whose dependencies are absent in the prepared runtime (`faction_stocks`, `magazine_binder`, `better_stats_bars_mcm`) and one script containing invalid C-style `/* */` Lua syntax. `scripts/quarantine-incomplete-gamma-scripts.ps1` moves only these fragments into an isolated reversible runtime folder; apply and verify on next restart. It does not change original GAMMA files.
- GAMMA `configs/scripts/evac/smart/pri_a28_school.ltx` references `spawn_isg` in its respawn list but defines `spawn_greh` instead. The overlay corrects the reference to the existing Greh squad section. This should remove its genuine respawn configuration error while keeping that NPC spawn path; runtime confirmation pending.
- The changed `CustomZone.cpp`, `SoundRender_Source_loader.cpp`, `Text_Console.cpp` and `Text_Console_WndProc.cpp` translation units passed local DX11 `ClCompile`. The full local `xrGame` compile was stopped after `CustomZone.cpp` had compiled because it was rebuilding hundreds of unrelated units; the GitHub DX11 job for `b3017f10d` is authoritative and was still running at this note.
- The console message `Bad ipAddress format [fdfd::...]` is a real IPv6 support gap in `ip_address::set` and the IPv4-only ban/subnet representation; suppressing that log alone would leave security semantics wrong. Addressing IPv6 requires extending the network address type and its filters.
- `surge_manager.script` currently gates its automatic loop on `db.actor.afterFirstUpdate`. Dedicated netcoop intentionally has no persistent `db.actor`; emissions and dynamic weather therefore need server lifecycle integration plus explicit client event/weather replication. Do not claim they work because the single-player scripts are present or because `surge_manager.start_surge()` exists.
