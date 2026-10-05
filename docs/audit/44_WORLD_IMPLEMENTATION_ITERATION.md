# 44. Исполняемая основа мира и границы подключения

Итерация 2026-10-05 после исходной сверки 43. Это продолжение полного
ТЗ, не объявление закрытых W1–W12 и не оценка готовности в процентах.

## Реализовано и проверено отдельно от игрового адаптера

В `backend/lostzone` исполняемый service process, HTTP loopback endpoint,
server credentials и bounded worker pool. Role/location allowlists,
payload contract, request budgets и fail-closed readiness исключают
назначение principal через body. Remote TLS/mTLS и Firebase session→
Player Gateway binding ещё не подключены.

SQLite WAL/FULL с OS process lock: WorldID/seed/epoch, local location
leases/fences, registry, один ItemLedger, transactions, command results,
inbox/outbox, aggregate sequence, snapshot checksum/watermark. Schema
v1→v2→v3 мигрируется без нового мира. Fault tests убивают отдельный backend
процесс до/после commit и проверяют повтор команды после потерянного ACK.
Это не coherent ALife/Lua/player/backend snapshot или journal replay.

Backend handoff реализует prepare/claim/commit/abort/status, target
reservation, signed token и recovery claim под текущим destination fence.
Claimed transfer не возвращается source из-за expiry. NPC/group IDs и
состояния прежние; трупы остаются на месте смерти. Переход одного живого
участника в обход persistent group отвергается. Нужны engine freeze,
hidden target placement/replication ACK, retirement source и client UI.

Quests с committed event objectives, unique entity links, CAS, atomic
progress/reward и защитой нужных тел. Permanent death не требует respawn
quest NPC. Это простые server definitions, не перенос всех GAMMA quests.

WorldState/bootstrap, weather/emission timelines, ordered bounded
scheduler, late-event occurred time и commit highwater. Поздний клиент
может вычислить текущую фазу. Реальные shelter/damage/anomaly effects и
engine environment playback ещё впереди.

Offline capture/hydration fence и analytic polyline travel: живой состав,
индивидуальное состояние, formation offsets, world-time/real-speed rebase,
одна актуальная arrival, freeze downtime. Location recovery не забирает
offline writer. Static stashes/doors/traps могут сохранять abstract capture,
но не получают actor route. Engine готовность не выводится из backend ACK.

Atomic whole-stack buy/sell: trusted catalog/preferences, price/condition,
quantity, оба wallets, ItemLedger и result одним commit. Funds/capacity/
carry weight/CAS/accepted price checked. Нет reroll trader stock. Engine
trade UI и partial-stack split ещё не используют этот сервис.

Rare NPC stash visits: offline ownership обеих сторон, protection,
current route position, capacity, deterministic choice и persistent
cooldown. Только перенос существующих вещей; deposits FOOD/MEDICINE/
AMMO/JUNK/TOOL, без оружия/брони/артефактов. Hydration до resolve отменяет
offline visit. Automatic route/target selection ещё не подключён.

Coarse combat: immutable individual/weapon capture и deterministic seed,
committed hostility, actual meeting position, bounded resolution,
individual health/injuries, ledger magazine rounds, persistent deaths,
corpse loot и evidence одной transaction. Restart/observer не меняют RNG.
Hydration/diplomacy/capture change отменяют abstract fight. Все погибшие
members остаются в roster; пустой погибший group не продолжает маршрут.
Это baseline model, не calibrated GAMMA combat или engine evidence playback.

## Native spatial и LOD

`netcoop_spatial_grid.h`: configurable cells, negative boundaries,
128-bit key, location scope, upsert/move/erase, 3D sphere/capsule, bounded
query. Индекс сравнен с brute reference на 20k synthetic records/256 queries.
Это не load-test на 128/512 игроков.

`netcoop_simulation_lod.h`: Full/Reduced/Abstract/Dormant demand policy,
union observers, cell bounds, conservative high-speed prewarm,
minimum dwell/exit delay, budget и immediate escalation. RepresentationGate
проверяет capture revision/generation, полный restore, ownership ACK,
safe placement и Reduced AI до replication. Stale callbacks и неоднозначный
dehydration ACK не возвращают старому runtime право изменения.

`xrServer::SendUpdatesAOI` с `-netcoop_chunk_shadow` сравнивает sphere set
и считает cell LOD demand. Пока не фильтрует packets и не переключает AI,
physics, spawn/ownership. Runtime u16 handles не выдаются за persistent IDs.
Template-heavy диагностические типы скрыты в одном .cpp; общему xrServer
header не требуется включать полное ядро grid/LOD.

## Доказательства и установленная сборка

- Backend на `c62d6db6b`: 55 tests PASS локально и в Actions Linux/Windows,
  [run 37340861592](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37340861592).
- Coarse combat на `e77b86250`: 63 tests PASS локально и в Actions
  Linux/Windows, [run 37342225793](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37342225793).
- С добавлением observer/export config: 65 tests PASS локально;
  native transport и соответствующая Actions проверка запускаются отдельно.
- Grid/LOD/clock/store/ALife native fixtures PASS GCC/MSVC на `79263abd5`,
  [run 37340572447](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37340572447).
- Full DX11 `230a77b8f` PASS,
  [run 37336051184](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37336051184).
  Matching artifact установлен в LostZone-3D-Hideout: 32 hashes verified,
  client/server SHA256 `1D55C3A353E7AC31AE51E9A2ED071E2FF45A99EB2E3545D358ABF88622EA8582`.
  Backup `build-logs/live-world-backup-20261005-191406` сохранён.
- Full DX11 `0917689f1` остановлен LNK1248 при создании xrGame.lib;
  fixture tests прошли. Изоляция заголовков `79263abd5` пересобирается,
  [run 37340572528](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37340572528).
  Исправленная полная сборка `79263abd5` завершилась успешно;
  соответствующий matching artifact устанавливается с backup/hash verification.
  Неуспешный artifact не установлен. Ограничение COFF описано
  [Microsoft](https://learn.microsoft.com/en-us/cpp/error-messages/tool-errors/linker-tools-error-lnk1248?view=msvc-170).

Игра автоматически не запускалась: ранее launch был blocked by policy;
запрет не обойдён. Нет live gameplay приёмки, данных p99/FPS/traffic,
25 игровых локаций или доказанной capacity. Backend не назначен вторым
владельцем существующего ALife мира и не запущен с новой независимой DB.

## Следующие обязательные подключения

1. Read-only bridge/identity comparison добавлен: приватный observer credential,
   bounded WinHTTP worker /v1/bootstrap, wire parser, WorldID/seed/epoch checks,
   LocationClock и лог сравнения ALife clock без изменения authority. Реальный
   native HTTP fixture проверяется в Actions Windows; remote clock/ownership
   adoption и coherent migration существующего мира ещё впереди.
2. Persistent mapping/ownership barrier в ALife и ItemLedger adapter;
   достаточная полнота captures и durable engine/backend capture barrier.
3. Location-scoped bootstrap, полноценные переходы с hidden target,
   safe destination/AOI admission и reconnect/error client states.
4. Reduced AI, bounded hydration/dehydration queue, optics/PVS interests,
   baseline/generation handshake и реальная indexed replication.
5. Offline encounter detection, anomaly/trap/shelter/emission effects,
   ecology без population regrowth, trade/supply routes и evidence playback.
6. Настоящие restart/crash/transfer/AOI churn и многопользовательские тесты;
   измерения нагрузки вместо переноса цифр из microbenchmark.
