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

- 2026-10-06 (Claude) — память сервера локации: DX11 грузил все текстуры (2.2 ГБ) на
  dedicated → исправлено в `2f55034`; prefetch моделей держал 2.8 ГБ вершин в shared
  memory → все запуски серверов с `-noprefetch`. Итог: ~3–3.5 ГБ → 1.4–1.9 ГБ рабочей,
  private 5.1 → 2.4 ГБ. Кластер 3 карт (Болота/Кордон/Свалка, `-Maps`): 73 и 53
  перехода ботов без ошибок; release чужого населения 114 отрядов.

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

- bac88d387/37424664770 backend SUCCESS Windows+Linux(229).
- Downloaded native24b artifact verified: built-from commit and2 manifest
  SHA256s match; identical client/server monolithic exe includes new binding;
  transit overlay matches. No separate xrGame.dll; earlier assumption corrected.
  No runtime install/launch or overwrite. Package:_build/artifacts/24b36893b.
- Whole-world ScaleChanged routes now stream into bounded8192-row/8 MiB
  admission before updates; refusal keeps old routes/arrivals/clock/anchor.
  Local full231 PASS with population/guarded-read faults and prior scale tests.
  Actions pending after push; chunked rescale/native authority/4 LOD still open.

- 479914f98/37426282814 backend SUCCESS Windows+Linux(231).
- NPC target arrival now holds mailbox before spawn if any connected player is
  within150m of entrance (inclusive boundary). No receipt/checkpoint/ACK on hold;
  cursor rotation allows other entrances, receipt retries never respawn or wait
  on later player proximity. Actual Lua PASS incl restart, two-player boundary,
  another entrance progress and delayed ACK. DX11 Actions next, no local native
  build/install/launch. Proximity only, not PVS/optics/observed transit animation;
  H10 still open and NPC transit still opt-in pending authoritative adapter.

- Backend location-scoped quest requirement projection: authenticated location
  role/allowlist/current lease,64 metadata rows, frozen-time due consequences,
  existing IDs/current registry location/death/version/writer/quest version.
  Cursor(character,quest,entity)+epoch/revision refuses mixed/stale scans;
  consumer replaces only completed scan, no spawn permission or private state.
  Local full238 PASS incl66-row pagination, migration/frozen writer, death/body
  pin/restart and actual HTTP scope/roles/expiry/query rejection. I03 partial.
  Actions next; native subscriber/delta/busy-world stability/query CPU open.
  21ea79c1c/37427274553 DX11 checks SUCCESS, engine compiling; no runtime action.

- OWNER OVERRIDE 2026-10-06: remove old story/quests and quest-only items; replace
  quest loot in stashes with ordinary consumables. Preserve existing traders.
  Latest amendment: keep a small selected set of former quest NPCs as faction
  mini-traders, with NEW difficult contracts designed from scratch. Old quest
  requirements in43/42 are superseded for legacy story, not justification to
  retain it. Codex edits dedicated sandbox Lua/trade profiles and narrow trade
  hook in server_compat; no replication/interest/runtime install/launch changes.
  General backend quest transaction machinery can support the new contracts;
  old story content/definitions must not be used as new contracts.

- 2026-10-06 13:40 (Claude) — нагрузка «все игроки в одной точке» (Болото, боты =
  настоящие сетевые клиенты-игроки, NPC как во фриплее): 32 — кадр 15 мс, 4 МБ/с;
  64 — 37 мс, 10,7 МБ/с, 2 таймаута рукопожатия; 128 — обвал: все новые персонажи
  спавнились в одну точку (капсулы друг в друге → кадр 0,5–5 с → SteamNet 5003).
  Исправлено: `netcoop_free_spawn_spot` (game_sv_single.cpp) — ближайшая свободная
  точка по кольцам 1,5 м на AI-сетке. Перепроверка 128 после сборки.
  Владелец: игроков НЕ замедлять (никаких 15/10 Гц для дальних игроков) — сделано:
  игроки до 300 м каждый тик, overload/бюджет их не трогают. Неизменённое состояние
  не-игроков не пересылается (пульс 0,5 с). Сервер не рендерит D3D при активном окне.
  Новое: `run-cluster-selftest.ps1 -Spread` (по -Bots на каждую карту, 512 = 4×128 —
  только на целевом ПК 20–30 ядер), `-netcoop_bots_first`, боты повторяют неудачный
  вход до 3 раз; `run-world-crash-test.ps1` + `-netcoop_world_crash=<point>`
  (before_alife/after_alife/pointer_temp/after_pointer) и `-netcoop_world_save_period`.
  Отряды одиночек (`netcoop_squads.script`, вкладка F6 «Отряд»), ЗЗ гп для лидера/
  замов/допущенных. Профайлер памяти `-mem_profile[=bytes]` + `tools/symaddr.py`
  (PDB назван в exe LostZoneDX11.pdb — инструмент делает hardlink).
  ВНИМАНИЕ: «shared strings: memory» в логе — это ЭКОНОМИЯ от общих строк, не расход.
  До загрузки уровня процесс уже 1040 МБ (на старте DLL 226 МБ) — ищем профайлером.

