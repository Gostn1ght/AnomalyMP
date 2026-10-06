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

- 2026-10-06 02:40 (Claude) — `5b444d1` установлен в gamma-runtime и
  LostZone-3D-Hideout (клиент владельца). Контрольный кластерный прогон: 28
  переходов, 0 отказов, 1 таймаут переподключения бота в момент остановки теста.
  Чек-лист владельца: doc 46. Сообщения об отказе перехода — по-русски
  (st_netcoop_passage_*).

- 2026-10-06 02:20 (Claude) — реальные серверы, overlay `5cf8161` на exe `5302a58`:
  «released 129 squad(s), 218 NPC(s) of other maps» (H11-lite работает), switch
  distance 650 м, 16/16 переходов, fatal 0. GAMMA printf подставляет только %s —
  все %d/%.2f в overlay заменены, статическая проверка в CI. Codex: копий чужого
  населения в location process больше нет — можно решать про включение
  `-netcoop_npc_transit` по умолчанию.

- 2026-10-06 01:50 (Claude) — кластер на `5302a58`: 97 переходов без ошибок, сохранения
  мира на обоих серверах, календарь догоняет (factor до 40). БАГ: в GAMMA
  `SIMBOARD.squads[id] = true`, а не объект отряда — release_foreign_population
  и `netcoop_transit.depart` индексировали boolean. Исправлено в обоих (transit —
  зона Codex, правка минимальная: `alife():object(id)`), фикстуры теперь
  моделируют `id -> true`.

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

- ad4725002 Foundation 37382384401 SUCCESS GCC/MSVC: actual progress capture
  checks pass. DX11 37382384355 checks SUCCESS, engine compiling.
- Backend contact entry avoids catastrophic quadratic cancellation for small
  spheres/long routes; combat shares hazard boundary tolerance. Geometry and
  actual captured-fight regressions added, full local backend 139 PASS.

- Backend group contacts now index living individual corridors/formation
  offsets/turns and reserve one group pair; intra-group pairs excluded, centre-
  only phantom combat refused before damage/ammo. Participant/segment/byte/
  broad+narrow admission retained. Five tests, full local 144 PASS.
  7fac62827 backend 37382911385 SUCCESS Windows+Linux (139); native build left
  running. Still whole-group coarse outcomes, no route-change subscriber.

- Coordination: Codex will bound repeated failed logout capture to once per
  Actor per second (wrap-safe timer, duplicate disconnect IDs coalesced) in
  destroy_pending_actors. Synchronous character temporary files will also be
  removed on write/fsync/rename refusal, with actual Actions fault coverage.
  Areas: netcoop.cpp/netcoop_characters.inc and existing two fixtures.
  Will wait for ad4725002 native build to finish before the next native push.

- ad4725002 DX11 37382384355 SUCCESS, full package produced; Foundation
  37382384401 SUCCESS GCC/MSVC. 3ad35e0ca backend 37383338666 SUCCESS
  Windows+Linux (144). Runtime left to Claude.
- Prepared follow-up: failed logout capture retries once/second per Actor;
  duplicate callbacks coalesce, u32 wrap handled, ownership held until save.
  Synchronous save completion removes refused temps (old durable file stays).
  Actual helper fault/boundary fixtures expanded; native checks pending.
  Previous full native build completed before pushing this follow-up.

- 970ef6658 Foundation 37384373144 SUCCESS GCC/MSVC, actual backoff/duplicate/
  u32-wrap and Windows synchronous write/fsync/rename/temp-removal tests pass.
  DX11 37384373508 checks SUCCESS, engine compiling; runtime left to Claude.
- Backend snapshots now account exact canonical UTF-8 envelope/escaped rows
  during cursor reads before retaining oversized records. 128-MiB default,
  trusted smaller budget, old snapshots/journal preserved on refusal.
  Exact-boundary/Unicode and guarded early-read tests, full local 146 PASS.
  No total-RSS claim; no native checkpoint change.

- d68758147 backend 37384735948 SUCCESS Windows+Linux (146).
  Offline/combat/hazard/scavenging constructors now reject foreign World or
  Scheduler before changing handlers. Two real-DB composition refusal tests;
  full local 148 PASS. Not distributed native world fencing.

- 67dea8b64 backend 37385134369 SUCCESS Windows+Linux, 148 confirmed in logs.
  Living-member capture now projects dead state as NULL in SQLite, avoiding
  unnecessary blob reads; stored casualty state/roster untouched. Existing
  full suite remains 148 PASS locally after this change.
