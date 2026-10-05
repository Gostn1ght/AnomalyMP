# 45. Handoff для Codex (кластер локаций, 2026-10-05)

Этот файл — самодостаточное задание для продолжения работы, если сессия
Claude остановится по лимитам. Обновляется после каждого шага.

## Координация (Claude снова активен с 2026-10-05 23:30)

Claude и Codex работают в одной папке `engine-steamnet` и одной ветке.
Каждый коммитит только свои файлы (`git add <path>`, не `-A`), перед push
делает `git pull --rebase gostn1ght menu-3d-hideout`.
- Codex: `backend/**`, `netcoop_transit*`, stash visits, wallet/account store,
  player-transfer fixtures.
- Claude: replication/interest management в engine (`xrServer.cpp` snapshot,
  doc 43 D), трафик на игрока, установка билдов и самотесты на реальных exe,
  3D меню (плакат).
Если нужно тронуть чужую зону — записать здесь строку перед изменением.
- Claude 23:50: H11-lite в `zz_netcoop_world_rules.script` — в режиме кластера
  один раз на мир (после fill_start_position) release generic отрядов чужих
  карт (story/companion/scripted остаются). После установки этого билда
  копии чужого населения в location process исчезают; Codex может решить,
  достаточно ли этого, чтобы включить `-netcoop_npc_transit` по умолчанию.
- Claude: статус серверов `netcoop_cluster/status_<port>.txt` (players/capacity,
  TTL 30 с); переход/redirect не ведут на выключенный или полный сервер.

## Правила владельца (обязательно)

- Сборка движка только через GitHub Actions: `git push gostn1ght HEAD:menu-3d-hideout`,
  workflow «Lost Zone DX11», артефакт `LostZone-DX11-client-server`
  (`gh run download <run> --repo Gostn1ght/AnomalyMP -n LostZone-DX11-client-server`).
  Новый push отменяет идущий DX11 run (cancel-in-progress) — не пушить во
  время сборки, если её результат нужен.
- Lua overlay ставится только из этого репозитория:
  `scripts/patch-gamma-netcoop-overlay.ps1 -RuntimeRoot ..\gamma-runtime`.
