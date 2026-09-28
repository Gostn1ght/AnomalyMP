# 36 — Reference: another team's multiplayer GAMMA ("Lost Path Online" / "Anomaly COOP")

Date: 2026-09-28. Source: `C:\Users\Mahito\Downloads\GAMMA MULY` (read-only).
Working copies and extracted data are in the Claude scratchpad:
`%TEMP%\claude\C--Users-Mahito-Desktop-NetAnomaly-Engine-Console-2026-09-10-NetAnomaly-Full\635ef86c-1902-46b5-9b7f-722f80ff71c5\scratchpad\ref\`
(below: `REF\`)

- `REF\gamedata\` — extracted `gamedata full.rar` (scripts 1178, configs 4744, shaders 370, textures 71)
- `REF\compare.txt` — hash compare against `gamma-runtime\client\{scripts,configs}`
- `REF\exe_ascii.txt`, `REF\exe_utf16.txt` — strings of `AnomalyDX11AVX.exe`
- `REF\exe_lua_exports.txt` — Coop*/coop_* names the engine exports to Lua
- `REF\frames\<video>\NN_tNNNNs.jpg` — frames (93 total), `REF\sheet_*.jpg` — contact sheets

## Credit / licence note

The author of this mod explicitly allowed reverse engineering and plans to open-source it.
Anything we derive from it (scripts, configs, protocol ideas) must credit the author.
Suggested line: *"Parts derived from Lost Path Online / Anomaly COOP (xray-monolith fork,
server "B4D1K WORLD"), used with the author's permission."* Ask the user for the author's
preferred name or handle before publishing. The window title of the build is "Lost Path Online".
Do **not** copy `configs\coop\chat_*.log` (these are real players' chat logs) or `configs\coop\webhook.ltx`
(it holds their Discord webhook URLs) into our tree.

---

## 1. Architecture in one paragraph

Their build is a **fork of xray-monolith** (the source paths in the exe are `xrGame\coop\CoopSession_*.cpp`
and `CoopRemoteActorManager.cpp`). It does **not** use the stock X-Ray MP (xrServer/DirectPlay) for gameplay.
Every process (host, clients and an optional **headless** host) runs a normal **single-player Anomaly
runtime** with its own ALife and the complete GAMMA Lua. A separate COOP transport sits on top of it,
built on **Valve GameNetworkingSockets** (`GameNetworkingSockets.dll`, UDP, default port **5445**, with its own
transport thread). Authority has three levels:

| Level | Name in code | What it owns |
|---|---|---|
| Session | **Coordinator** (= host, `IsHost()`) | canonical ALife entity registry (spawn/release/parent), world clock, emission/psi timeline, money and trade transactions, chat, party, roles and bans, persistence (SQLite) |
| Location | **Level Authority (LA)** — one player process per level | level scripts: smart terrains, sr_* restrictors, weather solve, dynamic anomalies, quest kills |
| Object | **Object Authority (OA)** — "bubble" owner | runs the **native AI/physics** of one NPC, monster, vehicle or physics object; hands off to another player when needed (`Runtime authority handed off`) |

All other processes hold **Replicas** of the object: the same C++ object, driven by runtime packets instead
of its own AI. So NPC AI does *not* run on the server for everyone. It runs on the machine of a player
near the NPC, and that machine streams the result through the Coordinator to the others.
Remote players are `mp_actor` (`CSE_ActorMP` / `CActorMP`) objects with **deterministic IDs
0xFEFF + PlayerId**. The IDs 0xFEFF..0xFFFE are reserved, and the ordinary ID generator is fenced off from that range.

This differs from our design (a dedicated authoritative server that runs all AI, with client puppets).

## 2. Network protocol (from exe strings)

Message names (the direction checks in the log strings, e.g. `Client sent forbidden X`, show who may send what):

- Handshake: `ClientHello` → `ServerHello` (assigns the player id and role), `ServerInfo`, `SessionInfo`
  (level, checkpoint, strict_progression), `PlayerProfileSubmit/Authoritative` (name, money, community, rank, visual).
- Join and level change: `LevelReady` → **CatchUp** barrier (`JoinSnapshotReady`, snapshot, journal replay,
  `CatchUpAck`, `CatchUpReplayEnd`, `CatchUpComplete`, `PlayerLevelReadyAck`). Runtime messages stay blocked
  until the catch-up is complete. Doors, inventory and container baselines are replayed.
- Entities: `EntitySpawnRequest/Authoritative/Receipt/Rejected`, `EntityReleaseRequest/Authoritative/Rejected`,
  `EntityDetachRequest/Authoritative`, `LevelRuntimeIdOccupancy`. Only the Coordinator creates CSEs.
  A client asks and waits for the canonical ID (`CoopRequestLevelAlifeSpawn`, `CoopConsumeAsyncAlifeSpawnRequestId`).
- Authority: `ObjectAuthorityMaterializedReceipt`, grants and epochs (`Local object authority granted`,
  `Bubble runtime owner resolved`, `Location-scoped authority handoff`).
- NPC runtime (OA → Coordinator relay → replicas): **`[COOP NPC] Runtime captured: id owner epoch seq pos speed
  move body mental slot item tracks torso legs wstate strap action`**. This one packet is their NPC
  animation and weapon-in-hands sync (see §4).
- Physics objects: `PhDataUpdate`, `[COOP PH] Runtime captured ... pos enabled sleep`. Hits on objects are routed to the OA.
- Projectiles: `ProjectileLaunchRequest/Authoritative` (grenades, launchers, committed to the shooter's OA).
- Gameplay intents: `GameplayEventRequest/Execute/Authoritative/Rejected` (runtime execution routed to an executor).
- Player HUD actions: `[COOP ACTION] Local Begin/lifecycle/marker submitted` (semantic item-use animations, §4).
- Script RPC: `ScriptRpcRequest` / `ScriptRpcExecute`. From Lua: `CoopStartScript(module, fn, ...)` (client→host),
  `CoopStartScriptTo(playerId, module, fn, ...)`, `CoopStartScriptAll(module, fn, ...)`, `CoopGetRpcSenderId()`.
  On the host they are queued to the main frame (`Deferred host ScriptRPC`).
- Trade: `TradeTransactionRequest/Authoritative/Rejected`, `TradeSupplyRequest/Authoritative`, `TradeAssortmentSubmit`.
- World: `WorldTimeAuthoritative`, `WeathersUpdate`, `PlayerLocationEvent`, `PlayerSessionEvent`.
- Voice: `VoiceFrameSubmit` (Opus 16 kHz mono / 20 ms / 24 kbit/s + FEC, OpenAL capture, PTT).

Other engine additions: SQLite (`player_capsules.sqlite3`, tables `coop_world_sessions`, `coop_player_capsules`,
`coop_player_inventories`, `coop_player_checkpoint_inventories`, plus admin and role journals), WinHTTP Discord webhooks,
Discord Game SDK (rich presence and "Join"), an ImGui HUD-world editor (F11), a C++ tactical AI layer
(`coop_tactical_ai`, squad roles such as suppressor and flanker), vehicles with driver OA and render-space replicas,
and a **headless mode** (`-headless_client -load <save> -fsltx`, "renderless presentation", text console,
autosave checkpoints archived with 7z).

Console commands: `coop_host`, `coop_connect`, `coop_disconnect`, `coop_stop_host`, `coop_status`,
`coop_players_list`, `coop_kick`, `coop_ban`, `coop_unban`, `coop_role <GUID> <role>`, `coop_give`, `coop_remove_item`,
`coop_set_health`, `coop_set_money`, `coop_set_position`, `coop_jump_level`, `coop_save`, `coop_world`,
`coop_world_sync`, `coop_world_reconcile`, `coop_transition`, `coop_party`, `coop_exchange`, `coop_downed_timer`,
`coop_clear_downed`, `coop_debug`, `coop_render`, `coop_trade_*`, `coop_tactical_ai*`, `set_time`, `set_weather`
(the last two are Coordinator-only and forced through the Level Authorities).

The engine exports **164 `Coop*` Lua globals** (list in `REF\exe_lua_exports.txt`) plus `IsHost`, `IsClient`,
`IsActive`, `IsMpActor`. The engine calls Lua entry points such as `_COOP_LocationEvents.player_joined_session`,
`_COOP_EnvironmentSync.OnAuthoritative/OnBecameAuthority`, `_COOP_ExecutionDomains.NativePre/PostScheduler`,
`_COOP_MAIN.coop_export_current_player_memory`, `_COOP_WorldBaseline.coop_export_world_snapshot`,
`itms_manager.coop_async_spawn_result` and the `_COOP_*Sync.Publish*` functions.

## 3. gamedata inventory and comparison with our gamma-runtime

`REF\compare.txt` (compared by name, md5):
- scripts: 971 identical, **70 changed**, **137 new** (90 of them `_COOP_*.script`, about 77k lines of Lua).
- configs: 3875 identical, 405 changed, 464 new.

New MP scripts (all `_COOP_*`) grouped by role:

| Area | Scripts |
|---|---|
| Core / bootstrap | `_COOP_MAIN` (6k lines: player memory export/import, shared script vars allowlist, inventory m_data, statistics, corpse loot, location notices), `_COOP_MAIN_GAMMA` (GAMMA adapters: MagsRedux, BHS, scopes), `_COOP_ClientPatches` (client-side overrides: corpse loot → Coordinator RPC, companion dialog fixes), `_COOP_ServerPatches`, `_COOP_GamePatch`, `_COOP_LuaCompatPatch`, `_COOP_ExecutionDomains`, `_COOP_ServerCall` |
| Authority glue | `_COOP_SimulationBinders` (authority-aware smart_terrain binder), `_COOP_WorldLogicAuthority` (grant tokens for sr_* restrictor effects), `_COOP_WorldBaseline`, `_COOP_EnemyAdmissionGuard`, `_COOP_GammaEnemyAdmissionShadow`, `_COOP_PlayerAIIdentityPatch` (NPCs treat mp_actor as player) |
| Monsters | `_COOP_BloodsuckerSync` (cloak state, vampire), `_COOP_BurerSync`, `_COOP_ControllerSync`, `_COOP_PoltergeistSync`, `_COOP_PseudogigantSync`, `_COOP_PsyDogSync`, `_COOP_MutantLootSync` |
| Players | `_COOP_BindStalker` (binder of `mp_actor`), `_COOP_PlayerMarker` (nickname above head), `_COOP_PlayerLife` + `_COOP_DownedTreatmentPatch` + `_COOP_DotMarksRevivePatch` (downed state and revive), `_COOP_PvPDamagePatch`, `_COOP_HudActionObserver/Producer` (item-use animations to 3rd person), `_COOP_Voice_mcm` |
| Social / PDA | `_COOP_Chat`, `_COOP_ChatPda` (PDA tab; channels general, faction, party, private; offline mailbox), `_COOP_Party*` (party, roles, ownership, PDA tabs), `_COOP_LocationEvents`, `_COOP_PartyLifecycleNews` |
| Trade / items | `_COOP_TradePatch` (4k lines), `_COOP_VirtualItems`, `_COOP_VirtualItemDetails`, `_COOP_PlayerExchange*Patch` (player-to-player trade via Contacts plus a money slider), `_COOP_GammaMagazineSync`, `_COOP_GridInventory` (optional Tarkov grid, off by default), `_COOP_InventoryHotkeys`, `_COOP_ArtifactExactlyOnce`, `_COOP_SmrLootCompat/RuntimeFence`, `_COOP_WeaponShowcasePatch`, `_COOP_FurniturePatch`, `_COOP_CampfireSync`, `_COOP_GlowstickSync`, `_COOP_InteractivePatch` (doors/usable objects with prediction and rollback) |
| Quests | `_COOP_QuestSpawn`, `_COOP_QuestTaskAdapters` (+ `_NTA2/3/4`), `_COOP_PersistAxrTaskGuard`, `_COOP_PersistRandomTaskBackfill` |
| World | `_COOP_EnvironmentSync`, `_COOP_LevelWeatherDomain`, `_COOP_WorldEvents` (emission/psi), `_COOP_EmissionAuthorityFix`, `_COOP_DynamicAnomalyProducer` |
| Persistence | `_COOP_PersistActorPstor`, `_COOP_DxrPersistence`, `_COOP_KillTrackerCSECompat` |
| Admin | `_COOP_AdminRuntime` (host → owner command bridge with ACK), `_COOP_authority_test`, `_COOP_ID_AUDIT`, `_COOP_NpcDamageTrace` |
| Performance | `_COOP_LazyNpcVoice`, `_COOP_LazyOptimizePatch`, `_COOP_GammaVisionLuaHotCache`, `_COOP_HotEvaluatorFastRejectShadow`, `_COOP_ActorDomainPerf` |
| UI | `ui_coop_servers` (server browser), `modxml_coop_ui`, main menu button `btn_coop_connect` in `ui_main_menu.script`, `configs\ui\ui_coop_*.xml`, `configs\text\eng\st_coop_*.xml` |

Configs: `configs\coop\server.ltx` (name, max_player ≤ 255, port 5445, pve_mode, party_mode, strict session
progression, capsule-only persistence), `server_roles.ltx` (roles user, moderator and admin; custom ids ≥ 4),
`features.ltx`, `trade.ltx` (virtual trade), `presentation.ltx` (`world_arm_pitch_deg`), `player_sounds.ltx`
(semantic sound registry), `static_world.ltx`, `webhook.ltx`. `configs\mp\mp_actor.ltx`
(`script_binding = _COOP_BindStalker.actor_init`), `mod_system_coop_player_world_animations.ltx`
(semantic → 3rd-person motion), `mod_system_coop_tactical_ai.ltx`, `mod_system_coop_3d_icons.ltx`,
`mod_system_coop_hudworld_zz_manual.ltx` (9.6k lines of HUD → world attach offsets).

Changes to core GAMMA scripts are small. `_g.script`, `itms_manager.script` and `ui_debug_launcher.script` get an async
canonical spawn (`CoopPeekAsyncAlifeSpawnRequestId`, `coop_async_spawn_result`). `ui_main_menu` gets a COOP
button and blocks save loading during a session. `axr_main` has a lazy-voice hook. Most other "changed" files are
our own NetAnomaly edits (e.g. `xr_meet` `gamma_pending_meet`) or GAMMA version differences, not their MP code.
Unused legacy code: `mp_bind_stalker_cl.script`, `mp_bind_monster_cl.script`. The commented-out block in
`_COOP_ClientPatches.Patch()` shows their old design, "host controls NPC, client evaluators return false". They moved away from it.

## 4. How each system works

**Player sync / remote players.** The local player is a normal SP `CActor`. Each remote player is a
`CActorMP` replica with id `0xFEFF + PlayerId` and only exists while that player is on the local level
(`CoopIsPlayerOnLocalLevel`; `_COOP_BindStalker` adds it to `db.OnlineStalkers` and `db.storage` so GAMMA
scripts, and NPCs through `_COOP_PlayerAIIdentityPatch`, see it). Movement is owner-authoritative. PvP hits are
applied **on the target owner's process** (`_COOP_PvPDamagePatch` transports BulletID and ammo section so GAMMA's
momo_multihit and Actor Damage Balancer still work). The nickname and PDA spot are placed by the engine (`CoopSession`), the floating name by `_COOP_PlayerMarker`.

**Weapons in hands and animations of players.** The weapon and state come from the actor packet (stock actor_mp
export/import). Item-use animations: `_COOP_HudActionObserver` wraps `game.play_hud_motion`,
classifies every `anm_ea_*` HUD motion into a **semantic** (`coop.item.eat`, `coop.medical.bandage`,
`coop.harvest.cut`, `coop.item.pickup`, ...). `_COOP_HudActionProducer` calls the native
`coop_begin_hud_presentation_action(semantic, duration_ms, speed, full_body, hand, section, anim)` / `coop_end_...`.
The receiver maps the semantic through `[coop_player_world_animation_map]` to a 3rd-person motion (`coop_world_eat`, ...),
or **retargets the HUD hand animation onto the world model** (`[COOP HUD RETARGET]`, split HUD partitions,
arm pitch from `presentation.ltx`). Animation names never go on the wire, only semantics. Downed players play
`norm_death_0` frozen while the CActor stays alive. Sounds use the same idea (`player_sounds.ltx`).

**NPC sync and animations.** The NPC's OA (the player process whose bubble contains it) runs the stock C++ AI and
GAMMA Lua. Each tick it captures **pos, speed, movement type, body state, mental state, active slot, item, animation tracks
(torso and legs), weapon state and strap state, and current action** and sends it. The Coordinator relays it to subscribers on that level,
and replicas apply it natively (`[COOP NPC] Local apply ... tracks torso legs wstate strap`). Replicas run no AI.
Hits on a replica are routed to the OA (`[COOP HIT BRIDGE] Replica bullet hit routed`). NPC shots are presented
on replicas as FX (`[COOP NPC SHOTFX] replica shot`). Special monster abilities are glued in Lua: the OA publishes
native state edges (`object:get_visibility_state()` → `force_visibility_state()` on replicas, burer shield,
poltergeist hidden state, psy-dog phantoms, controller tube). A victim-specific effect (vampire, stomp) goes only
to the victim's process, where native C++ owns camera and HUD.

**Dialogs and trade with NPCs.** Dialogs run **locally on the talking player's process** against its local
NPC object and its own actor (per-player info portions, tasks and news are merged by owner:
`Engine registry merged by owner: info relations news map_locations tasks ...`). There is no dialog protocol.
Only side effects are made authoritative. Trade: special traders use `_COOP_VirtualItems` plus a native
`TradeTransaction*` (items are logical GUIDs with a CSE bundle, IDs allocated only on materialization, money committed by
the Coordinator, "personalized assortment" per player and trader). Ordinary NPC trade keeps the stock
`CInventoryOwner` path. Video frame `frames\19714887518846\02_t0031s.jpg` shows the stock GAMMA dialog window with Petrenko and a `[Торговля]` option.

**Player-to-player trade.** PDA Contacts → RMB invite → stock UIInventory trade layout with Offer and Ready. Money goes through
`CoopExchangeSetMoneyOffer` and a slider dialog (`_COOP_PlayerExchangeMoneyPatch`, native
`CoopPlayerExchangeExtension.h`). Frames: `frames\19661101664806\03..06_*.jpg`.

**Inventory / items.** Every item mutation that creates or destroys CSEs is a request to the Coordinator
(`CoopRequestAttachAddon/DetachAddon/InstallUpgrade/UnloadMagazine`, `CoopRequestWeaponClone` for GAMMA scope
switching, `CoopTransferPlayerInventoryItemToWorldEndpoint`, `CoopRequestLootContainerSync`). Script
per-item data (`m_data`/pstor, MagsRedux rows, BHS limb HP) is moved as "inventory m_data" through
`coop_capture/apply_inventory_item_mdata`. Corpse loot is rolled only by the Coordinator
(`death_manager.create_release_item` → `CoopStartScript("_COOP_MAIN","coop_create_release_item_by_str",id)`).

**PDA.** The stock GAMMA PDA with added tabs: chat (`_COOP_ChatPda`), party (`_COOP_PartyPda`, roles, ownership),
Contacts shows players. Rankings and statistics are merged across players (`coop_stats_*` in `_COOP_MAIN`). News:
"Игрок X зашел на локацию Y" / "подключился к сессии" (`_COOP_LocationEvents`, `_COOP_ServerCall`).

**Quests / tasks.** Per-player task registry. The stock GAMMA task scripts stay untouched. `_COOP_QuestTaskAdapters*` and
`_COOP_QuestSpawn` wrap only the mutation edges (`xr_effects.setup_*_task`, `reward_random_money`,
`fetch_reward_and_remove`, `treasure_manager.set_random_stash`, `news_manager.relocate_item`, ...). The client submits a
semantic intent, the Coordinator creates the CSEs (quest item, stash, critters) and returns canonical IDs, and the Level Authority does the kills.
There are per-player quest item ACLs (`CoopRegisterQuestItemAccess`, private stash content).

**Weather / emissions.** The Coordinator owns the world clock (`WorldTimeAuthoritative`). Weather is solved by the
Level Authority of each level and mirrored to replicas on that level (`_COOP_EnvironmentSync.OnAuthoritative`,
`_COOP_LevelWeatherDomain` freezes WeatherManager during events). Emission and psi-storm have one timeline
scheduled by the Coordinator (`_COOP_WorldEvents`, `coordinator_force_start/end`). Every process plays the presentation, and only the LA
mutates NPCs. Dynamic anomalies are canonical per level on the Coordinator (`_COOP_DynamicAnomalyProducer`).

**Admin tools.** Roles (user, moderator, admin plus custom) are stored per world. Commands are journaled in SQLite and executed on the
owner process (`_COOP_AdminRuntime.Apply` → native `CoopAdminRuntimeApply`, ACK back). There are bans by PlayerGUID, sanctions,
Discord webhooks, and the stock Anomaly debug spawner (frame `frames\17782063630935\02_t0031s.jpg`). An external web
"Anomaly COOP Launcher" (localhost:5555) starts Host, Client and Headless profiles and copies fresh engine builds
(`frames\18755407776344\00_t0001s.jpg`).

**Saves / persistence.** The world is the host's SP save (the headless host loads a save through the stock SP start and autosaves
checkpoints). Each player's character is a **PlayerCapsule** in SQLite on the host (session GUID + player GUID, inventory
payload, actor CSE, "player script memory" = allowlisted pstor/m_data, BHS state, tasks and infos). On reconnect it is
restored by `coop_load_prepared_player_memory` / `_COOP_WorldBaseline.coop_merge_prepared_player_memory`.
A new player gets a character creation screen with faction selection (`frames\18755407776344\08_t0121s.jpg`).
Loading saves is disabled in-session.

## 5. What we can reuse vs. what we must reimplement

Directly reusable (with credit, after adapting API names):
- **Semantic HUD-action idea and data**: `mod_system_coop_player_world_animations.ltx`, the classifier in
  `_COOP_HudActionObserver.script` (catalog of `anm_ea_*` aliases → semantics). We need a native
  `begin/end_hud_presentation_action` equivalent in our message set (e.g. relayed through `M_NETCOOP_SCRIPT`).
- **Monster special-state sync pattern** (`_COOP_BloodsuckerSync`, `_COOP_BurerSync`, `_COOP_PoltergeistSync`,
  `_COOP_PsyDogSync`, `_COOP_ControllerSync`, `_COOP_PseudogigantSync`). With a server-authoritative model the "OA" is our
  server, and `CoopStartScriptAll` maps to our `netcoop_broadcast`. `force_visibility_state` / `get_visibility_state`
  already exist on game_object.
- **Quest adapters list**: which GAMMA functions spawn or remove items and need server routing
  (`_COOP_QuestTaskAdapters*.script`, `_COOP_QuestSpawn.script`). This is a ready checklist for our per-player tasks.
- **GAMMA compatibility knowledge**: MagsRedux (`_COOP_MAIN_GAMMA`, `_COOP_GammaMagazineSync`), BHS state export,
  PvP ADB and momo fix (`_COOP_PvPDamagePatch`), `_COOP_PlayerAIIdentityPatch` (so NPC combat_ignore and relations see the player
  objects), corpse loot routing in `_COOP_ClientPatches`, `_COOP_LazyNpcVoice` (performance).
- **UI**: `ui_coop_servers` (server browser), chat and party PDA tabs (`ui_coop_*_pda.xml`, `_COOP_ChatPda`),
  player exchange money dialog. The logic must be rewired to our RPC.
- `configs\coop\server.ltx` / `server_roles.ltx` format as a model for our server config.

Must reimplement engine-side (their scripts depend on 164 native `Coop*` functions):
- Script RPC with sender identity (`CoopStartScript*`, `CoopGetRpcSenderId`). We have `M_NETCOOP_SCRIPT` one-way only.
- The **NPC runtime packet** fields (pos, speed, move, body, mental, slot, item, tracks torso/legs, wstate, strap, action). This is the
  key to the "NPCs look alive, weapons in hands" result. Our `play_netcoop_puppet` already sends mode + MotionIDs. Compare it
  with their field list and add slot/item/wstate/strap.
- Coordinator-owned entity spawn/release with receipts, catch-up barrier on join/level change, per-player
  persistence (capsules), virtual trade transactions, weather/time/emission authority, voice (Opus).
- Their distributed OA/bubble model is a large design change. Treat it as a reference, not something to port.

## 6. What the user wants to see (from videos and screenshots)

Videos (frames in `REF\frames\`):
- `19714887518846` (6 min, Rostok/Duty base, then Cordon): 2 players together. The other player (nick DIGIMONICH) is visible in 3rd
  person, in armor, **holding a rifle**, with a nickname star (`12_t0181s.jpg`). He **crouches and loots a box with a world
  animation** (`22_t0331s.jpg`). Full stock **dialog window with an NPC** (Petrenko) including the Trade option (`02_t0031s.jpg`). PDA map
  and messages. News "Игрок DIGIMONICH покинул локацию Бар" (`13_t0196s.jpg`). Quicksave by the host
  ("Игра сохранена: b4d1k - quicksave_5 [Host]"), GAMMA HUD, minimap, 3D-scope rifle.
- `19661101664806`: Sidorovich-style bunker, a remote player sitting at the table (red mask), PDA **Contacts** with players,
  **invite to trade → player-to-player exchange UI with money transfer dialog** (`03..06_*.jpg`).
- `18045700409961`: host and client windows side by side (vanilla Anomaly look), trade window in the bunker, PDA news
  "Игрок Stalker зашел на локацию Кордон" (`07_t0106s.jpg`).
- `18755407776344`: **COOP web launcher** (Host / Client / Headless), in-game **server browser** (server "B4D1K WORLD",
  Online, ping), new character creation with faction choice and GAMMA new-game options, then GAMMA loading and spawn,
  **PDA chat tab** (`15_t0226s.jpg`).
- `17782063630935`: Cordon village, Sidorovich PDA broadcast, **debug spawner** used to spawn Freedom and Duty squads,
  large **NPC squad firefight** watched from above (NPCs moving, flanking, dead bodies) (`02_t0031s.jpg`, `06..10_*.jpg`).
- `17527712778836`: driving a modded **G-class car** off-road with a speed/rpm HUD (vehicle sync).
- `19975586777698`: short clip, a remote player (B4D1K) and NPCs running around corpses on Cordon.

Screenshots (in the Downloads folder): two players in exo suits **aiming weapons with lasers in 3rd person** (`0R6N…jpg`,
`VfCK…jpg`). **Downed / revive countdown** ("реанимации 50 секунд") seen from both windows (`RW5k…jpg`). Host/client side-by-side
test with a machine gun (`6RD2…jpg`). PDA messages with player join/leave news (`q4ID…jpg`). A huge weapon pile
(many synced world items), "hold F to take magazine" (`w6PG…jpg`). **3D-rendered inventory icons** `hw3d_v1_section_*.dds`
(`rZi5…jpg`, `2qsY…jpg`, `asEf…jpg`) and item detail windows with 3D preview (`827a…jpg`). G-class car (`xMdi…jpg`).

In short, the target experience is **stock GAMMA** (dialogs, trade, PDA, HUD, tasks) played by several people at once.
Other players are shown as full 3rd-person characters with weapons in hands, item-use animations and name tags.
NPC squads fight believably, and there are join/leave news, chat, party, player trade, downed/revive, vehicles, a server browser and a launcher.