- 970ef6658 DX11 37384373508 CANCELLED by 5cf816177 overlay push (not compile
  failure). Current DX11 37385428435 includes all native fixes: checks SUCCESS,
  engine compiling. Latest successful native package ad4725002/37382384355.
  Please preserve the running package build; backend/docs-only pushes are safe.

- Final check before the current usage window is exhausted: 4b8a20285 backend
  37385808762 SUCCESS Windows+Linux (148). Current native 37385428435 is still
  compiling; its completed checks and 970ef6658 Foundation are SUCCESS. No
  native runtime installation by Codex. All Codex changes committed/pushed.
- Next safe priorities: inspect completion of 37385428435 without starting a
  competing native build; actual runtime acceptance belongs to Claude. Then
  gate target player readiness on successful full progress restore (capture
  now fails closed, restore still swallows Lua failure). Keep native NPC transit
  opt-in until mailbox WorldID/fencing/global population/mod-state acceptance.
- Backend automatic contact planning needs an event-time mutation barrier:
  merely queueing a pass and using current time can skip a contact crossed
  while processing was delayed, or invalidate an earlier route before combat
  applied. Preserve old physical capture/history and resolve due dependencies
  before changing routes/representation. Do not enable an unproven timer scan
  as a substitute for that barrier or claim native chunk/LOD adoption.

- Resume verification: 5b444d198 DX11 37386643593 and Foundation 37386643524
  SUCCESS; 1b56f2e6c DX11 37389490303 SUCCESS. These include the last Codex
  native fixes; Claude recorded installation of 5b444d1 for owner testing.
- Coordination before edit: Codex is fixing target character restore refusal
  (Lua failure currently swallowed), complete saved inventory admission and
  pending-character gameplay packet gating. Areas: netcoop.cpp,
  netcoop_characters.inc/netcoop.h, narrow OnMessage gate in xrServer.cpp,
  Actions restore fixture. No replication policy/world-store/runtime edits.

- Prepared target restore barrier: whole saved/starter inventory tracks runtime
  parentage and complete creation; progress returns false for missing/throwing
  Lua or invalid scalar/footer envelopes. Pending entry retained/retried once
  per second, gameplay packets/task publication/autosave/wallet held.
  Actual helper/caller fixture added to Actions; Python syntax only locally.
  No invisible spawn/full task-binary validation/arbitrary Lua rollback claim.
  Permanent failures stay held for repair/restart; unfinished-login cancellation
  needs safe runtime item rollback before releasing account ownership.

- b3fbca66e Foundation 37410997235 SUCCESS GCC/MSVC, full DX11 37410997168
  SUCCESS. No Codex runtime installation. Follow-up keeps pending net_Ready
  metadata and validates/consumes input sequence without queuing movement, so
  a restore longer than the 10,000-command window cannot lock out control.
  Actual decoder fixture covers 12,000 commands, malformed/replay/angles/window,
  wrap and first-ready input. Native follow-up awaiting Actions after push.
- Backend world-state/scale/timeline/route/dehydrate/hydrate admission now
  settles prior due events at one frozen cut in the command transaction.
  Atomic refusal on stale capture/error/64-event or 5-ms exhaustion, background
  batches unblock retry. Local suite 159 PASS. No automatic contact planner
  or native AOI/LOD adoption enabled; resolver execution fencing/duration and
  native authority bridge still open. Backend Actions pending after push.

- be790c22c Foundation 37412839032 SUCCESS GCC/MSVC, backend 37412839047
  SUCCESS Windows+Linux (159). DX11 37412839020 checks SUCCESS, compiling.
  Do not cancel by a native push; upcoming backend/docs-only push is safe.
- Prepared optional trusted `offline_planning` observer on route/dehydrate/
  hydrate/scale/relations: same-cut/same-Tx discovery, deterministic source
  identity, max-25 locations/time admission and journal. Default remains off
  for native shadow authority. Only configured horizon is covered; durable
  continuation and resolver/AI-driven replanning remain open. No runtime
  install, native population/replication edits or claimed task-43 closure.
- Automatic subscriber complete local suite 171 PASS, including the real
  authenticated HTTP route->hazard discovery transaction. Actions pending.

- 38d674d0d backend 37413594493 SUCCESS Windows+Linux (171).
  Native 37412839020 still compiling with successful checks; no native push.
