# 43. Полное ТЗ живого мира: задачи и фактический прогресс

Проверено 2026-10-05 по исходному тексту владельца из вложения
`cb4dd276-28a8-4677-8d34-9201412d0a1e/Вставленный текст.txt`, до раздела
«Финальный принцип симуляции мира» включительно. Следующий за ним
вставленный журнал прежней работы не используется как доказательство
выполнения требований. Код проверен на `0d5e5e6600f44e09fe3f4c34fc90d93e22704ee9`.

**W1–W12 — группы работ, а не число задач исходного промта.** Ни одну
группу целиком нельзя объявить закрытой. Ниже требования развёрнуты в
отдельные проверяемые задачи; буквы и номера — рабочая детализация,
а не исходная авторская нумерация. Наличие проекта в документах 41/42
не засчитывается как выполнение кода. Процент готовности по количеству
строк не вычисляется: стоимость задач сильно различается.

На исходной сверке `0d5e5e660` рабочая детализация содержит **188 задач**: 10 ограниченных
задач имеют реализацию и fixture-проверки, 3 имеют частичную основу,
175 остаются впереди. Это подсчёт данного списка, а не заявление,
что пользователь буквально написал 188 пронумерованных пунктов.

После этой сверки добавлены исполняемый transactional backend, handoff,
quests/timelines, abstract routes, economy/scavenging/encounters и native
spatial/LOD shadow. Фактическая реализация и границы проверок перечислены
в [итерации 44](44_WORLD_IMPLEMENTATION_ITERATION.md). Отметки здесь
сохраняют критерий работы **в игровой системе**: отдельный backend resolver
или fixture не закрывает engine adapter и приёмку всего пункта.

Статусы:

- `[x]` — ограниченная задача реализована и проверена указанным тестом;
  это не обещание проверки всей системы в работающей игре.
- `[ ] Частично` — код/основа есть, но критерий целиком не выполнен.
- `[ ]` — реализация и приёмка требования впереди.

Контракты, классы, сообщения, таблицы и порядок работ описаны в
[документе 42](42_WORLD_CONTRACTS_AND_CLOCK.md). Он определяет актуальные
W4–W12; поздние номера W8–W12 в первоначальном документе 41 уже расходятся
с уточнённым порядком. Этот список фиксирует прогресс, не заменяя контрактов.

## A. Сервисы, authority и масштаб мира

Основание: «Масштаб мира», «Общая серверная архитектура», «Сервер является
авторитетным», «Что требуется спроектировать». Контракты: 42 §2–3, §13–14.

- [ ] A01. Частично: исполняемый local World Service; engine adoption впереди. Глобальный календарь,
  seed, параметры мира и события; не обслуживает каждый AI/physics tick.
- [ ] A02. Независимые Location Runtime: каждый процесс изменяет только
  принадлежащую ему локацию, без повторной инициализации всей Зоны.
- [ ] A03. Authority lease и fencing между процессами/хостами: старый
  владелец после потери lease не может публиковать изменения.
- [ ] A04. Частично: backend Player Persistence с транзакциями; game bridge впереди.
- [ ] A05. Частично: backend Quest Service; GAMMA adapter впереди.
- [ ] A06. Частично: Transfer/Session Service; hidden engine spawn/release впереди.
- [ ] A07. Частично: SQLite WAL, schema migrations v1→v4, crash tests;
  coherent engine/backend recovery впереди.
- [ ] A08. Event/Message Bus: повторная доставка, inbox/outbox,
  дедупликация, порядок и повтор после отключения.
- [ ] A09. Auth/Gateway: удостоверенная серверная сессия и проверка
  запросов к backend; Firebase login не заменяет этот контракт.
- [ ] A10. Общее описание каждого интерфейса реализовать в коде:
  authority, RAM/DB, messages, cadence, errors и конкурентные изменения.
- [ ] A11. Автоматическая интеграционная проверка, что клиент не может
  назначить лут, смерть, результаты боя или квестовый прогресс.

## B. Глобальные часы и World State

Основание: «Глобальное время», World Seed, World State, server restart.
Контракты: 42 §4; W2a, W2b/W3.

- [x] B01. Переносимое ядро WorldClock: 64-битный monotonic time,
  непрерывность при смене положительного масштаба времени.
- [x] B02. Ядро LocationClock: плавная коррекция, holdover, отклонение
  старых/повторных/некорректных samples и смена epoch.
- [x] B03. Локальные WorldID/seed сохраняются; epoch увеличивается
  до bootstrap и не используется повторно после неудачного старта.
- [x] B04. Exclusive OS lock для одного владельца **локальной папки**;
  конкурирующий процесс отклоняется, каталог создаётся до открытия lock.