- 2026-10-06 15:30 (Claude) — память сервера: GAMMA ставила звуковой кэш 512 МБ и на
  выделенном сервере → 8 МБ (SoundRender_Core.cpp). Болота: private 2,4 → 1,96 ГБ,
  куча 1,53 → 1,02 ГБ. 128 игроков в одной точке: стеки [hitch]/[hitch-mt] показали
  запись аренд всех игроков в одном кадре (теперь 4 за 250 мс), UI-подсказку костра GAMMA
  на сервере (start_tutorial — no-op на dedicated), Lua-чтения общего хранилища на каждого
  игрока (теперь порциями), перерисовку GDI-консоли (не рисуется свёрнутой, реже),
  и залп «весь мир каждому входящему» → очередь входа: 4 одновременно (xrServer_CL_connect.cpp).
  Краш-тест сохранений мира PASS на реальном сервере (G13).

- 2026-10-06 18:30 (Claude) — профиль главного потока сервера (`-netcoop_sample_profile`,
  `tools/profile-report.py <exe> <log>`), 64 игрока у базы ЧН: ИИ сталкеров 35% (лучи
  зрения 8%, Lua-планировщики GAMMA 8%, память 6%), Lua всего 29%, репликация ~5%, сон ~10%.
  Сделано: бюджет лучей зрения NPC на dedicated (≤30 м — каждый раз, дальше 12 за
  обновление по кругу). Пространственный индекс репликации ускорен (сортированный массив
  ячеек), но по умолчанию выключен: на толпе не быстрее полного перебора; включать
  `-netcoop_chunk_index` для рассредоточенных игроков. Гибернация пустых серверов
  проверена (1424 → 151 МБ), WARP-устройство на сервере проверено. 64 игрока: кадр
  21–26 мс, 0 отказов; 128: 126 играют (на 4-поточном ПК вместе с ботами).

- 2026-10-06 23:30 (Claude) — сервер без игроков: найдено и исправлено, что (1) Lua-мир
  стартовал только с первым игроком; (2) level_weathers.valid_levels пустой на сервере →
  ни выбросов, ни пси-штормов; (3) часы от 0 года во float (шаг ~1,1 ч) ломали расписание
  выброса/погоду — теперь от 2012; (4) укрытия GAMMA не загружались → в конце выброса гибли
  все онлайн-NPC вне surge-смартов; (5) safe_release_manager не работал (actor_on_reinit);
  (6) полная блокировка респавна оставляла карты без мутантов → теперь каждая секция смарта
  заполняется до фриплейного лимита один раз, погибшие не восполняются. Трупы: удаляются с
  лутом при рестарте и после 40 мин без игрока в 100 м (netcoop_corpses), engine-detach
  лута трупа только с -netcoop_corpse_drop. Личный ПДА (PAW без ALife, метки в хранилище
  "pda"), карта клиента показывает метки по объектам/позициям, метки заданий следуют за
  целью (taskpos). Живые тесты: run-world-persistence-test, run-emission-restart-test (PASS),
  run-emission-cover-test, run-world-day-test (сутки мира без игроков).