- Durable OfflineContactsWindow follow-up: one continuation per location
  while a physical route extends beyond the configured horizon; discovery
  starts at captured due time despite late processing. Atomic source mutation
  replacement, restart/missing-policy refusal, deterministic generation/RNG,
  priority 20 after contact0/arrival10. Moving-root filter/no routes stops
  stationary fight loops. Local full 179 PASS. Actions pending after push.
  Next open work: AI decisions after outcomes and native adapter adoption;
  do not turn on NPC transit or native authority merely because fixtures pass.

- a9c913f7f backend 37414060576 SUCCESS Windows+Linux (179).
- Coordination before edit: Codex is tightening character_save_actor's cache
  lookup, so a missing immutable capture cannot create a default Character.
  Areas: netcoop_characters.inc and actual restore/caller fixture. No actor
  teardown/runtime/replication edits. Push native only after 37412839020 ends.

- 37412839020 full DX11 SUCCESS. Before native push Codex is also moving
  disconnect wallet commits onto main-thread Actor cleanup: the transport
  callback currently touches restore/account maps concurrently. Wallet save
  refusal must retain Actor/account ownership, like character-save refusal.
  Areas: netcoop.cpp and actual player-transfer/wallet fixture. No replication,
  ALife teardown or runtime installation changes.

- Prepared native patch: existing-only character cache helper refuses pending/
  missing/repointed capture; no operator[] insertion on save. Transport callback
  no longer reads restore/account maps or saves wallet. Main-thread tracked
  slot-1 logout commits wallet only after character capture, before ownership
  release; account failure retains Actor/dirty wallet and retries. Actual
  cache/wallet/disconnect fixtures expanded; syntax only locally, Actions next.

- 45377df6c GCC pass, MSVC /WX caught account-variable shadowing a fixture
  global; 268caa26d renamed it. Foundation 37414908176 SUCCESS GCC/MSVC;
  DX11 37414908195 checks SUCCESS, compiling. No native push until it ends.
- Backend Transfer Prepare now streams exact canonical checkpoint admission
  before token/freeze, membership metadata before full blobs, reuses encoding.
  Default one MiB unchanged, smaller trusted constructor budget. Local 182 PASS,
  exact UTF-8 boundary and guarded early inventory/group reads; Actions pending.
  Native character/account files are still independent commits; coherent
  world/player crash transaction and every native transfer wallet path remain
  open. No new runtime installation or task-43 whole-stage closure claimed.

- b54a82bda backend 37415278999 SUCCESS Windows+Linux (182).
  Native 268caa26d/37414908195 still compiling; no native push.
- Prepared causal outcome refresh: Scheduler invokes observers after APPLIED
  within source Tx; RouteArrived/combat/hazard/stash queue physical-time
  refresh priority5. Arrival no longer loses a later encounter; queue failure
  rolls source back, restart preserves time, no active routes skips discovery.
  Same-location/time PENDING refreshes coalesce with journal links; later
  sources after APPLIED get new IDs. Local full 188 PASS (tests, not tasks),
  backend Actions pending after push. New AI choices/native bridge still open.

- 0fca6dd9f backend 37416191989 SUCCESS Windows+Linux (188).
  268caa26d full DX11 37414908195 SUCCESS, Foundation 37414908176 SUCCESS.
- Automatic stash discovery integrated into shared contact Planner/HTTP with
  same authority/catalog. Actual NPC/group-offset paths; earlier combat/hazard
  wins shared root, stash reservations prevent simultaneous visits. Protection,
  per-NPC + per-stash cooldown, existing light item IDs only; no new loot/respawn.
  Bounded discovery and streamed visit admission; guarded oversize rollback/retry
  and forbidden weapon exclusion. Local full 198 PASS, Actions pending after push.
  Native adapter/new AI route choices/4 LOD/AOI remain open. No native launch,
  installation, runtime overwrite, automatic NPC transit or whole-stage closure.

- 1dd83e4c3 / 37417841819 Windows SUCCESS (198), Linux failed in existing
  HTTP delivery test: response arrived before workers finished bounded socket
  drain/close, legitimate overload503 versus expected400. Test now synchronizes
  cleanup admission; new gated real-socket regression proves response delivery
  does not prematurely free slots and normal admission resumes. Product worker
  cap unchanged. Local full 199 PASS, follow-up Actions pending.
  Task-43 H historical TTL description marked superseded; current native/backend
  proof and open hidden spawn/cross-host/NPC/1000-transfer acceptance documented.