- Runtime владельца: `..\gamma-runtime` (сервер `dedicated\`, клиент `bin\`),
  клиент с 3D меню: `..\LostZone-3D-Hideout`. Старые exe: `gamma-runtime\backup-e90a2d2`.
- Нет респавна NPC/мутантов; сна нет; мебель только в помещениях вне безопасных
  зон; всё сохраняется после рестарта (см. doc 41 конец, doc 43).
- Отношения фракций игроки не меняют; репутация per-player.
- Коммиты: в конце `Co-Authored-By` строка ассистента; не добавлять чужие файлы.
- Lua-проверки локально: `python scripts/check-netcoop-items.py`,
  `python scripts/check-netcoop-world-rules.py` (нужен `pip install lupa`).

## Что сделано (код, в игре не проверено)

Кластер локаций — `src/xrGame/netcoop_cluster.inc` (+ хуки в `netcoop.cpp`,
`xrServer.cpp`, `level_changer.*`, `netcoop_characters.inc`, `netcoop_bots.cpp`):
- один dedicated процесс на карту из одной runtime папки; адреса карт —
  `$app_data_root$/netcoop_cluster.ltx` `[locations] k00_marsh = host:port`;
- M_CHANGE_LEVEL клиента → сервер проверяет переход (`g_lchangers`, радиус+10 м),
  замораживает игрока, синхронно сохраняет персонажа в точке прибытия,
  пишет HMAC-билет `netcoop_cluster/ticket_<login>_<slot>.txt`, снимает lease,
  шлёт клиенту `netcoop_transfer host|port|level`; клиент делает
  `start client(host/name=login/port=port)`;
- lease аккаунта `netcoop_cluster/online_<login>.txt` (heartbeat 10 с, TTL 30 с);
- вход на сервер другой карты → `redirect|host|port|level` в auth result;
- общий `netcoop_accounts.txt` сливается между процессами (named mutex, mtime);
- `zz_netcoop_world_rules.script`: generic цели отрядов только на своей карте;
- задания помнят карту выдачи (`CGameTask::m_netcoop_origin`), другие серверы
  их не вычисляют;
- облачный (Firebase) вход теперь отправляет auth при подключении (`client_can_login`);
- запуск: `gamma-runtime\netcoop_cluster_start.bat` (Болота 1267, Кордон 1277);
- самотест: `scripts/run-cluster-selftest.ps1 -Runtime ..\gamma-runtime -Bots 4 -Minutes 12`
  (порты 1367/1377, `appdata\selftest`, флаг `-netcoop_cluster_selftest`).

Дополнительно (коммиты после `a3bf4e0`, ещё не собраны на момент записи):
- `092b269` общий календарь кластера: каждый сервер пишет `netcoop_cluster/clock_<port>.txt`,
  отстающий ускоряет время (до 4x) до догоняния — без скачков;
  generated задания с целью (не story) на другой карте отменяются
  (`netcoop_server_compat.cancel_task_on_other_map`);
- `c59a005` общее расписание выброса для кластера (`netcoop_emission.script`,
  слот частоты + детерминированный час, слот помнится после рестарта);
- `837632e` `scripts/netcoop-cluster/netcoop_cluster_watchdog.ps1` — перезапуск упавших серверов;
- `gamma-runtime
etcoop_1_server.bat` поднят до maxplayers=16 (бэкап `.bak_cluster`).
- Компаньоны при переходе остаются ждать на старой карте и снова следуют,
  когда игрок вернётся (уже так по `get_script_target`); перенос NPC между
  серверами — H09, не сделан.

## Очередь задач (по приоритету для ЗБТ)

1. Прогнать самотест, починить найденное (логи `gamma-runtime\appdata\selftest\logs`,
   `appdata\selftest_bots\logs`, строки `[cluster]`, `[bots]`).
2. Общее время/погода/выброс кластера (doc 43 B09–B13, J). Решение владельца
   нужно: идёт ли время, пока сервер карты выключен. Часы `netcoop_alife_clock.h`
   запрещают скачки — нужен catch-up API, не отключать проверку.
3. Задания между картами (doc 43 I): цели на другой карте должны выбираться/
   проверяться на сервере той карты (story id), награда идемпотентна.
4. NPC transit между серверами (H09/H10) — после 2–3.
5. Нагрузка 16–32 игроков: `-netcoop_bots N -netcoop_bots_addr 127.0.0.1/port=1267`.
6. Плакат «Революционный проект «Фолк Восянка»» в 3D меню: генератор готов
   (`tools/make-soviet-poster.py <фото>` → `client/textures/netcoop/poster_folk.dds`),
   `build-lostzone-room.py` вешает его на заднюю стену (x -1.6..-1.0, y 1.36..2.26)
   только если DDS есть. Ждёт фото от владельца (файл не сохранён на диск);
   после генерации: пересобрать комнату, overlay patch, коммит. Комната: `scripts/build-lostzone-room.py`,
   задняя стена Z1=3.0, текстура в `scripts/netcoop-overlay/client/textures/`.

## Журнал

- 2026-10-06 01:20 (Claude) — билд `5302a58` установлен в gamma-runtime.
  `scripts/run-world-restart-test.ps1`: «[world] saved selftest_restart_a (periodic)
  in 207 ms» → перезапуск → «loading saved world selftest_restart_a», игровое время
  продолжилось. ПЕРВОЕ успешное сохранение/загрузка мира на реальном сервере.

- 2026-10-06 00:10 (Claude) — самотест на билде `8d586d8`: 96 переходов, 0 ошибок.
  НАЙДЕН БАГ: в `netcoop_server_compat.script` цикл AddUniqueCall вызывал
  `owned_objects_update/stash_visits_update/keep_switch_distance`, объявленные
  `local` ниже по файлу → nil globals, ошибка каждый кадр, ни одна из трёх
  функций (мебель/тайники/визиты в тайники/switch distance) в игре НЕ работала.
  Исправлено forward-объявлением (`2139a01`), CI-проверка
  `scripts/check-netcoop-lua-scope.py`. Codex: lupa-фикстуры вызывают функции
  напрямую и такое не ловят — проверять и сам цикл.
  World save: ни одно сохранение мира не прошло ни в одном логе (owner/selftest).
  Причина: `Level().ClientSave()` в `world_store_save_now` падал (SEH, catch(...))
  в Objects_net_Save на dedicated до первого M_SAVE_PACKET (которые netcoop и так
  отклоняет). Убрано в `846664a`; ждёт проверки на реальном сервере.

- 2026-10-05 23:35 (Claude) — нагрузка, билд `1566b38`, один сервер Болот, 16 ботов,
  8 мин: 16/16 играют, 0 отвалов; кадр сервера avg 9–14 мс, max 127–209 мс;
  трафик ~110 КБ/с на игрока (~1,7 МБ/с на 16) — для интернета много, нужна
  экономия snapshot (задача). Следующее: установить DX11 `8d586d8` и повторить
  кластерный самотест (изменения Codex в player transfer/wallet).

- 2026-10-05 22:10 — самотест на билде `1566b38` (реальные exe, 2 сервера, 4 бота,
  10 мин): 88 переходов Болота↔Кордон, 0 отказов/ошибок/падений, прибытие в точку
  перехода (Кордон -273,-22,-274; Болота 558,2,-181). Счётчики `leaves/arrivals`
  в сводке занижены: логи серверов не сбрасываются на диск при Stop-Process.

- 2026-10-05 22:00 — билд `1566b38` установлен в gamma-runtime; `a3bf4e0`
  (облачный вход + заморозка заданий) собирается; самотест запущен.

- Продолжение Codex 2026-10-05: `95a4f2c9f` DX11 Actions 37362306316 SUCCESS.
  Новый NPC adapter имеет paired source/target checkpoints + durable mailbox
  ack/tombstone и crash/retry Lua fixtures. Старые destructive-read/partial-loot
  пути убраны. Автоматический transit выключен до H11/global ownership;
  `-netcoop_npc_transit` только для изолированных испытаний. Подробности и
  незакрытые критерии — doc 44, раздел «исправления аварийного перехода».
  Не переносить Lua v2 поверх старых exe: API put изменён, нужны id/ack bindings.

- Новый набор: запрет late source wallet overwrite, fail-closed account save
  (mutex/fsync/rename) и abort player prepare при его ошибке; physical stash
  reach 2 м, combat/wounded/observer guards, настоящий CTime cooldown + legacy
  migration. Lua PASS. Нужен итоговый Actions build; не ставить частичные overlays.
  Foundation 57535cd5c / 37366256415 полностью SUCCESS (GCC/MSVC).

- Backend следующий блок: admin-only offline_contact (continuous bounded 3D
  contact для известной пары), durable encounter schedule, route capture fence
  при world-scale rebase, restart/retry checks. Broad phase / автоматическое
  перепланирование / native ownership adapters всё ещё нужны.
- `8d586d8f9` Foundation 37367127157 SUCCESS GCC/MSVC (включая wallet/account
  fault checks). DX11 37367011993 в очереди, runtime не обновлён. Следующий
  backend-only commit не меняет native/overlay code и не отменяет этот build.

- HTTP fix: ранний POST отказ на Windows мог дать TCP reset вместо JSON error.
  Respond теперь flush/half-close + bounded tail drain; повторные реальные HTTP
  tests и полный локальный backend run: 75 PASS. ab98e1811 backend Windows
  Actions 37368019662 SUCCESS (74 tests, до fix); Linux queued.

- Stash follow-up: own/group motion dependencies captured, stale route/scale
  plans cancelled without moving items or consuming cooldown; restart-only
  fences do not cancel valid plans. Full local backend 80 PASS. Backend
  2802baa3f / 37368996036 SUCCESS Linux+Windows (75 tests). DX11 8d586d8f9
  run 37367011993 attempt 1 failed runner admission, not compilation; attempt 2
  checks SUCCESS and actual engine build running. Runtime still 1566b38 in
  gamma-runtime / 79263abd5 in LostZone-3D-Hideout; no partial overlays installed.

- Codex: backend contact corridor index + admin offline_contacts now selects
  candidates by spatial cells and segment time windows, uses continuous narrow
  phase, excludes group members, reserves pending combat, commits earliest
  disjoint pairs atomically. Overflow fails whole admission (no truncation).
  Full local backend 90 PASS; native/runtime files not changed. Route-change
  subscriber/replanning, large-map windowing/native adoption still pending.
- DX11 8d586d8f9 / 37367011993 attempt 2 SUCCESS, artifact verified present.
  Installation/selftest remains Claude's area; no installer/runtime edits by
  Codex. This package has v2 transit API and wallet/account durability fixes.

- Native fixture follow-up: latest a5702564c DX11 run 37371467639 failed before
  engine compilation, because cluster_move now calls cluster_target_problem
  and the isolated player-transfer fixture had not included that dependency.
  Codex updated its fixture to extract the ACTUAL target availability helper
  and TTL (rather than return a hard-coded success), plus tests for unreadable,
  stale, malformed, full and available target status. Native verification must
  run on Actions; no local compiler used. Runtime installation remains Claude.

- Codex backend Hazards: offline_hazard, captured anomaly/trap state, full
  individual/item/motion captures, equipment condition protection, deterministic
  avoidance, permanent death/same-ID corpse loot, cooldown/one-charge/evidence
  transaction. Group-member trajectories preserve turns and offsets. New
  arrivals priority 10 after contact priority 0; old arrivals not rewritten.
  14 new tests, full local backend 104 PASS. Not adopted by native AI/volumes;
  discovery/replan/emission/shelter/artifact effects still pending. No runtime
  or native engine source edits. gamma-runtime marker now 8d586d8f9 (read-only).

- Codex: quest/locked stash protection at plan+commit, individual catalog/item
  quest markers for automatic take/deposit; shared corpse quest pin query.
  Added byte admission to combat/hazard captures and streamed inventory/member
  limits. Six new tests, full local backend 110 PASS. Native/GAMMA flags still
  need adapter mapping. fc0ef544a Foundation 37372547105 SUCCESS GCC/MSVC;
  DX11 37372547180 queued. f40d63326 backend 37371605344 Windows SUCCESS (90),
  Linux failed runner acquisition (no tests executed); new backend pending.

- Coordination note before edit: Codex is fixing silent player inventory
  truncation in netcoop_characters.inc (character-save/transfer safety), with
  actual native helper coverage in its existing player-transfer fixture.
  Claude's replication/world-store/Lua-scope/runtime changes are left alone.

- Native player snapshot completeness: netcoop_characters.inc now preflights
  all child IDs/parents/inventory types/cycles/depth/count before clearing the
  previous snapshot. Invalid/over-limit capture refuses save, so transfer abort
  preserves source/old file instead of losing some items. Actual helper tests
  included in check-netcoop-player-transfer.py; local syntax only, native Actions
  pending. Foundation now triggers on netcoop_characters.inc as well. Other
  actor's dirty world-store/Lua-scope/overlay files excluded from this commit.

- Codex: death/last-member group events enqueue durable quest failures in the
  death transaction. Consequences run without player polling in atomic batches
  of 64, preserve original evidence across restart/handoff, release corpse pins
  after failure, and never reward/respawn. Shared per-World scheduler handlers;
  bounded legacy recovery via admin quest_reconcile/after_entity/next_after.
  Missing death evidence stays held and cannot block cursor progress.
  Native quest event/UI adoption remains separate.
  Full local backend 117 PASS; native/runtime paths untouched in this change.
- Verification: 6dd10b37b Foundation 37373918198 SUCCESS GCC/MSVC; DX11
  37373918186 checks SUCCESS, engine compiling. b317ac297 backend
  37372725746 SUCCESS Windows+Linux (104). 2a12b6de6 / 37373382669 Windows
  SUCCESS (110), Linux cancelled. Backend-only follow-up will not cancel DX11.
- NPC transit default decision: H11-lite does not prove full old-world state
  migration/unique global population, and mailbox WorldID/cross-host fencing,
  mod-state remapping and real paired-checkpoint failure acceptance remain.
  Keep -netcoop_npc_transit opt-in; no launcher/default changes by Codex.
  Do not count generic foreign-map release as acceptance of automatic transit.

- Codex: offline_hazards location discovery via budgeted 3D corridor queries,
  exact individual member paths/offsets, hazard radius/cooldown/immunity.
  Common combat/hazard reservations now cancel stale captures before their due
  time and atomically replan; journal failure rolls cancellation back too.
  Bounded streaming backlog/state capture, no silent truncation. Ten new tests;
  full local backend 127 PASS. Still explicit passes, not automatic route-change
  subscriber or globally ordered combat/hazard planner; no native adoption.
- Confirmed: 6dd10b37b DX11 37373918186 SUCCESS, Foundation 37373918198 SUCCESS;
  285c569c6 backend 37376503077 SUCCESS Windows+Linux, 117 tests. Installation and
  real exe testing remain Claude's area; Codex did not overwrite runtime.

- Coordination before native edit: Codex is fixing the local-host account
  claim race/stale resumed writer using an OS-held per-account ownership file,
  plus storage front-end cross-location exclusivity and auth-failure release.
  Areas: netcoop_cluster.inc, finish_auth in netcoop.cpp, isolated Actions
  ownership fixture/workflows. Runtime/world-store/replication left alone.

- Native lifetime account ownership now holds an exclusive OS file handle
  through the whole session/save drain. Concurrent/local duplicate claims,
  TTL stealing of a stalled process and non-owner release are refused;
  create/fsync/rename failure releases without admitting. Slot-zero storage
  claims/refreshes/releases account state; rejected character selection releases.
  Actual Windows subprocess/barrier/crash/I/O fixture added to Actions; syntax
  only checked locally. Every cluster process needs the matching new binary;
  old servers ignoring ownership files and cross-host writers are not fenced.

- Verification: 5302a58f4 Foundation 37378444819 SUCCESS GCC/MSVC, actual Windows
  ownership fixture PASS after correcting a strict fixture-only variable
  shadow warning. DX11 37378445074 native checks SUCCESS, engine compiling.
  1d8004572 backend 37377564300 SUCCESS Windows+Linux (127).
- Codex combined offline_plan: one planning instant, globally earliest
  combat/hazard choice, preempts later valid captures when a new earlier trap
  appears; retains prior RNG/EventID at equal time. Atomic cancel+replace,
  bounded admission, no health/ammo mutation during planning. Eight new tests;
  full local backend 135 PASS. Route-change subscriber/native adoption pending.

- Coordination: Codex follows up netcoop_characters.inc with bounded background
  save count/bytes, pending complete-snapshot coalescing, in-flight accounting
  and process-unique temporary names, plus actual helper Actions coverage.
  Will preserve the running 5302a58f4 DX11 build before the next native push.

- Coordination: native disconnect cleanup currently erases/destroys a tracked
  Actor even if its synchronous character save failed. Codex will retain/retry
  that Actor and ownership until the snapshot commits, with actual cleanup
  function coverage in the player-transfer fixture. netcoop.cpp area noted;
  world-store/runtime/replication remain untouched.

- Prepared native follow-up: bounded 256-pending/32-MiB commit queue (in-flight
  bytes included), complete pending snapshot replacement, process/u64 unique
  temp names and rejected/failed temp cleanup. Actual threaded helper and
  Windows fsync/rename fixture added; Actions pending.
  Failed tracked logout save now retains Actor/link/ownership and requeues
  cleanup; success alone releases/removes, corpse/moved/untracked policies
  preserved. Actual cleanup and ninth-leaf ownership tests in transfer fixture.
- Backend geometry work now shares the broad/narrow budget. Full local 136
  PASS; 9f26f5b92 backend 37379314800 SUCCESS Windows+Linux (135).
- 5302a58f4 DX11 37378445074 SUCCESS, full package includes ownership and
  846664a26 world-save fix. Running build completed before this native push.
  Installation/native world-save/restart acceptance remain Claude's area.

- Coordination: Codex will make native progress capture fail closed before
  Actor/inventory mutation in character_save_actor (netcoop.cpp and
  netcoop_characters.inc). Missing/throwing Lua capture and oversized tasks or
  progress currently silently save an old quest snapshot as success. Coverage
  extends the existing Actions player-transfer fixture; runtime unchanged.
- 024fbef42 corrects fixture-only MSVC narrowing in the disconnect test; native
  Actions pending. f4803b1c0 backend 37380934586 SUCCESS Windows+Linux (136).

- 024fbef42 Foundation 37381694426 SUCCESS GCC/MSVC, queue/disconnect tests
  pass. DX11 cancelled by README push 1c7099246; not a compile failure.
  Progress capture now refuses missing/throwing Lua or oversized task/info/
  script/origin data before Actor/inventory mutation; transfer fixture includes
  actual progress function, 512/513 boundary and previous-snapshot retention.
  Python syntax only locally; progress native checks pending on next push.
