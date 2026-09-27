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