- [x] B05. ALife календарь и server environment time factor подключены
  к новым часам при `-netcoop_world=<name>`.
- [x] B06. Clock-aware ALife checkpoint: identity/epoch/revision,
  проверка чужого/усечённого состояния и migration старого prefix.
- [x] B07. Чтения из ALife worker и server thread защищены mutex;
  live reload/reset под той же epoch отклонён.
- [ ] B08. Частично: LocalWorldService и WorldStateSnapshot есть;
  backend durable WorldState с weather/emission timelines добавлен;
  engine consumption и territories впереди.
- [ ] B09. Удостоверенный World Service endpoint и wire encoding
  Bootstrap/ClockSync/ScaleChanged, доставка серверам локаций.
- [ ] B10. Подключить LocationClock к действительным location packets;
  сейчас это тестируемое ядро, а не межсерверная синхронизация.
- [ ] B11. Event-time highwater и replay: восстановленное время не
  откатывает уже подтверждённые мировые события.
- [ ] B12. Частично: backend event-time mutation/scale barrier реализован;
  общий engine/recovery barrier ещё нужен. Календарь, движение
  и запланированные события меняют масштаб согласованно.
- [ ] B13. ClockSync: asymmetric delay, loss/reorder, длительный разрыв
  связи и рестарт настоящего World Service/Location Server.

B01–B07 проверены native fixtures `check-netcoop-world-clock.py` и
`check-netcoop-alife-clock.py` в GitHub Actions на GCC/MSVC. Это fixtures
ядра/настоящих методов ALife со stub окружением, не live gameplay.
Сон и индивидуальное ускорение календаря исключены владельцем.

## C. Чанки и spatial optimization

Основание: simulation chunks/cells, «Несколько игроков», «Никаких жёстких
границ chunk», дальнее наблюдение. Контракты: 42 §5–6; W4–W5.

- [ ] C01. ChunkGrid каждой локации с настраиваемым размером ячейки.
- [ ] C02. Корректный CellID для отрицательных координат и границ карты.
- [ ] C03. Spatial index: insert/move/remove без полного обхода мира.
- [ ] C04. У каждой сущности актуальный location/cell и стабильный ID.
- [ ] C05. Области интереса всех игроков объединяются для simulation;
  один игрок не включает Full Simulation всей карты.
- [ ] C06. Simulation, replication и rendering radius независимы.
- [ ] C07. Activation margin учитывает максимальную наблюдаемую
  дистанцию, оптику, скорость игрока и время подготовки объектов.
- [ ] C08. Approximate visibility/PVS для открытого поля, гор и высот;
  нет raycast к каждому NPC каждый tick.
- [ ] C09. Перенос сущности между ячейками не меняет её ownership,
  здоровье, задачу и инвентарь.
- [ ] C10. Overlapping activation areas: переход границы ячейки не
  останавливает NPC, бой и стаю мутантов.
- [ ] C11. Телепорт/резкое перемещение: safe admission до готовности
  нового наблюдаемого набора, без появления NPC перед игроком.
- [ ] C12. Shadow mode: сравнить новый индекс/AOI с legacy до
  переключения authoritative paths.
- [ ] C13. Профиль: время spatial query, число активных ячеек, churn
  и стоимость двух игроков на противоположных концах локации.

SpatialGrid реализован и fixture проверен; engine использует его в
diagnostic shadow для сравнения с legacy. Новое ядро поддерживает cells,
move/erase, location scope, 128-bit IDs и capsule query. Native LOD policy
объединяет observer demand и содержит hysteresis/barrier. Live ownership,
реальное переключение AI/physics и packet admission впереди; C целиком
не закрыт. Shadow использует runtime handles вместо durable registry.

## D. Interest Management и network replication

Основание: «Interest Management», оптика, network replication.
Контракты: 42 §5; W4.

- [ ] D01. Персональный AOI/relevant set каждого подключённого игрока.
- [ ] D02. Relevance policy для видимых, owner-only и global сущностей.
- [ ] D03. Spawn baseline до delta, SpawnAck и generation handshake.
- [ ] D04. Старые пакеты/reused engine u16 ID не применяются к новой
  сущности; учитываются PersistentID и generation.
- [ ] D05. Distance-based update rates: близкие, дальние видимые,
  невидимые; приоритет игрока и ближайшего боя.
- [ ] D06. Byte/packet budget, coalescing дальних deltas, bounded queues.
- [ ] D07. Клиентская interpolation для редких distant updates.
- [ ] D08. Состояния оптики/камеры используются только как безопасный
  hint; клиент не может выключить обязательную симуляцию.
