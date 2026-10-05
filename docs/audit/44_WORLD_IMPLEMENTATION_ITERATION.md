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

Следующее исправление: source disconnect/periodic `store_money` не пишет
кошелёк уходящего/redirected игрока; начальный wallet capture выполняется до
freeze. Account save теперь возвращает результат: lock timeout/CreateMutex
failure не дают писать без блокировки, fsync/close/rename failure сохраняют
старый файл и dirty state. Переход отменяет prepare ticket до character save,
если wallet commit не прошёл. Actual player fixture проверяет поздний source
save после изменения target wallet; Windows account fixture инъецирует
lock/fsync/rename failures. Полного lease fencing при параллельном входе
между процессами это не закрывает.

Stash adapter: взаимодействие с NPC на расстоянии до 2 м вместо 60 м;
проверяется наблюдение и за NPC, и за ящиком, бой/ранение запрещают посещение.
Календарь cooldown использует CTime diffSec; legacy 31-day timestamps
мигрируют с консервативной 6-часовой паузой, прежняя история сохраняется.
Actual Lua fixture этих случаев проходит. Путь NPC к специально выбранному
тайнику, async item-transfer acknowledgment и глобальный ledger ещё нужны.

На `57535cd5c` весь Foundation (GCC + MSVC, включая actual mailbox/player
fixtures) SUCCESS: Actions 37366256415. Первый `887fe7277` DX11 остановился
на deprecated strcpy в новом player fixture; замена на bounded snprintf
проверена Foundation. Полный DX11 `57535cd5c` оставался в очереди до следующего
набора исправлений; этот запуск не используется как свидетельство сборки.

## Контакты офлайн-маршрутов (следующий backend блок)

`offline_contact` — admin-only narrow phase для известной пары кандидатов:
непрерывные piecewise-linear 3D trajectories, первое вхождение в radius,
повороты/неподвижная сторона/высота. Вычисление линейно по суммарным сегментам
двух маршрутов (до 1024 на сторону), без per-NPC polling. План combat,
полные participant captures, route version/active и command result сохраняются
одной транзакцией. Нет встречи — нет scheduled combat/ammo/death.

World-scale rebase ранее менял route version без entity version: прежний бой
мог пройти по устаревшему due time, если персонажи всё ещё были близко.
Теперь resolver отменяет его по route capture прежде любых изменений;
legacy events без route capture тоже fail closed. Restart/refence без
семантической смены маршрута план не изменяет.

Проверки: непрерывное пересечение с далёкими endpoints, поворот, неподвижная
цель, высотное/параллельное разделение, начальное сближение, bounded/finite
inputs, transactional contact scheduling/retry, miss без патронов, scale
rebase cancel, движущийся clock в immediate contact и restart до встречи.
Предыдущие 65 backend checks также проходят. Spatial broad phase discovery,
автоматическое перепланирование после смены маршрута и engine presentation
не подключены: J/offline AI блок не объявляется законченным.

Native Foundation на `8d586d8f9` / Actions 37367127157 SUCCESS GCC/MSVC:
actual mailbox, player handoff с late wallet, account lock/fsync/rename faults,
остальные clock/store/bridge/corpse/items/spatial/replication fixtures. Полный
DX11 Actions 37367011993 пока в очереди; установленных новых exe нет.

Общий Windows run после contact блока один раз выявил реальную транспортную
ошибку: при раннем отказе POST (неверный Content-Type) незачитанное тело
вызывало TCP reset/WinError 10053 вместо JSON 400. Исправлен response shutdown:
сначала flush + SHUT_WR, затем bounded incoming tail drain (64 KiB, короткий
socket timeout/deadline), без ожидания произвольного Content-Length.
Повторные unauthorized/MIME/oversize POST checks и полный локальный backend
run **75 tests PASS**. Это не retry в тесте и не подавление ошибки клиента.
На ab98e1811 Actions 37368019662 Windows (74 tests до этого fix) SUCCESS;
Linux ещё в очереди. Новый backend-only commit требует Actions обоих ОС.