- 2026-10-07 02:00 (Claude) — ночь, сервер без игроков и нагрузка:
  * Онлайн-смарты на dedicated не обновлялись (биндер не работает) → респаун и логика
    смартов на своей карте не шли, мутантов 0. Теперь `update_online_smarts` раз в 1 с;
    респаун только смартов своей карты и не рядом с игроком. Болота без игроков: 41 NPC,
    31→45 мутантов. Это вскрыло Lua-панику: звуковые темы GAMMA (`sound_theme.script:217`)
    берут `db.actor` → `xr_sound.set_sound_play/play_sound_looped` на сервере без игрока
    идут с якорным актором (id 0), ошибка — в лог, не падение.
  * Профиль 16 ботов: 9% главного потока — `cluster_lease_write` (fsync + WRITE_THROUGH
    на каждый пульс аренды), 7% — таймер GDI-консоли (перерисовка каждые 100 мс в обход
    лимита). Пульсы аренды/часов/статуса теперь без сброса на диск (захват сессии —
    по-прежнему с ним); таймер консоли через `RefreshIfChanged`. Кадр 20–22 → 12 мс
    (вторая правка — в сборке 68274a8e9).
  * Новое: `-netcoop_ai_far/-netcoop_ai_combat/-netcoop_ai_path` (E04), PREWARM
    `-netcoop_prewarm=<с>` (E09, точка «через 4 с» для движущихся игроков в
    `netcoop_nearest_actor_distance`), боевой пин `-netcoop_combat_pin=<м>` (E18:
    NPC в бою с игроком не уходит в офлайн), перцентили кадра `[frames] p50/p95/p99` (M01).
  * Отладочный канал по карте: `netcoop_debug_<map>.lua` (несколько серверов в одном
    runtime съедали общий файл первым).
  * Живые тесты PASS: `run-emission-cluster-test.ps1` (J10: два сервера, рестарт Кордона
    посреди выброса), `run-world-living-test.ps1` (L35: 77/77 живых с теми же id/отрядами/
    235 предметами; болты не сравниваются — движок выдаёт новый при выходе в онлайн),
    `run-world-day-test.ps1` теперь проверяет инварианты (сироты, потерянные члены
    отрядов, дубли story id) и ловит Lua-панику.

- 2026-10-07 04:00 (Claude) — защита A11 и память:
  * `server_remote_event_allowed`: от удалённого клиента отклоняются GE_HIT/
    GE_HIT_STATISTIC/GE_DIE/GE_ASSIGN_KILLER/GE_GAME_EVENT/GE_TELEPORT_OBJECT/
    GE_CHANGE_POS/GE_CHANGE_VISUAL/GE_TRADER_FLAGS/GE_FREEZE_OBJECT/ограничители;
    GE_TRANSFER_AMMO — только если получатель принадлежит отправителю (иначе
    R_ASSERT ронял сервер); GE_DESTROY/GE_INSTALL_UPGRADE/GE_ADDON_* — только вещи
    своего Actor; GE_INFO_TRANSFER — только себе. Честный клиент их не шлёт (пули
    клиента визуальные, урон считает сервер). Если владелец увидит в логе сервера
    `rejected event <тип>` при обычной игре — это легальный путь, который надо
    разрешить точечно.
  * Бот-читер `-netcoop_bots_cheat=<id>` + `run-cheat-test.ps1`: PASS на новом сервере,
    старый (2d878e589) упал на `c_from == c_parent`.
  * Профиль памяти Кордона (`-mem_profile`, блоки ≥4 КБ): конфиги ~180 МБ, CDB ~177 МБ,
    вершины скелетных моделей (_Load_hw) ~50 МБ, анимации ~26 МБ; текстуры 0.
    Кэш DLTX (~80 МБ) сбрасывается через 60 с после уровня на dedicated.
  * Нагрузка на 4-поточном ПК: 64 бота вытесняют сервер с CPU; `-BotsBelowNormal`
    для честного кадра сервера. Плохая сеть: `-BotArgs "-netcoop_fake_loss=5 -netcoop_fake_lag=120"`.
  * Пауза кадра: `Sleep(psNET_DedicatedSleep)` жила в `IGame_Level::OnRender`, которую
    dedicated больше не вызывает (рендер отключён 2026-10-06) → пустой сервер 98% ядра.
    Теперь в `CRenderDevice::on_idle`: кадр короче `-netcoop_frame_ms` (5) досыпает
    остаток, длинный — не спит. Пустые Болота: 30% ядра, p50 6 мс. Во время паузы
    вторичный поток делает шаги Lua GC (`psLua_ParallelGC`, пока `isRendering`).
  * Идея на будущее: скрытый якорный актор (id 0) держит онлайн 450 м вокруг стартовой
    точки даже без игроков (`netcoop_nearest_actor_distance` берёт `graph().actor()`):
    исключить его, когда на карте есть игроки, или совсем — экономия CPU/памяти, но
    проверить мир без игроков заново (выбросы, трупы, респаун).