- [ ] D09. Despawn из AOI не означает уничтожение world entity.
- [ ] D10. Replication gate: неподготовленная сущность не видна игроку.
- [ ] D11. Проверки loss/reorder/reconnect, AOI churn, bytes/player/sec
  и p99 replication под 32/64/128 реальными sessions.

Существующие дистанционные фильтры — исходная база, а не выполнение D.

## E. Четыре Simulation LOD, PREWARM и hydration

Основание: «Simulation LOD», «Event-driven simulation», «NPC никогда
не должен визуально просыпаться», PREWARM, HYDRATION/DEHYDRATION.
Контракты: 42 §6; W5.

- [ ] E01. SimulationLodManager с Full/Reduced/Coarse/Statistical.
- [ ] E02. LOD0: полноценные AI, perception, путь, бой, пули, гранаты,
  укрытия, physics и интерактивные объекты в наблюдаемой области.
- [ ] E03. LOD1: NPC продолжают движение/патруль и базовые действия.
- [ ] E04. Конфиг частот AI для Full/Reduced; дешёвые perception/path
  cadence вместо полного вычисления каждый frame.
- [ ] E05. Дальние взаимодействия без детальной баллистики/physics,
  с согласованным переходом в Full до наблюдаемого боя.
- [ ] E06. LOD2: GroupState, маршруты, ресурсы и состояние каждого
  конкретного члена группы; без анонимного повторного создания состава.
- [ ] E07. LOD3: события и аналитические состояния без тика каждого NPC.
- [ ] E08. LOD выбирается по максимальному спросу всех наблюдателей.
- [ ] E09. PREWARM прогнозирует позицию/скорость/направление игрока,
  соседние ячейки и точки обзора.
- [ ] E10. Очередь hydration с бюджетом, приоритетом и deadline.
- [ ] E11. Частично: backend допускает полный projected hydration capture
  по мере чтения до смены владельца; native materialization barrier ещё нужен.
  Загрузка persistent и abstract state до материализации.
- [ ] E12. Catch-up от LastSimulationTime до текущего WorldTime.
- [ ] E13. Позиции групп на текущем участке маршрута рассчитываются
  аналитически, а не берутся из старой точки ухода игрока.
- [ ] E14. Восстановить member IDs, здоровье, боезапас, инвентарь,
  задачи, маршрут и индивидуальные состояния.
- [ ] E15. Запустить Reduced AI до разрешения replication.
- [ ] E16. Dehydration сохраняет изменения до удаления online representation.
- [ ] E17. Hysteresis/cooldown; возврат игрока отменяет понижение LOD.
- [ ] E18. Combat/quest/transfer pins запрещают опасное сворачивание.
- [ ] E19. Stale async hydration result не создаёт вторую копию entity.
- [ ] E20. ALife adapter: Full→Reduced→Group→Statistical и обратно
  меняют представление, сохраняя существование и причинность.
- [ ] E21. Приёмка: высота/оптика, максимальная скорость, два игрока,
  бой у границы; нет видимого «пробуждения» и пропажи сущностей.

Основа E добавлена: planner четырёх уровней, hysteresis и RepresentationGate
в native fixture/shadow; backend сохраняет полный capture и аналитические
маршруты конкретных групп. ALife adapter/Reduced AI/hydration queue ещё
не подключены. Штатные два ALife состояния не считаются четырьмя LOD.

## F. Entity ownership, предметы и защита от duplication

Основание: «Loot ownership», «Ownership transfer Entity», Containers,
Unique NPC, anti-duplication. Контракты: 42 §3, §7; W6.

- [ ] F01. PersistentID, version, owner и fence для всех persistent entities.
- [ ] F02. Реестр entity mapping: engine object ↔ persistent representation.
- [ ] F03. ItemLedger: предмет существует ровно в одном месте/инвентаре.
- [ ] F04. Единый atomic MoveItem вместо независимых remove/add.
- [ ] F05. WORLD/PLAYER/NPC/CORPSE/STASH/CONTAINER/TRADE/TRANSFER/DESTROYED
  участвуют в одном ownership контракте.
- [ ] F06. Частично: backend owner/version/CAS и текущая авторизация при
  CommandID replay, включая lease grant/renew/abort и entity/session/item/
  quest/trade paths. Native mutation adapter и общие generations ещё нужны.