- Stash motion capture: member NPC depended on a group route without changing
  its own version; world-scale rebase also changes route version only. Visits
  now capture own route and (where applicable) group ID/version/route, validate
  current offline group authority, and cancel stale/legacy plans before any
  item/cooldown mutation. Restart-only fences are excluded from semantic input.
  Five new tests: group route replacement, solo/group scale rebase while still
  inside reach, group visit across restart (same item once), legacy cancellation.
  Local full backend: 80 PASS. Backend 2802baa3f Actions 37368996036 SUCCESS
  on Linux/Windows (75 tests before this change). DX11 8d586d8f9 retry acquired
  runner; checks SUCCESS, engine compiling. No workflow migration was needed.

## Contact corridor broad phase (backend-only)

ContactIndex uses location-scoped 3D cells, floor coordinates (including
negative boundaries), per-segment AABBs and overlapping time windows. Query
padding accounts for contact radius; exact continuous narrow phase decides
whether/when paths meet. Atomic upsert/erase preserve the old entry if a
replacement violates limits. No entity/segment/pair/work overflow is truncated.

Admin-only offline_contacts snapshots up to 256 offline roots on one map,
excludes persistent group members and roots reserved by pending combat,
sorts contacts by time/IDs, schedules earliest disjoint pairs in one DB
transaction (max 64), and reports deferred overlapping contacts. Retry and
restart preserve scheduled IDs/captures; second-plan journal failure rolls
back the entire batch. This command has no production engine authority.

Five index tests compare candidates to brute-force continuous geometry,
negative cells/map/height/time/radius separation, move/remove and rejected
replacement, dense work/pair overflow, reference/segment/entity admission.
Five batch tests cover crossing+restart+retry reservations, group-only roots,
sparse/neutral misses, second-plan rollback and actor limit. HTTP role checks
cover the new operation. Full local backend **90 tests PASS**.

Bounds: 8192 segments, 131072 references, 4096 cells per segment/query,
200000 work checks, 4096 pairs. Incremental index API exists, but admin
adapter rebuilds from a bounded snapshot on each explicit planning command.
Automatic route-change subscriptions/replanning, large-map windowing, native
AI handover and real load acceptance remain. C/K are not marked wholly done.

DX11 **8d586d8f9 / 37367011993 attempt 2 SUCCESS**, including checks+engine;
matching client/server artifact available (187445389 compressed bytes).
Foundation same commit SUCCESS; runtime installation/selftests belong to the
other active actor per doc 45 coordination; do not mix v2 Lua into old exe.

## Offline persistent hazard contact (backend-only)

Admin offline_hazard captures and schedules continuous route contact with one
persistent ANOMALY/TRAP; no per-NPC collision tick. Individual group trajectories
now retain the group polyline's turns and each member's offset. Hazard type,
radius/intensity/damage, cooldown, active/armed/charges, owner and safe factions
come from trusted state. Inventory captures include IDs/versions/state; trusted
ARMOR/ARTIFACT protection considers equipped flag and condition, not possession
alone. Deterministic bounded experience/knowledge avoidance is a baseline
policy, not a claimed GAMMA resistance model.

One transaction saves actual member positions, injuries/permanent deaths,
unchanged loot IDs moved to corpse, last-member group death, stopped route,
hazard cooldown/one trap charge and evidence. Hydration, route-scale change,
item or hazard revision cancels before mutation. Failure of evidence write
rolls all of these back. Restart preserves captured outcomes. Two contacts
cannot spend one charge twice. New RouteArrived priority 10 settles after
physical contact (priority 0) at the endpoint; old persisted arrival priority
is not rewritten (conservative cancellation possible).

14 meaningful tests cover trap death+restart/retry/inventory, equipped/unequipped
and damaged protection, hydration, scale, item mutation, owner/faction/height/
cooldown misses, journal rollback, deterministic anomaly clone/restart, offset
member through route turn and last-member death, invalid policy, endpoint
priority, competing contacts. HTTP role checks include operation. Full local
backend **104 tests PASS**. Automatic hazard discovery, retreat/path decisions,
real game volumes/hydration, emission/shelter/artifact effects remain; L is not
marked complete. Native compilation is still exclusively GitHub Actions.