- 2026-10-07 07:00 (Claude) — итог ночи, установлена 69cf233a1 (gamma-runtime и
  LostZone-3D-Hideout):
  * Суточный прогон PASS: 150 мин, 3 выброса, трупы по правилу 40 мин, инварианты 0,
    ошибок 0, память +31 МБ (Болота ~1,9 ГБ private; после сброса кэша DLTX на 60–90 МБ
    меньше прошлых прогонов).
  * Процессы ботов теперь с паузой кадра 10 мс (~20% ядра каждый). 64 бота: 64/64
    играют, 0 отказов, но сервер 157% ядра, кадр p50 ~110 мс. Профиль: CSheduler 63%,
    CAI_Stalker 33% (Lua биндеры 18%, CActionPlanner 12%), Feel::Vision::o_trace 12%
    (ray_query: каждый NPC трассирует всех игроков ближе 30 м — бюджет лучей нужен и
    внутри 30 м), CBaseMonster 8%. Следующий шаг: бюджет зрения в толпе и частота
    биндеров GAMMA для NPC, которые не в бою.

- 2026-10-07 утро (Claude): владелец — «не делай NPC тупыми ради оптимизации». Бюджет
  лучей зрения больше не касается игроков (O_ACTOR/S_ACTOR трассируются всегда).
  Физпредметы (`CPhysicObject`: двери, бочки, ящики) не реплицировались вовсе
  (`net_Export` пишет 0 в single, а `server_physics_update` брал только предметы и
  трупы) → теперь предмет, сдвинувшийся на сервере (после 30 с оседания уровня),
  отправляется как предметы, спящий — раз в 60 с. `run-prop-test.ps1` PASS, бот
  `-netcoop_bots_watch=<id>`. Сборка c38376323 установлена; 16 ботов: p50 8–9 мс.

- 2026-10-07 (Codex) — owner requests continuing lossless optimizations and
  adapting IX-Ray scheduler. Coordination before edit: xrEngine/xrSheduler*,
  ISheduled initialization, actual scheduler CI fixture/workflows and docs.
  No replication/interest/runtime install/launch changes. Pinned IX-Ray stable
  612b165c97d5e6a50ac0a6d1384ac8c95a63dda5 and develop
  c55dacab6165c0f28fd09479043fcd89a9625357: same queue/interval/budget algorithm
  already present; no claimed magic threading/crowd speedup from replacing it.
  Adapt profiling/tolerant unregister and improve registration/lifetime safety,
  retaining existing update intervals and full player/NPC work. Live64+ result
  required before marking performance acceptance complete. Existing untracked
  backend/tests/test_transfer_stress.py is preserved and not part of this edit.

- 2026-10-07 (Codex) — separate backend handoff validation: finish the previously
  untracked test_transfer_stress.py in its own commit; local Python run PASS
  (1000 player/group commits, 250 aborts, transactional fault injection and
  eight actual process exits before/after each phase). Existing backend workflow
  discovers it on Linux/Windows. See 51_TRANSFER_STRESS.md; H12 stays partial
  until native source/target crash and hidden-spawn acceptance. No runtime edit.

- 2026-10-07 (Codex) — IX-Ray scheduler fixtures PASS: World Foundation
  37578376041, GCC+ASan/UBSan and MSVC, release/DEBUG, exact 32825 callback trace
  against pinned IX-Ray, register-pair/lifetime/address-reuse tests. Native code
  last changed at 9cbec96e8; DX11 run 37578375978 (87cbb2133) is building.
  World Backend 37578376035 PASS 240 tests on both OS, including 1000 handoffs
  and eight process crashes. Do not label the 64-player frame acceptance done.
  Current backend cleanup policy corrected to DESTROYED leftover corpse loot
  per latest owner rule; independent ground/player items preserved. 241 Python
  tests local PASS; see 52_CORPSE_LOOT_POLICY.md, backend CI pending.

- 2026-10-07 (Codex) — final scheduler native source c64e88fbc: RT cancellation
  now marks dirty and compacts once after a batch; unchanged frames skip this
  scan. Actual fixture adds 2048 RT removals. World Foundation 37579014305 PASS
  on both OS/release/DEBUG, including exact IX-Ray trace and sanitizer checks.
  DX11 37579014309 is building; avoid native pushes until its result is known.
  Corpse backend policy 055aa98e7: World Backend 37578839647 PASS 241 tests on
  both OS. Runtime installation/live64 remains separate; original audit counts
  stay unchanged. Doc49 marks its historical 1–5 Hz Reduced AI proposal as
  superseded by owner's no-AI-degradation instruction.