- [ ] F07. CommandID/result: повтор запроса не повторяет выдачу или перенос.
- [ ] F08. Сохранение condition, attachments, ammo и индивидуального состояния.
- [ ] F09. Unique NPC и члены обычных групп не клонируются при hydration.
- [ ] F10. Permanent death tombstone: смерть не превращается в respawn.
- [ ] F11. Quest-protected/PlayerOnly/FactionAccessible права доступа.
- [ ] F12. Fault injection: одновременный pickup, смерть+trade,
  stale owner, повтор transfer; сохраняется один owner и количество вещей.

## G. Persistence, journal, recovery и рестарт

Основание: «Persistence», «Crash recovery», event system.
Контракты: 42 §8; W1/W7.

- [ ] G01. Частично: существующие ALife world snapshots и player saves;
  полная независимая persistence всех новых типов ещё не введена.
- [x] G02. Проверка обоих файлов committed snapshot `.scop`/`.scoc`:
  size/checksum, readback фактической Lua serialization.
- [x] G03. Inactive slot выбирается относительно последнего commit;
  не перезаписывает committed slot сразу после рестарта.
- [x] G04. Публикация manifest только после записи/flush обоих файлов;
  повреждённый pointer/отсутствующий sidecar останавливают загрузку.
- [ ] G05. Durable event journal важных изменений после snapshot.
- [ ] G06. Idempotent replay и snapshot event watermark.
- [ ] G07. Coherent capture barrier для clock, ALife, Lua и ItemLedger.
- [ ] G08. Согласование world snapshot и player inventory commit.
- [ ] G09. Transactional inbox/outbox; crash между commit и ACK.
- [ ] G10. Recovery по валидному snapshot+journal с явной проверкой
  integrity, без генерации нового мира при потере данных.
- [ ] G11. Retention/compaction и миграция схем без потери persistent IDs.
- [x] G12. Первичный durable checkpoint до допуска игроков и важных действий.
  Native doc76: до первого COMMIT отказы nbot202/203, включая failed
  script validation; original checker restored, оба snapshot digests
  проверены, после bootstrap commit nbot204 Actor42752/final1playing.
  Local admission only, не distributed/crash/post-admission transactions.
- [ ] G13. Native engine crash/kill/power-loss испытания на каждом шаге
  capture/write/commit/replay; измерить RPO/RTO и snapshot pause.

G02–G04 проверены `check-netcoop-world-store.py` и
`check-netcoop-world-rules.py`. Это ещё не полный crash recovery:
нет журнала, возможна потеря последних пяти минут и несогласованность
отдельных world/player saves. Не заявляется crash-safe ItemLedger.

## H. Переходы игроков, NPC и sessions

Основание: «Переходы между локациями», «NPC, переходящие между локациями».
Контракты: 42 §9; W8.

- [ ] H01. Admission: предел общей/локальной capacity, очередь target.
- [ ] H02. Единственный session owner персонажа и reconnect policy.
- [ ] H03. Freeze и durable transferable checkpoint на source.
  Включить инвентарь с condition/ammo/attachments, здоровье/радиацию/
  ранения и прочее сохраняемое состояние персонажа, quest links;
  destination не создаёт стартовый комплект повторно.
- [ ] H04. Одноразовый transfer token с персонажем, target, expiry и fence.
- [ ] H05. State machine Prepare/Claim/Commit/Release/Abort/Status.
- [ ] H06. Hidden target spawn, подтверждение, затем release source.
- [ ] H07. Повторы/старые tokens не дают duplicate spawn или inventory.
- [ ] H08. Disconnect/crash source/target и expiry после claim.
- [ ] H09. NPC/squad transit с теми же IDs и одним location owner.
- [ ] H10. Наблюдаемый переход реально проигрывается; ненаблюдаемый
  считается abstract event с тем же конечным результатом.
- [ ] H11. Ограничить ALife/GAMMA initializers своей локацией прежде,
  чем запускать второй authoritative location process.
- [ ] H12. Приёмка: 1000 переходов с аварией в каждой стадии,
  заполненной target и проверкой сохранности персонажа/вещей.
- [ ] H13. Transition endpoints и безопасные destination spawn points:
  направление перехода/возврат, проверка поверхности и готовности AOI.
- [ ] H14. Freeze/admission policy не оставляет персонажа одновременно
  активным в бою на source и target; client input принадлежит одному owner.
- [ ] H15. Понятные клиентские состояния ожидания/ошибки/reconnect,
  возможность выяснить результат pending transfer, без повторной регистрации.

Текущий переход внутри одного engine/обычные netcoop запросы не
подменяют этот межсерверный handoff.