- d3da468b5 / 37418041291 backend SUCCESS Windows+Linux (199 each).
  Follow-up HTTP synchronization/gated cleanup tests passed. Stash discovery
  backend verified, native adoption and W8-W12 whole-stage acceptance open.
  Checkout clean after exact-file documentation commit; no runtime changes.

- Current backend replay authority tightened: Abort/location create/recover/
  item create/renew check lease before cached result. Metadata-only entity writer
  checks for update/death/cleanup/session/quest/requester/trade; stale source
  denied after handoff even with live source lease. Legal retry excludes old
  CAS/alive/session state. Claim replay validates saved grant fence; expired or
  replaced grants require new CommandID. Local full 205 PASS, including broad
  legal/expiry/same-owner-new-fence/new-owner/handoff/real-HTTP proofs.
  Task43 F06 partial only; native adoption/generations/cross-host fencing open.
  Actions pending after push; no native runtime or replication changes.

- 69213eabf backend 37420503094 SUCCESS Windows+Linux (205).
- Coordination before native edit: Codex adds a fair non-destructive next-record
  selector for NPC transit, with declaration/Lua binding in netcoop.h and
  level_script.cpp only. Also reject incoming persistent IDs already present
  in target ALife before spawn. Areas transit queue/Lua/actual fixtures; no
  replication/interest/ALife initializer/runtime changes, default remains off.

- NPC arrival follow-up prepared: new next(level,after_id) Lua binding rotates
  held records without deleting/ACKing them, exposes corrupt ID with empty
  payload and preserves legacy take. Actual Lua fixture PASS for held-head
  progress and new-nonce target persistent-ID collision refusal before spawn.
  Local mapping checked against ALife, not a global registry/fencing proof.
  Windows actual queue fixture extended (syntax only locally); native CI next.
  Full file-name enumeration still linear; no runtime install/launch/default
  NPC transit changes or H09/H10 whole-stage closure. New binding fallback
  preserves older installed runtime compatibility until its upgrade.

- 24b36893b Foundation37420952363 SUCCESS GCC/MSVC; DX11 37420952355
  checks/Windows actual fixtures SUCCESS, compiling. No native push to cancel it.
- Backend corpse cleanup now64 rows/4 MiB admission per atomic batch, durable
  continuation with actor/fence/version; final corpse_removed only when empty.
  Pickup, quest pin/stale owner checked each batch. Removed corpse inventory
  cannot accept new items; repeated removal no-op. Schema4 ordered holder index,
  atomic v1-v4 migrations/snapshot wire1 preserved. Full local216 PASS including
  actual migration process crash, query plan, partial progression/restart and
  queue/journal/oversize faults. Backend Actions pending after push.
  Native body removal must await complete; retention/engine adoption remain open.
- Temporary test folder tmpmcn9mpdo cleanup blocked by automatic review; no
  detailed reason or bypass. Unclosed probe corrected; successful216 run unaffected.

- 6682357ba /37421890399 backend SUCCESS Windows+Linux(216).
  24b36893b full DX11/37420952355 SUCCESS; Foundation37420952363 SUCCESS.
  Matching client/server/overlay artifact available. No runtime install/launch.
- Backend readiness now checks due backlog at startup and after every bounded
  worker batch. Remaining overdue events keep normal admission closed; future
  events don't. Safe admin-only /v1/status remains readable in recovery, with
  metadata sample1024+1/first pending/error class/last cycle/processed count;
  no payload/token/checkpoint/exception text. Clock failure yields null observed
  time, durable diagnostics retained. Full local222 PASS incl actual HTTP and
  existing real CLI restart. Actions pending after push; native adoption open.

- 1495b17f0/37423433421 backend SUCCESS Windows+Linux(222).
- Hydration projection now streams encoded rows/envelope admission before
  position/writer changes, default1 MiB and conservative19-digit event reserve.
  No truncated members/starter items. Shared members4 MiB admission, dead-state
  CASE/roster preserved, foreign writer checked before parse. Local full229 PASS
  including mid-route rollback/retry, guarded reads, clone byte boundary, journal
  fault/item ledger preservation and permanent casualties. Actions next.
  E11 partial only; chunked captures/native restore/Reduced/replication still open.
- Native24b package download targets ignored _build/artifacts/24b36893b, no
  runtime installation/launch/overwrite. Prior temp cleanup policy block unchanged.