## Quest stash protection and capture byte admission

Locked entity state and active quest requirements now protect otherwise
NPC-accessible stashes, both at planning and commit. Granting a quest after
planning cancels that visit without consuming cooldown or moving loot. A shared
Ownership.quest_required query also retains existing corpse protection. Trusted
catalog quest_protected bool and item quest_item/quest_protected flags exclude
individual items from BOTH automatic take/deposit; player access is unchanged.
Four tests cover lock before/after planning, late quest pin and completed pin
release, both movement directions/markers, and invalid catalog policy.

Combat/hazard member queries stop at 65 records (root plus up to 64 fighters),
inventory is streamed with the same 64-item boundary, and CaptureBudget stops
encoded state accumulation at 1 MiB with metadata reserve before parsing the
remaining states. Existing final canonical event limit remains. Two actual
resolver tests reject multiple individually valid large item states without
scheduling damage/charge/ledger changes. Full local backend **110 tests PASS**.
No native adapter adoption or whole C/K/L completion is claimed.

fc0ef544a Foundation Actions 37372547105 **SUCCESS GCC/MSVC**, including the
actual target availability helper and failure cases in the repaired transfer
fixture. DX11 37372547180 queued. f40d63326 backend Actions 37371605344 Windows
**SUCCESS (90 tests)**; Linux cancelled by external runner admission failure:
"The job was not acquired by Runner of type hosted even after multiple attempts".
Not a code/test failure; newer backend jobs cover the follow-up changes.

## Player inventory checkpoint completeness (native, verification pending)

character_capture_items previously continued past missing children/count 512,
and returned at depth >8, then character_save_actor persisted the truncated
inventory. New character_inventory_complete validates the entire registered
inventory tree before any money/state update or previous items.clear:
registered matching child ID, exact parent, inventory type, no invalid/repeated
ID/cycle, at most 512 items and the same capture depth boundary. On failure the
save returns false; existing transfer abort path cancels prepare and unfreezes
source, preserving the previous on-disk character snapshot.

Actual helper is extracted into the existing player-transfer C++ fixture with
valid empty/ordinary/boundary cases and missing/foreign-ID/wrong-parent/non-item,
invalid-ID, duplicate/cycle, count/depth overflow. Wiring order is checked before
clearing inventory. Foundation workflow now includes character source changes.
Only Python fixture syntax checked locally; native compilation/execution remains
GitHub Actions. This fixes silent capture truncation, not the separate native
session lease race, file-worker queue/fencing or distributed ledger adoption.

## Durable quest death subscriber and bounded compatibility recovery

EntityDied and GroupLostAllMembers now enqueue QuestDeathConsequences in the
same transaction as the permanent death/loot changes, when an active quest
requires that entity alive. The scheduler fails at most 64 linked quests per
atomic batch, journals the original death ID/time, and durably queues the next
batch. A quest failure does not require a player poll, location ownership or
an unfrozen character; it survives a player's prepared/committed handoff.
No reward, wallet write or replacement NPC is created. Corpse pins remain
until all active requirements are resolved; alive_required=false objectives
still retain their corpse. A failed journal write rolls back the batch, while
the previously committed death remains available for retry.

Schedulers constructed on the same World share registered handlers. A new
World after restart creates fresh handlers; a scheduler from another World is
refused. Startup examines up to 64 legacy dead quest targets. The admin-only
quest_reconcile operation has an optional after_entity cursor and returns
next_after to continue the bounded scan; unproven deaths are held and reported,
so even 64 missing journal records cannot starve later proven deaths. This is
explicit maintenance for old records, not an unbounded startup sweep.

Seven new tests cover automatic consequences during handoff, restart with old
death evidence, 65-quest fanout, journal rollback/retry, last-member group death,
foreign scheduler rejection, and cursor recovery past incomplete old records.
HTTP role checks include the new maintenance operation. Native quest/UI event
adoption and quest configuration migration remain pending; this is backend
functionality, not completion of all I requirements.
Full local backend suite: **117 tests PASS**.