Исторический статус 2026-10-05 (Claude, первый рабочий вариант):
кластер локаций `src/xrGame/netcoop_cluster.inc`. Один dedicated процесс на
карту из одной runtime папки (общие accounts/characters), адреса карт в
`$app_data_root$/netcoop_cluster.ltx` (пример `scripts/netcoop-cluster/`).
- H02/H14 🔧 lease аккаунта (`netcoop_cluster/online_<login>.txt`, heartbeat
  10 с, TTL 30 с): вход отклоняется, пока другой живой сервер держит игрока;
  уходящий игрок заморожен (все его пакеты игнорируются до disconnect).
- H03 🔧 синхронное сохранение персонажа (fsync) с точкой прибытия перехода;
  после этого source больше не сохраняет персонажа; кэш персонажа на target
  сбрасывается при входе, файл читается с диска.
- H04/H07 🔧 одноразовый ticket (HMAC-SHA256, общий secret, TTL 180 с,
  удаляется при чтении); клиент ticket не получает и подделать не может.
- H05 частично: Prepare (проверка перехода) → Commit (save+ticket+release
  lease) → Claim на target (lease+ticket). Abort = отказ до save.
- H08 частично: падение source → lease истекает за 30 с, персонаж в
  последнем сохранении; падение target → вход повторяется.
- H13 частично: точка прибытия — данные самого level changer на сервере,
  клиент передаёт только идентификатор перехода.
- H15 частично: отказ показывается игроку текстом; переподключение
  автоматическое (`start client(...)`) с теми же учётными данными.
- Accounts: общий файл сливается между процессами (named mutex, re-read
  по mtime, свои несохранённые изменения не теряются).
Самотест 2026-10-05 (`scripts/run-cluster-selftest.ps1`, билд 1566b38, реальные
серверы и headless боты): 88 переходов за 10 минут без отказов и ошибок.
Открыто: H01 очередь/ёмкость, H06 hidden spawn, H09/H10 NPC transit,
H11 (каждый процесс пока ведёт свою копию ALife: NPC других карт там
офлайн и игрокам не видны; story-объекты совпадают по story id, задания на
обычные объекты другой карты пока не переносятся), H12 нагрузочная приёмка.

Актуализация 2026-10-06; этот абзац заменяет старое описание TTL lease выше.
Native ownership аккаунта удерживается exclusive OS file lock в общей runtime
папке: TTL больше не позволяет другому процессу забрать живого владельца.
При падении процесса OS освобождает lock; это не межхостовый fencing. Native
переход сохраняет персонажа синхронно, target перечитывает файл, одноразовый
HMAC ticket привязан к переходу. Пока inventory parentage, Lua/task/info restore
не завершены, target не принимает игровые действия/autosave/wallet mutations;
валидная input sequence продолжает обновляться, чтобы долгий restore не
блокировал управление после завершения. Logout capture/wallet failure удерживает
Actor/ownership и повторяется с backoff. Wallet commit вынесен из transport
callback в main-thread cleanup. Character/account файлы ещё не единый commit.

Backend дополнительно реализует capacity reservations, transfer state machine
Prepare/Claim/Commit/Release/Abort/Status, immutable checkpoint, command dedup и
fault/restart проверки. Это отдельная authority; native player adapter ещё нужен.
Native NPC mailbox/receipt-before-ACK остаётся opt-in: полного общего persistent
registry/fencing/full mod-state adapter нет. Prune чужой generic ALife population
проверен в runtime (H11-lite), но не заменяет единственного глобального NPC owner.
Поэтому ни H, ни W8 целиком не закрыты. H01 очередь, H06 hidden target spawn,
H09/H10 полноценный NPC/squad handoff, H12 1000 аварийных переходов, H13 surface/
готовность AOI и межхостовое fencing/recovery остаются открытыми.

Native доказательства: Foundation 37414908176 и полная DX11 37414908195
SUCCESS на 268caa26d. Билд произведён GitHub Actions; установка последнего
пакета и live acceptance этим результатом не утверждаются. Подробности и
история фактических runtime проверок — в документах 44/45.

## I. Межлокационные задания

Основание: «Квесты между локациями», «Уникальные NPC». Контракты: 42 §10; W9.

- [ ] I01. Quest state хранится вне конкретного Location Server.
- [ ] I02. Progression/version/CAS и авторитетная проверка условий.
- [ ] I03. Частично: backend authenticated location-scoped requirements pages
  (64 rows, epoch/revision cut) следуют за существующими IDs при migration/death;
  native subscriber/apply и live cross-location приёмка ещё нужны.
- [ ] I04. Quest NPC связан с существующим PersistentID, без клонирования.
- [ ] I05. Offline death/migration согласованы с заданием.
- [ ] I06. Reward transaction идемпотентна и не выдаёт награду повторно.
- [ ] I07. Приёмка Кордон→Юпитер, рестарт destination, конкурирующие
  стадии, offline death и 512 наборов заданий.