- 2026-10-07 (Codex) — completed source/CI/package scheduler iteration. Latest
  native source 3a95c0dce includes xrCore/profiler.h explicitly (the full build,
  rather than the previous PCH stub, exposed that missing dependency). Fixture
  now imports the real profiler header. World Foundation 37580073705 PASS all
  Linux/Windows release/DEBUG + sanitizers; DX11 37580073704 SUCCESS including
  package/upload. Artifact 11464314210 downloaded to
  _build/gha/scheduler-3a95c0dce; built-from and both exe hashes validated;
  IX-Ray notice matches source. Exe SHA256
  D41B3D55DE56BB62F3DBF6F30F46A4976A04985F88EE7251E43C65E9D6A8EEC5.
  No runtime installation or native launch: keep live64 p50/p95/AI population
  acceptance open. Current backend 241 tests PASS remains 37578839647.
  Next lossless work: profile pure reads first; actor binding functor/depth are
  already cached, and CPropertyStorage's public mutable vector prevents naive
  lookup caching. No added live checkmarks in the 188-point audit.

- 2026-10-07 (Codex) — coordination before direct-ticket hot-loop edit: xrEngine/xrSheduler*, new scheduler ticket helper, actual scheduler CI fixture/project/workflow and documentation. Preserve callback frequency/order/intervals/budget and NPC quantity. Owner explicitly requires smooth, responsive NPCs throughout maximum visibility; distant-NPC live acceptance remains mandatory. No replication, runtime installation or native launch edits. Pinned hash-check baseline is native 3a95c0dce.

- 2026-10-07 (Codex) — owner clarification: no visible frozen/jittery NPCs at maximum visibility. Coordination before foreign-region fix: xrServer.cpp AOI cadence and netcoop_replication_index cpp/h + actual predicate fixture. Existing NPC 1/2/4/16 tiers multiplied by overload conflict with this requirement. Protect creature roots (NPCs/mutants/actors and held objects) every tick at all distances, independent of budget/overload; index must include them globally. Also bypass lossy unchanged hash filtering for these live states. No AI callbacks/population reduction, no runtime install/launch. Native DX11 37584887087 will be superseded by the combined build for this owner-requested fix; Foundation 37584887106 already PASS direct tickets.

- 2026-10-07 (Codex) — combined code d54030213: Foundation 37585364939 PASS on Linux/Windows (actual scheduler/reference/lifetime/ticket checks + actual AOI predicate/index full-rate differential). DX11 37585365023 is building. Windows overhead 64RT/128normal benchmark reduction varied 14.4–26.2% between CI runners (1.85–3.40 us per synthetic frame), NOT a gameplay FPS claim. All creatures/actors and their inventory-root states bypass distance/overload/byte-budget/hash suppression; traffic increases, measure it with live64. Bots do not render NPCs; watch flag tracks physics, so maximum-view smoothness requires a real graphical client. Docs53/54 record proof/limits, doc48 adds a historical-snapshot clarification without new live checkmarks. No running game processes observed; no runtime install/launch.

- 2026-10-07 (Codex) — FINAL combined scheduler/creature replication source
  d54030213cfbf950b5103ab0c275423242ed87a1: Foundation 37585364939 PASS both OS;
  DX11 37585365023 SUCCESS checks/full engine/package/upload. Artifact
  11466733728 (189509686 bytes) downloaded to _build/gha/scheduler-d54030213.
  built-from, both exe manifest hashes and IX-Ray notice validated. Exe SHA256
  36BA115085198F7B5BAF08E384AB306B2174FB19CA861EBFF6187498DCD57395.
  No runtime install/launch. Keep real 16/64 load, traffic/send queue, distant
  NPC movement/reactions and graphical client acceptance OPEN. Full-rate applies
  after existing Net_Relevant/handshake/transport eligibility; do not claim a
  delivery or AI/frame-time guarantee from a passing synthetic fixture. Actual
  benchmarks measured scheduler overhead only, not the 110 ms game frame.
  Current repository code/CI/package substeps complete; 188 live audit counts
  unchanged. Next native runtime testing remains the recorded installation lane.