Verification update: 6dd10b37b Foundation 37373918198 SUCCESS GCC/MSVC, including
the actual player inventory completeness helper. Its DX11 run 37373918186 is
still compiling; installed runtime is not claimed to contain that fix.
b317ac297 backend 37372725746 SUCCESS Windows+Linux (104 tests). 2a12b6de6
backend 37373382669 Windows SUCCESS (110); Linux cancelled, requiring a newer
successful Linux run before its follow-ups are accepted there.

## Native NPC transit default remains opt-in

H11-lite release_foreign_population does not by itself establish a unique
global NPC registry or safe existing-world migration. It partitions generic
initial squads once; old saves without netcoop_foreign_released also take that
path, while story/companion/scripted entities are retained. It cannot prove
that a valuable foreign-map state has been preserved in another authority.
The mailbox also lacks a shared WorldID envelope and cross-host writer fencing,
and full mod/Lua state remapping plus native checkpoint failure acceptance is
unfinished. Therefore -netcoop_npc_transit remains an explicit opt-in; normal
launchers remain unchanged. Automatic activation must follow ownership,
complete-state and migration acceptance, rather than the partition helper.

## Location hazard discovery and stale contact reservations

Admin offline_hazards now discovers physical contacts through read-only 3D
corridor queries against persistent active hazards. It checks each actual
group member path/offset/turn and each hazard radius, cooldown, owner and safe
factions; it does not infer danger from sharing a chunk. Queries share one
200000-work budget across the whole pass. At most 256 roots, 256 hazards,
256 living participants, 8192 route segments, 4096 eligible candidates and
64 disjoint contacts are admitted. No silent population/candidate truncation.

Combat and hazard planning share bounded pending reservations. Registered
validators compare current ownership, versions, motion, diplomacy, members,
equipment and hazard captures; stale plans are cancelled and journaled before
reserving replacements. Missing validators conservatively retain reservations.
Cancellation and replacement plans use the same transaction. Backlog payloads
are streamed with a 512-plan/8-MiB admission; location state reads have an
8-MiB admission too. A work/byte/journal failure rolls back the entire pass.

Ten new tests cover no-false-negative corridor queries against exact geometry,
height/time/radius bounds, shared query work admission, hazard discovery across
retry/restart, early stale replan after scale change, atomic rollback of old
cancellation/new plan, inactive/immunity/cooldown rules, member offsets, shared
combat/hazard reservations, 65-contact admission rollback, and stale combat
release. HTTP rejects the operation for location/observer roles.
Full local backend **127 tests PASS**.

This remains explicit event-driven planning; automatic route-change subscriber,
global earliest ordering across the two planners, windowing large locations,
native AI/volume integration and live-server capacity acceptance are unfinished.
No whole C/K/L section is marked complete.

6dd10b37b DX11 Actions 37373918186 **SUCCESS**, actual full engine package built
on GitHub Actions. Foundation 37373918198 SUCCESS GCC/MSVC. Quest subscriber
285c569c6 backend Actions 37376503077 **SUCCESS Windows+Linux (117 tests)**.
Runtime installation and real native tests remain the other actor's area.

## Local account lifetime ownership (native, Actions pending)

The timestamp-only lease allowed concurrent read-then-write claims and takeover
from a paused server that could later resume writing an old character snapshot.
cluster_claim_session now opens an OS-exclusive per-account ownership file and
retains its handle for the entire session. Same-process and other-process
claims are refused; a stalled living owner is held past TTL, a process crash
releases its OS handle. The compatibility timestamp is still honoured until
expiry after a crash/old owner, but is no longer the mutual-exclusion mechanism.
Claim create/fsync/rename failure does not report success or retain the handle.
Heartbeat writes require locally held ownership. Release by a non-owner does
not remove any lease; owner release drains all background commits before
closing the exclusive handle. Empty ownership files are never deleted/replaced.

Front-end storage previously checked only local s_actor_character entries, so
a live character on another map could be edited through its saved inventory.
Authenticated slot-zero storage now claims ownership and refreshes the disk
cache around the complete read/write transaction, then releases. Failed gameplay
character selection also releases the acquired ownership instead of leaking it.