## J. Погода, выброс и укрытия

Основание: «Погода», «Выброс», «Укрытия от выброса».
Контракты: 42 §11; W10.

- [ ] J01. Единая WeatherState/seed/transition timeline из World Service.
- [ ] J02. Локальные модификаторы и interpolation относительно WorldTime.
- [ ] J03. Публикация изменений без отправки погоды каждый frame.
- [ ] J04. EmissionID и расписание warning/start/peak/end заранее.
- [ ] J05. Late join/restart восстанавливают правильную фазу выброса.
- [ ] J06. Shelter graph и estimated arrival для NPC/групп.
- [ ] J07. Полный AI рядом; математическое укрытие/последствия далеко.
- [ ] J08. Idempotent damage/death/anomaly/artifact effects одного выброса.
- [ ] J09. Отмена stale abstract effect при переходе к наблюдаемой симуляции.
- [ ] J10. Приёмка двух location servers, restart на каждой фазе,
  повтор EmissionEnd и batch effects на 25 локациях.

Имеющиеся GAMMA погодные/выбросные скрипты — исходная база;
межсерверный контракт J ими пока не выполнен.

## K. Offline simulation, маршруты и последствия

Основание: event-driven simulation, causality, deterministic simulation,
Simulation Catch-Up, звуковые события/следы. Контракты: 42 §12; W11.

- [ ] K01. Частично: backend scheduler/arrival/durable planning windows;
  native adoption нужен, постоянного ticking NPC в backend нет.
- [ ] K02. Частично: backend analytic route/start/arrival/speed; engine adapter нужен.
- [ ] K03. Частично: backend GroupState хранит конкретных членов/потери;
  полная native hydration состояния ещё нужна.
- [ ] K04. Частично: backend actual member contacts и configured mutation
  subscriber/durable horizons; native outcomes и последующее AI решение впереди.
- [ ] K05. Детерминированный seed из world/event/chunk/day и simulation version.
- [ ] K06. Результат фиксируется до применения и не зависит от первого игрока.
- [ ] K07. Потери, ранения, ammo/medical расход, победители и контроль точки.
- [ ] K08. EventRecord содержит участников, время, результат и evidence.
- [ ] K09. После прихода игрока появляются сохранённые последствия:
  тела, вещи, раненые, победивший отряд и изменённое состояние территории.
- [ ] K10. Дальний звук привязан к реальному событию, направлению и дистанции.
  Частично (2026-10-09, код): каждый раунд офлайн-боя GAMMA (OCS) на карте
  сервер сообщает игрокам в 150–1500 м (точка между отрядами, стрельба/мутанты);
  клиент играет дальнюю запись GAMMA с этого направления, громкость по реальной
  дистанции (netcoop_distant_battles / netcoop_distant_sound, фикстура в CI).
  Случайный ambient-канал out_gunfire GAMMA не тронут. В игре не проверено.
- [ ] K11. Косметические blood/shell effects отдельно от persistent loot.
  Частично (2026-10-09, по коду): гильзы — частицы оружия (ShootingObject
  shell particles) и звуки grok_casings_sounds, кровь — wallmarks/частицы на
  клиенте; ни один из них не создаёт серверный объект/предмет, а кровь на
  динамических неживых предметах уже отвергается. Отдельная приёмка в игре не
  проводилась.
- [ ] K12. Частично: bounded backend catch-up и captured-time continuation;
  большая live native приёмка ещё нужна. Семь часов не проигрываются по ticks.
- [ ] K13. Full↔Coarse boundary у события не разрешает бой дважды.
- [ ] K14. Приёмка: 20 минут без игроков, другой первый наблюдатель,
  одинаковые input/seed на двух серверах и большой catch-up.

## L. Аномалии, артефакты, лут и прочие объекты мира

Основание: все разделы от «28. Аномалии» до классификации World Entity.
Контракты: 42 §12; W6/W11/W12. Здесь включены дополнительные части ТЗ,
которые не умещаются в формулировку «оптимизация по чанкам».

- [ ] L01. Abstract Anomaly State с ID/type/position/radius/intensity,
  active/cooldown/seed/emission cycle без удалённых collision/damage ticks.
- [ ] L02. Anomaly prewarm создаёт gameplay volumes до replication;
  сервер определяет попадание, урон, смерть и выброс вещей.
- [ ] L03. Route anomaly risk учитывает опыт, faction, экипировку и знания NPC.
- [ ] L04. Детерминированные offline anomaly injuries/deaths/item consequences.
- [ ] L05. ArtifactID и одно authoritative состояние world/inventory/container.
- [ ] L06. ArtifactSpawnEvents после EmissionEnd определяются заранее,
  не генерируются первым приблизившимся игроком.
