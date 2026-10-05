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
- С добавлением observer/export config: 65 tests PASS локально и в Actions
  Linux/Windows на `fa9db372a`,
  [run 37344077860](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37344077860).
- Grid/LOD/clock/store/ALife native fixtures PASS GCC/MSVC на `79263abd5`,
  [run 37340572447](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37340572447).
- Full DX11 `230a77b8f` PASS,
  [run 37336051184](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37336051184).
  Первоначальный matching artifact установлен с backup/hash verification;
  затем заменён успешной сборкой `79263abd5`, указанной ниже.
- Full DX11 `0917689f1` остановлен LNK1248 при создании xrGame.lib;
  fixture tests прошли. Изоляция заголовков `79263abd5` проверена,
  [run 37340572528](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37340572528).
  Исправленная полная сборка `79263abd5` завершилась успешно;
  matching artifact установлен: 32 hashes verified, client/server SHA256
  `21C180B9DD4A1CF0DB2C00D09B9B2420156308AA9A7D2DFE1C865C3FCD02D3CC`.
  Backup `build-logs/live-world-backup-20261005-195139` сохранён.
  Неуспешный artifact не установлен. Ограничение COFF описано
  [Microsoft](https://learn.microsoft.com/en-us/cpp/error-messages/tool-errors/linker-tools-error-lnk1248?view=msvc-170).
- Bridge `fa9db372a` выявил две ошибки приёмки: MSVC raw literal внутри
  assert fixture и C1189 (xrCore запрещает exceptions в release engine TU),
  [foundation](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37344077673),
  [DX11](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37344077889).
  Literal вынесен из macro. Parser, WinHTTP, follower и worker перенесены в
  отдельный exception-enabled .cpp без xrCore/PCH; engine вызывает noexcept
  boundary и сохраняет штатные compiler settings. Worker проверяется отдельным
  native fixture, включая authenticated HTTP, identity mismatch и stop/join.
  Повторный Actions run ещё требуется; неуспешный artifact не установлен.

## Сохранение предметов при игровой очистке

Добавлены native adapters для online GE_DESTROY и offline ALife release
мертвых NPC/мутантов: полная проверка children, обычный detach, затем удаление
тела. Существующие IDs/quantity/condition/ammo не пересоздаются; offline
предметы получают position/node/graph тела. Неполный detach оставляет тело
с оставшимися вещами. Actors, живые существа и single-player сохраняют
отдельную старую политику. Native fixture использует настоящий release method
и online adapter block со stub registries; Actions приёмка впереди.

Lua world guard останавливает исключительно age-based release_item_manager
и его уже поставленный timer: оба порядка on_game_load и замена метода
проверены locally через actual Lua. Consumption/quest/pickup paths не
перехватываются. Также закрыты отдельные age purges: floor artefacts в
grok_artefact_despawner.delete_artefacts и persistent NPC inventory в
release_npc_inventory.clean_npc_inv, с сохранением vanilla behaviour вне co-op.
Native age-only NeedToDestroyObject для inventory item,
weapon и dropped grenade также отключены в co-op; armed missile fuse
оставлен в отдельном действующем пути. Для этого добавлен fixture настоящих
methods и fuse scheduler; native checks запускаются только в Actions.
Это ещё не полный аудит всех mod cleanup, не ItemLedger adapter и не
доказательство игрового restart сохранения.

Bridge worker на `5a0a296b4` прошёл actual GCC/MSVC fixture, включая
WinHTTP→backend, foreign seed rejection и bounded stop/join.
[Foundation run](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37347061537)
завершился success на Linux, Windows остановился на Python default text
encoding при чтении corpse source. Чтение sources исправлено на UTF-8;
это не ошибка bridge protocol. Общий native pipeline и полный DX11
ещё должны пройти на итоговом commit.
Повтор `bb92601b0`: Linux PASS; Windows снова прошёл bridge/store, но
corpse fixture остановился на /WX C4244 (template map initializer с int→u16
key). Fixture использует явные u16 keys; production adapter не изменён.

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

## Продолжение 2026-10-05: исправления аварийного перехода

Полный DX11 на `95a4f2c9f` успешно собран в
[GitHub Actions](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37362306316).
Это подтверждает сборку предыдущего состояния; новые изменения ниже проходят
отдельную проверку, в установленную игру ещё не перенесены.

В NPC transit обнаружены реальные нарушения сохранности: target удалял запись
до восстановления; source публиковал её до удаления/сохранения отряда;
отсутствующая секция предмета молча пропускалась. Исправленный адаптер:

- сохраняет retired source и durable outbox в одной паре ALife/Lua snapshots;
- публикует под неизменным случайным 128-bit transfer ID после source checkpoint;
- читает mailbox без удаления; target сохраняет весь приём с inbox receipt до ack;
- ack атомарно переводит запись в tombstone; saved outbox retry не публикует её снова;
- переносит полный поддерживаемый stalker/item STATE и `se_object/game_object`
  Lua state, сохраняя отдельный persistent ID при смене временного native u16 ID;
- отсутствующий предмет/вход, userdata/cyclic/unmapped mod state удерживают передачу;
- заменяет исполняемый `loadstring` на ограниченный data-only parser;
- исправляет squad packet: текущая GAMMA пишет пять строк до save marker,
  старый utils_stpk squad helper понимал четыре.

Локальный actual Lua fixture: source save failure/restart, durable source +
publish failure/restart, target save failure/retry/restart, target commit +
ack failure/restart, missing section/entrance, partial spawn rollback, partial
source release, unsupported mod state, persistent identity/state, malicious
wire/depth/size/duplicate-key rejection. Native Windows mailbox и actual player
cluster_move fault fixtures выполняются только в Actions.

**H09/H10 всё ещё частичны.** Каждый location server пока загружает ALife
registry всей Зоны (H11), а глобальная engine/backend ownership mapping ещё
не подключена. Поэтому автоматический NPC transit по умолчанию выключен;
исправленный адаптер допускается только с явным `-netcoop_npc_transit` в
изолированной проверке. Обычный cluster soak флаг это не включает.
Это предотвращает появление копий начальной foreign population. Также ещё
нужны общий fencing/mutation barrier, remapping произвольных ссылок модов,
наблюдаемый маршрут, permanent-death ownership и проверка на настоящих exe.
Не заявлены cross-host transport, глобальный ItemLedger или приёмка H12.
Mailbox tombstones и inbox receipts сохраняются без TTL; их безопасная
компактификация после согласованного checkpoint ещё впереди.
Старые `.lua/.claimed` записи прежнего адаптера не удаляются/не импортируются
автоматически: нужно установить, были ли их NPC уже восстановлены.

Player handoff больше не продолжает переход при ошибке записи ticket:
ticket готовится до изменения character destination; ошибка character save
отменяет prepare и возвращает source; lease release/redirect идут только
после успешного сохранения. Это не полноценная распределённая 2PC-приёмка.
Watchdog запускает служебные процессы с скрытым окном.