The new isolated Windows fixture extracts the actual file/claim/heartbeat/
release functions. It exercises real subprocess refusal, two claimers sharing
a start barrier, independent accounts, a stalled live owner, actual process
termination, drain ordering, non-owner release, injected create/fsync/rename
failures and legacy timestamp expiry. Source wiring assertions cover storage
and rejected selection. Only Python syntax checked locally; native compilation
and execution are added to Foundation and DX11 Actions, pending verification.

All local cluster servers must use the updated matching binary; an older
server that ignores the ownership file is not fenced by this mechanism.
This is Windows single-host/shared-runtime ownership, not distributed authority,
snapshot journal/2PC adoption or cross-host fencing. Save worker backpressure
and full native inventory-ledger integration remain unfinished.

## Combined earliest combat/hazard planning

Admin offline_plan now collects both discovery passes at one planning instant,
then admits up to 64 globally time-ordered disjoint contacts in one transaction.
Valid pending plans are options rather than unconditional locks, so a newly
placed earlier trap preempts a later captured firefight/hazard. Stale captures
are cancelled first; preemption creates durable cancellation evidence, without
health/ammo/charge mutation. Exact time ties retain previous EventID/capture/RNG,
then fresh ties use combat followed by persistent IDs. Retry/restart/new command
seed cannot reroll a retained valid outcome. Failure during preemption/capture
or admission rolls back every cancellation and replacement together.

Both original explicit planners share their existing bounded discovery helpers;
limits remain per search (combined at most 400000 candidate work checks plus
bounded validation/scheduling), 512 pending captures/8 MiB, 64 chosen contacts.
No silent truncation. Automatic route-change subscriber and native integration
are still pending, but the earlier separate-command ordering limitation now has
a unified authority operation. Eight new tests cover chronological choice in
both directions, preemption of an existing later fight and valid hazard by a
new trap, retained RNG across restart/retry/new seed, atomic journal failure,
65-contact refusal and world-scale stale cancellation. Full local backend
**135 tests PASS**; HTTP roles also reject location/observer mutation.

5302a58f4 Foundation 37378444819 **SUCCESS GCC/MSVC**, including actual Windows
session ownership subprocess/barrier/crash/flush/rename tests. Its DX11
37378445074 native checks SUCCESS; full engine compiling. 1d8004572 backend
37377564300 **SUCCESS Windows+Linux (127 tests)**.

## Bounded native character commit queue and logout failure retention

Pending background character writes now admit up to 256 queued paths and
32 MiB serialized file bytes, INCLUDING the single in-flight commit. A newer
complete snapshot supersedes only the pending snapshot for its own path;
an in-flight file is never replaced underneath I/O. Queue/byte rejection
returns false before last_save is advanced, removes the rejected temporary
file, and retains the prior durable snapshot. Failed worker commits release
their admission and attempt to remove the failed temporary file. Worker take
and finish account for bytes under the same lock. Temporary names include
process ID and a nonwrapping u64 sequence for both background and synchronous
saves; overlong paths are refused rather than truncated into a different file.

This bounds queued file payload/backlog, not total engine RSS or fsync latency.
Background save still acknowledges enqueue, not durable completion; it is
not zero-RPO journaled inventory transaction or cross-character atomic saving.
Synchronous transfer/disconnect saves still drain older pending commits first.

Native disconnect cleanup previously destroyed a tracked Actor even when
character_save_actor returned false. It now retains the Actor/character link
and account ownership, migrates off the disconnected client and requeues the
main-thread cleanup. Only successful synchronous capture/commit releases
ownership and removes the live Actor. Dead bodies retain their corpse policy;
already moved and untracked Actors keep their original cleanup paths.
Ownership migration depth now includes the ninth leaf permitted by inventory
preflight, so a supported deepest child does not retain a dead client owner.