- [ ] L07. Safe deterministic artifact placement при hydration.
- [ ] L08. NPC ищут артефакты offline с equipment/experience/danger/task.
- [ ] L09. Артефакт остаётся у NPC, затем в corpse inventory после смерти.
- [ ] L10. GroundLootCluster уменьшает число активных entities;
  сохраняет individual IDs/condition/ammo/attachments, без потери вещей.
- [ ] L11. Safe ground placement: поверхность, rotation и downward validation;
  предмет не зависает, не проваливается, не оказывается внутри стены.
- [ ] L12. Persistent stash: содержимое, lock/owner/version/discovery/quest links.
- [ ] L13. Loot seed фиксируется при создании; открытие/рестарт не reroll.
  Частично (код, 2026-10-10): план содержимого ящика бросается один раз и
  хранится (netcoop_box_contents v2), лут трупа создаётся при смерти один раз,
  опустевший тайник не перегенерируется (zz_netcoop_sandbox). В игре не проверено.
- [ ] L14. Частично: backend route discovery/редкость/общие contact reserves
  реализованы; native AI/ledger adapter и live приёмка ещё нужны. NPC редко посещают тайники, реально/аналитически добираются
  до них и забирают/кладут вещи через atomic MoveItem.
- [ ] L15. Stash access: PlayerOnly/QuestProtected/NPCAccessible/FactionAccessible.
- [ ] L16. Scavenging ограничен carry capacity/needs/value/faction;
  NPC не получает бесконечный инвентарь.
- [ ] L17. Смена оружия NPC оставляет прежнее оружие с тем же item identity.
- [ ] L18. Containers имеют authoritative inventory/owner/lock/version;
  pickup/trade выполняются общей транзакцией.
- [ ] L19. Corpse: entity ID, death time/cause, inventory и quest association.
- [ ] L20. Ragdoll→static→abstract corpse без постоянной удалённой physics.
- [ ] L21. Частично: native online/offline detach и backend cleanup есть;
  backend переносит вещи durable партиями до 64/4 MiB, завершает тело только
  после последней партии; engine tombstone/quest adapter и gameplay recovery
  впереди. Corpse cleanup сохраняет death tombstone и переводит **все
  оставшиеся вещи** на землю с теми же IDs; quest bodies имеют special policy.
- [ ] L22. Loot generation policy зависит от world events/economy/выброса,
  а не ухода игрока или рестарта; не подменяет rare stash visits.
- [ ] L23. Mutant territory/food/aggression/migration/species relations
  сохраняют индивидуальный состав стаи и постоянные смерти.
- [ ] L24. Persistent dens/nests, food/threat/capacity; автопополнение
  популяции отключено согласно новому решению владельца.
- [ ] L25. Лёгкая экология меняет опасность маршрутов и события без Full AI.
- [ ] L26. Trader money/inventory/supply/demand/restock с configurable economy.
- [ ] L27. Поставки/караваны/редкость связаны с world events и ledger.
- [ ] L28. Campfire active/fuel/start/end: состояние рассчитывается по времени;
  не нужен постоянный distant fire tick.
  Частично (код): на старте сервера костры не горят, зажигают NPC через лагерную
  логику GAMMA или игрок спичками через сервер, состояние рассылается всем
  (netcoop_campfire.inc). Расчёта fuel/end по времени нет.
- [ ] L29. Door open/lock/destroyed state сохраняется и влияет на offline route.
  Частично (код): состояние дверей (ph_door binder) и физика входят в снимок мира
  (world_store_capture_physics_props); влияние на офлайн-маршрут не сделано.
- [ ] L30. Важные destructibles сохраняют INTACT/DAMAGED/DESTROYED.
  Частично (код): здоровье разрушаемых объектов сохраняется в снимке мира
  (netcoop_capture_saved_health), разрушенные не возвращаются. В игре не проверено.
- [ ] L31. Trap owner/type/armed/charges и offline trigger с version check.
- [ ] L32. Persistence/Simulation/Replication classes реализованы в общих policies.
- [ ] L33. Event связи emission→artifacts→NPC→trade, mutants→routes→loot,
  factions→territory→quests, weather/time→schedules/perception.
- [ ] L34. Частично: штатный smart-terrain/SMR NPC/mutant replenishment
  отключён server Lua guard; нужен аудит остальных spawn-путей модов.
- [ ] L35. Сохранить полное состояние живых NPC/мутантов при restart
  и LOD transitions; убитые не создаются снова.