New actual-helper GCC/MSVC fixture covers pending coalescing, byte/count
boundaries, unchanged admission on rejection, in-flight accounting, unique
process/sync paths, one real producer/consumer contention and latest snapshots.
Windows additionally executes actual commit fsync/rename fault handling.
The existing player-transfer fixture now extracts actual disconnect cleanup
and give_to_server: failure retains/retries ownership and Actor, success cleans
once, dead/moved/untracked policies and deepest valid child ownership checked.
Only Python syntax checked locally; native execution/build remain Actions-only.

Backend follow-up includes continuous narrow-phase input work in the same
200000 budget as spatial candidate discovery. An actual planner test fills
the broad budget and refuses the additional exact geometry without publishing
a partial fight. Full local backend **136 tests PASS**.
9f26f5b92 backend Actions 37379314800 **SUCCESS Windows+Linux (135 tests)**.
5302a58f4 DX11 37378445074 **SUCCESS**, including the local account ownership
and other actor's dedicated world-save ClientSave removal. Runtime installation
and real world-save/restart acceptance are still not inferred from compilation.

## Native progress capture refuses incomplete quest/script snapshots

Missing Lua serialization, thrown script errors, more than the restore limit
of 512 tasks and oversized task/info/script/origin data now return false from
the actual character_capture_progress function. Complete progress replaces the
cached snapshot only after validation. character_save_actor checks this result
before changing money, position, inventory, actor packet or storage revision;
cluster_move therefore keeps the source Actor instead of redirecting with an
old quest snapshot. Failed disconnect capture uses the existing retain/retry
path. Capture checks the one-MiB envelope before copying a large script result.

The Actions transfer fixture extracts the actual progress capture and checks
successful task/script/origin persistence, missing/throwing Lua hooks, 512/513
tasks, component/combined payload overflow and unchanged prior progress on
failure. Only Python syntax checked locally; native execution remains Actions.
This does not add transactional engine quest rewards or full GAMMA quest
remapping; restore-time failures and player-facing retry messages remain open.

024fbef42 Foundation 37381694426 SUCCESS GCC/MSVC: bounded native character
queue and disconnect retention fixtures pass. f4803b1c0 backend 37380934586
SUCCESS Windows+Linux, 136 tests. Claude's 5302a58 runtime test is recorded in
the shared handoff: actual world saved in 207 ms and loaded on server restart;
this first native acceptance does not prove all mod-owned entity state.

## Contact precision at small radii and long travel distances

Continuous sphere entry now uses closest-line/chord geometry rather than the
subtraction of two large quadratic terms. At a ten-million-metre separation
and a 0.1-metre radius, the old result fired about 0.209 world milliseconds
early on the supported one-day window. Surface entry, reverse travel, grazing,
tangency and a nearby miss are now checked. Combat resolution also matches
hazards' one-micrometre boundary tolerance: SQLite/interpolation rounding could
previously cancel a correctly captured 0.1-metre fight. An actual planned
fight now applies and journals its individual casualties at that boundary.
Full local backend **139 tests PASS**. Native paths are unchanged.

ad4725002 Foundation 37382384401 SUCCESS GCC/MSVC, including actual quest
progress capture; DX11 checks succeeded and full engine compilation is pending.

## Offline fights discover living group members instead of group centres

Both direct contact and location discovery now index actual living NPC/mutant
trajectories with formation offsets and route turns. Member pairs from the
same group are excluded before pair admission; earliest contacts collapse to
one persistent group-pair reservation. Resolution checks an actual individual
pair at the captured time before ammo or casualties, so two abstract centres
passing close do not manufacture combat when every living member misses.
Root positions remain the group's route anchors and member IDs are unchanged.

Index limits now apply to living participants (256), route segments (8192),
cross-group candidate pairs (4096) and shared broad/narrow work (200000), plus
the combined eight-MiB entity-state capture. Admission overflow rolls back all
new plans. Five tests cover offset/turn contact and restart, location discovery
with one group reservation, centre-only false positives, participant overflow
and manually scheduled phantom combat without ammo spend. Full local backend
**144 tests PASS**; 7fac62827 backend 37382911385 SUCCESS Windows+Linux (139).
This remains coarse whole-group combat after actual contact, not per-fighter
ballistics or a native AI adapter. Automatic route-change planning is pending.