- [ ] L36. Частично: release_item_manager и native inventory/weapon/grenade
  age-only TTL отключены; полный mod audit и restart приёмка впереди. Удалить gameplay-item TTL из всех mod cleanup paths:
  вещи на полу и содержимое тайников сохраняются.
- [ ] L37. Новое наполнение тайников: редко, обычные consumables/materials/ammo;
  без брони и мощного оружия, с проверкой loot classification.
  Частично (код): STASH_VISIT в netcoop_server_compat — не чаще раза в 6 игровых
  часов, 8 %, только NPC рядом и без игроков, кладут еду/медицину/материалы/
  патроны, никогда оружие/броню/артефакты; предметы переносятся, не создаются.
- [ ] L38. Проверить цепочку artifact→NPC→corpse→player→trader→player
  через аварии/рестарты; всегда один экземпляр и одно место существования.

**Новые решения владельца заменяют старые части промта:** NPC/мутанты
не respawn и не восстанавливают численность; их состояния и смерти постоянны.
Gameplay предметы на земле не исчезают по TTL. Удаляться могут тела
и косметические эффекты; оставшийся loot тела сохраняется. NPC меняют
обычные доступные тайники редко; не удаляют/генерируют защищённые вещи.
Пока классификация оружия не готова, auto-deposit исключает всё оружие.
Это не запрещает игроку хранить в собственном тайнике броню/оружие.
Серверные костры/старые сохранения тайников уже есть, но весь новый
event-driven/persistent контракт соответствующих L-задач не проверен.

## M. Перегрузка, профилирование и нагрузочная приёмка

Основание: «Backpressure и деградация», стабильность, 25 локаций/512/128.
Контракты: 42 §13; критерии W4–W12.

- [ ] M01. Метрики frame p50/p95/p99/max: AI/physics/replication/IO отдельно.
  Частично (код, 61736a7ae): [frames] p50/p95/p99/max; [profile] ai, replication,
  items, physics (свой счётчик шага физики), io (запись мира) мс/с. Не снято вживую.
- [ ] M02. Metrics по LOD/chunks/online entities и очереди hydration.
  Частично (код, 997d0c80e): [world] онлайн сталкеры/мутанты/игроки/предметы на
  земле/физпропы и ALife всего/онлайн; LOD/chunks/hydration — только в shadow.
- [ ] M03. Prewarm latency/deadline и достаточный reserved budget.
- [ ] M04. При перегрузке сначала дальняя replication/Reduced/Coarse,
  ближайший бой и игроки имеют приоритет.
- [ ] M05. Bounded backlog, event age, admission limits и cooldown возврата качества.
- [ ] M06. Тесты 32/64/128 настоящих игровых sessions в hot location.
- [ ] M07. 512 sessions по 25 локациям; пустые локации остаются abstract,
  не симулируют всю Зону Full AI.
- [ ] M08. Суточный сценарий NPC/loot/stashes/emission/trade/transfer.
- [ ] M09. Инварианты zero duplicate IDs/one owner, bounded RSS/backlog,
  packet budgets, snapshot pause, RPO/RTO при restart.
- [ ] M10. Сравнить плотный и рассредоточенный сценарии с legacy baseline;
  только после этого заявлять достигнутую capacity.

512 clock readers в native fixture не являются 512 игровыми connections.
В проверочном server launcher пока `maxplayers=2`.

## Проверки и текущая граница следующего шага

Проверки фундамента на указанном code commit прошли в
[GitHub Actions World Foundation](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37326362258).
[Полная DX11 сборка](https://github.com/Gostn1ght/AnomalyMP/actions/runs/37326362377)
на момент составления списка ещё выполняется; промежуточные `checks`
прошли. До её успешного завершения этот список не подтверждает сборку
всего engine или установку нового native package. Native компиляция
выполняется только через GitHub Actions, как потребовал владелец.

Ближайшая последовательность: закончить durable World State/clock
transport и location authority → реализовать C/D в shadow mode → E.
Нельзя добавлять четыре LOD простым увеличением дистанции ALife или
останавливать дальних NPC. Новые ownership/persistence гарантии должны
появиться до опасной hydration и второго location owner.

Переходы H остаются обязательной частью реализации. NPC transit также
связан с K (маршруты/arrival events), заданиями I и ownership F;
обычный перенос игрока на другую карту внутри одного процесса не
закрывает безопасный handoff между серверами.

Отдельные незакоммиченные изменения мебели/тайников и состояния
персонажа не входят в этот code commit и не засчитаны как завершение
нового ItemLedger/World Service. Проверка нового запуска и поведения
в самой игре ещё не выполнена.
