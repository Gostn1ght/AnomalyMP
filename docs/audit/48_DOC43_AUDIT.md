# 48. Аудит дока 43 (2026-10-06)

Честный статус каждого из 188 пунктов дока 43. ✅ проверено на реальных exe;
🔧 есть в коде/fixtures, в игре не проверено; 🟡 частично; ⬜ не сделано.
Генерируется `tools/make-doc43-audit.py`.

Итого: ✅ 10, 🔧 22, 🟡 59, ⬜ 97 из 188.

## A

| Пункт | Статус | Что есть |
|---|---|---|
| A01 Частично: исполняемый local World Service; engine adoption впереди | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A02 Независимые Location Runtime: каждый процесс изменяет только | 🟡 | процесс на карту; чужое generic население удаляется (live), но ALife всей Зоны всё ещё грузится |
| A03 Authority lease и fencing между процессами/хостами: старый | 🟡 | lease аккаунта + файловые замки (работают по общей сетевой папке); межхостового fencing нет |
| A04 Частично: backend Player Persistence с транзакциями; game bridge впереди | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A05 Частично: backend Quest Service; GAMMA adapter впереди | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A06 Частично: Transfer/Session Service; hidden engine spawn/release впереди | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A07 Частично: SQLite WAL, schema migrations v1→v4, crash tests; | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A08 Event/Message Bus: повторная доставка, inbox/outbox, | 🟡 | backend World Service (Codex); engine только observer/частичные адаптеры |
| A09 Auth/Gateway: удостоверенная серверная сессия и проверка | 🟡 | аккаунты, Firebase, observer token; нет единого gateway |
| A10 Общее описание каждого интерфейса реализовать в коде: | ⬜ |  |
| A11 Автоматическая интеграционная проверка, что клиент не может | ⬜ |  |

## B

| Пункт | Статус | Что есть |
|---|---|---|
| B01 Переносимое ядро WorldClock: 64-битный monotonic time, | 🔧 | native fixtures в CI |
| B02 Ядро LocationClock: плавная коррекция, holdover, отклонение | 🔧 | native fixtures в CI |
| B03 Локальные WorldID/seed сохраняются; epoch увеличивается | 🔧 | native fixtures в CI |
| B04 Exclusive OS lock для одного владельца **локальной папки**; | 🔧 | native fixtures в CI |
| B05 ALife календарь и server environment time factor подключены | ✅ | рестарт сервера: игровое время продолжилось (2026-10-06) |
| B06 Clock-aware ALife checkpoint: identity/epoch/revision, | 🔧 | native fixtures в CI |
| B07 Чтения из ALife worker и server thread защищены mutex; | 🔧 | native fixtures в CI |
| B08 Частично: LocalWorldService и WorldStateSnapshot есть; | 🟡 | backend WorldState; engine не потребляет |
| B09 Удостоверенный World Service endpoint и wire encoding | ⬜ |  |
| B10 Подключить LocationClock к действительным location packets; | 🟡 | кластерный календарь через файлы: отстающий догоняет ускорением (видно в live логах) |
| B11 Event-time highwater и replay: восстановленное время не | ⬜ |  |
| B12 Частично: backend event-time mutation/scale barrier реализован; | ⬜ |  |
| B13 ClockSync: asymmetric delay, loss/reorder, длительный разрыв | ⬜ |  |

## C

| Пункт | Статус | Что есть |
|---|---|---|
| C01 ChunkGrid каждой локации с настраиваемым размером ячейки | 🔧 | SpatialGrid в shadow-режиме, fixtures |
| C02 Корректный CellID для отрицательных координат и границ карты | 🔧 | SpatialGrid в shadow-режиме, fixtures |
| C03 Spatial index: insert/move/remove без полного обхода мира | 🔧 | SpatialGrid в shadow-режиме, fixtures |
| C04 У каждой сущности актуальный location/cell и стабильный ID | 🔧 | SpatialGrid в shadow-режиме, fixtures |
| C05 Области интереса всех игроков объединяются для simulation; | ⬜ |  |
| C06 Simulation, replication и rendering radius независимы | ⬜ |  |
| C07 Activation margin учитывает максимальную наблюдаемую | ⬜ |  |
| C08 Approximate visibility/PVS для открытого поля, гор и высот; | ⬜ |  |
| C09 Перенос сущности между ячейками не меняет её ownership, | ⬜ |  |
| C10 Overlapping activation areas: переход границы ячейки не | ⬜ |  |
| C11 Телепорт/резкое перемещение: safe admission до готовности | ⬜ |  |
| C12 Shadow mode: сравнить новый индекс/AOI с legacy до | 🟡 | shadow сравнение и лог [chunk-shadow] |
| C13 Профиль: время spatial query, число активных ячеек, churn | 🟡 | shadow сравнение и лог [chunk-shadow] |

## D

| Пункт | Статус | Что есть |
|---|---|---|
| D01 Персональный AOI/relevant set каждого подключённого игрока | 🟡 | legacy AOI: дистанционные уровни частоты на клиента |
| D02 Relevance policy для видимых, owner-only и global сущностей | ⬜ |  |
| D03 Spawn baseline до delta, SpawnAck и generation handshake | ⬜ |  |
| D04 Старые пакеты/reused engine u16 ID не применяются к новой | ⬜ |  |
| D05 Distance-based update rates: близкие, дальние видимые, | 🟡 | legacy AOI: дистанционные уровни частоты на клиента |
| D06 Byte/packet budget, coalescing дальних deltas, bounded queues | ⬜ |  |
| D07 Клиентская interpolation для редких distant updates | ⬜ |  |
| D08 Состояния оптики/камеры используются только как безопасный | ⬜ |  |
| D09 Despawn из AOI не означает уничтожение world entity | ⬜ |  |
| D10 Replication gate: неподготовленная сущность не видна игроку | ⬜ |  |
| D11 Проверки loss/reorder/reconnect, AOI churn, bytes/player/sec | 🟡 | замер ботами: 16 игроков ~110 КБ/с на игрока; нет loss/reorder тестов |

## E

| Пункт | Статус | Что есть |
|---|---|---|
| E01 SimulationLodManager с Full/Reduced/Coarse/Statistical | 🔧 | LOD planner + hysteresis в shadow/fixtures |
| E02 LOD0: полноценные AI, perception, путь, бой, пули, гранаты, | ⬜ |  |
| E03 LOD1: NPC продолжают движение/патруль и базовые действия | ⬜ |  |
| E04 Конфиг частот AI для Full/Reduced; дешёвые perception/path | ⬜ |  |
| E05 Дальние взаимодействия без детальной баллистики/physics, | ⬜ |  |
| E06 LOD2: GroupState, маршруты, ресурсы и состояние каждого | ⬜ |  |
| E07 LOD3: события и аналитические состояния без тика каждого NPC | ⬜ |  |
| E08 LOD выбирается по максимальному спросу всех наблюдателей | ⬜ |  |
| E09 PREWARM прогнозирует позицию/скорость/направление игрока, | ⬜ |  |
| E10 Очередь hydration с бюджетом, приоритетом и deadline | ⬜ |  |
| E11 Частично: backend допускает полный projected hydration capture | 🟡 | backend projected hydration capture |
| E12 Catch-up от LastSimulationTime до текущего WorldTime | ⬜ |  |
| E13 Позиции групп на текущем участке маршрута рассчитываются | ⬜ |  |
| E14 Восстановить member IDs, здоровье, боезапас, инвентарь, | ⬜ |  |
| E15 Запустить Reduced AI до разрешения replication | ⬜ |  |
| E16 Dehydration сохраняет изменения до удаления online representation | ⬜ |  |
| E17 Hysteresis/cooldown; возврат игрока отменяет понижение LOD | 🔧 | LOD planner + hysteresis в shadow/fixtures |
| E18 Combat/quest/transfer pins запрещают опасное сворачивание | ⬜ |  |
| E19 Stale async hydration result не создаёт вторую копию entity | ⬜ |  |
| E20 ALife adapter: Full→Reduced→Group→Statistical и обратно | ⬜ |  |
| E21 Приёмка: высота/оптика, максимальная скорость, два игрока, | ⬜ |  |

## F

| Пункт | Статус | Что есть |
|---|---|---|
| F01 PersistentID, version, owner и fence для всех persistent entities | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F02 Реестр entity mapping: engine object ↔ persistent representation | ⬜ |  |
| F03 ItemLedger: предмет существует ровно в одном месте/инвентаре | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F04 Единый atomic MoveItem вместо независимых remove/add | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F05 WORLD/PLAYER/NPC/CORPSE/STASH/CONTAINER/TRADE/TRANSFER/DESTROYED | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F06 Частично: backend owner/version/CAS и текущая авторизация при | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F07 CommandID/result: повтор запроса не повторяет выдачу или перенос | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |
| F08 Сохранение condition, attachments, ammo и индивидуального состояния | 🟡 | condition/ammo/upgrades/item state сохраняются в персонаже и мире |
| F09 Unique NPC и члены обычных групп не клонируются при hydration | ⬜ |  |
| F10 Permanent death tombstone: смерть не превращается в respawn | 🟡 | спавнеры и респавн отключены (live лог); tombstone в backend |
| F11 Quest-protected/PlayerOnly/FactionAccessible права доступа | 🟡 | владелец/список доступа мебели и тайников (код) |
| F12 Fault injection: одновременный pickup, смерть+trade, | 🟡 | backend ItemLedger/CAS/dedup/fault tests (Codex); native adapter нет |

## G

| Пункт | Статус | Что есть |
|---|---|---|
| G01 Частично: существующие ALife world snapshots и player saves; | ✅ | сохранение мира и продолжение после рестарта на реальном сервере (2026-10-06, раньше не работало) |
| G02 Проверка обоих файлов committed snapshot ` | ✅ | fixtures + live: слот, pointer, sidecar, загрузка сохранённого мира |
| G03 Inactive slot выбирается относительно последнего commit; | ✅ | fixtures + live: слот, pointer, sidecar, загрузка сохранённого мира |
| G04 Публикация manifest только после записи/flush обоих файлов; | ✅ | fixtures + live: слот, pointer, sidecar, загрузка сохранённого мира |
| G05 Durable event journal важных изменений после snapshot | ⬜ |  |
| G06 Idempotent replay и snapshot event watermark | ⬜ |  |
| G07 Coherent capture barrier для clock, ALife, Lua и ItemLedger | ⬜ |  |
| G08 Согласование world snapshot и player inventory commit | ⬜ |  |
| G09 Transactional inbox/outbox; crash между commit и ACK | 🟡 | backend inbox/outbox |
| G10 Recovery по валидному snapshot+journal с явной проверкой | ⬜ |  |
| G11 Retention/compaction и миграция схем без потери persistent IDs | ⬜ |  |
| G12 Первичный durable checkpoint до допуска игроков и важных действий | 🔧 | новый мир сохраняется через 30 с после старта; вход закрыт до первого сохранения |
| G13 Native engine crash/kill/power-loss испытания на каждом шаге | ⬜ |  |

## H

| Пункт | Статус | Что есть |
|---|---|---|
| H01 Admission: предел общей/локальной capacity, очередь target | 🔧 | лимит 128 на сервер и 512 на кластер при входе, статус живости/заполненности серверов |
| H02 Единственный session owner персонажа и reconnect policy | ✅ | сотни переходов ботов на реальных серверах: lease, синхронный save в точке прибытия, HMAC ticket, заморозка |
| H03 Freeze и durable transferable checkpoint на source | ✅ | сотни переходов ботов на реальных серверах: lease, синхронный save в точке прибытия, HMAC ticket, заморозка |
| H04 Одноразовый transfer token с персонажем, target, expiry и fence | ✅ | сотни переходов ботов на реальных серверах: lease, синхронный save в точке прибытия, HMAC ticket, заморозка |
| H05 State machine Prepare/Claim/Commit/Release/Abort/Status | 🟡 | native prepare/commit/claim + fixtures Codex; backend state machine |
| H06 Hidden target spawn, подтверждение, затем release source | ⬜ |  |
| H07 Повторы/старые tokens не дают duplicate spawn или inventory | 🟡 | native prepare/commit/claim + fixtures Codex; backend state machine |
| H08 Disconnect/crash source/target и expiry после claim | 🟡 | native prepare/commit/claim + fixtures Codex; backend state machine |
| H09 NPC/squad transit с теми же IDs и одним location owner | 🔧 | адаптер NPC transit (Codex), по умолчанию выключен |
| H10 Наблюдаемый переход реально проигрывается; ненаблюдаемый | ⬜ |  |
| H11 Ограничить ALife/GAMMA initializers своей локацией прежде, | 🟡 | release чужого generic населения проверен live (129 отрядов) |
| H12 Приёмка: 1000 переходов с аварией в каждой стадии, | 🟡 | сотни переходов без аварий; нет инъекции сбоев на каждой стадии |
| H13 Transition endpoints и безопасные destination spawn points: | 🟡 | точка прибытия из level changer; нет проверки поверхности/AOI |
| H14 Freeze/admission policy не оставляет персонажа одновременно | ✅ | сотни переходов ботов на реальных серверах: lease, синхронный save в точке прибытия, HMAC ticket, заморозка |
| H15 Понятные клиентские состояния ожидания/ошибки/reconnect, | 🟡 | автопереподключение, причины отказа по-русски |

## I

| Пункт | Статус | Что есть |
|---|---|---|
| I01 Quest state хранится вне конкретного Location Server | 🔧 | контракты контактов: состояние в общем хранилище кластера, проверка на сервере, награда ровно раз (Lua тест) |
| I02 Progression/version/CAS и авторитетная проверка условий | 🔧 | контракты контактов: состояние в общем хранилище кластера, проверка на сервере, награда ровно раз (Lua тест) |
| I03 Частично: backend authenticated location-scoped requirements pages | 🟡 | backend quest state/CAS/requirements |
| I04 Quest NPC связан с существующим PersistentID, без клонирования | ⬜ | в engine: задания чужой карты заморожены, generated с целью на другой карте отменяются |
| I05 Offline death/migration согласованы с заданием | ⬜ | в engine: задания чужой карты заморожены, generated с целью на другой карте отменяются |
| I06 Reward transaction идемпотентна и не выдаёт награду повторно | 🔧 | контракты контактов: состояние в общем хранилище кластера, проверка на сервере, награда ровно раз (Lua тест) |
| I07 Приёмка Кордон→Юпитер, рестарт destination, конкурирующие | ⬜ | в engine: задания чужой карты заморожены, generated с целью на другой карте отменяются |

## J

| Пункт | Статус | Что есть |
|---|---|---|
| J01 Единая WeatherState/seed/transition timeline из World Service | 🔧 | погода кластера из общего календаря: цикл по часу, одинаковый на всех серверах (Lua тест) |
| J02 Локальные модификаторы и interpolation относительно WorldTime | 🔧 | погода кластера из общего календаря: цикл по часу, одинаковый на всех серверах (Lua тест) |
| J03 Публикация изменений без отправки погоды каждый frame | 🔧 | погода кластера из общего календаря: цикл по часу, одинаковый на всех серверах (Lua тест) |
| J04 EmissionID и расписание warning/start/peak/end заранее | 🟡 | общее детерминированное расписание выброса кластера (код + Lua тест) |
| J05 Late join/restart восстанавливают правильную фазу выброса | 🔧 | рестарт посреди выброса продолжает его с той же фазы (Lua тест) |
| J06 Shelter graph и estimated arrival для NPC/групп | ⬜ |  |
| J07 Полный AI рядом; математическое укрытие/последствия далеко | ⬜ |  |
| J08 Idempotent damage/death/anomaly/artifact effects одного выброса | 🟡 | фаза выброса для поздно вошедших и урон один раз на владельца (fixture) |
| J09 Отмена stale abstract effect при переходе к наблюдаемой симуляции | ⬜ |  |
| J10 Приёмка двух location servers, restart на каждой фазе, | ⬜ |  |

## K

| Пункт | Статус | Что есть |
|---|---|---|
| K01 Частично: backend scheduler/arrival/durable planning windows; | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K02 Частично: backend analytic route/start/arrival/speed; engine adapter нужен | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K03 Частично: backend GroupState хранит конкретных членов/потери; | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K04 Частично: backend actual member contacts и configured mutation | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K05 Детерминированный seed из world/event/chunk/day и simulation version | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K06 Результат фиксируется до применения и не зависит от первого игрока | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K07 Потери, ранения, ammo/medical расход, победители и контроль точки | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K08 EventRecord содержит участников, время, результат и evidence | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K09 После прихода игрока появляются сохранённые последствия: | ⬜ |  |
| K10 Дальний звук привязан к реальному событию, направлению и дистанции | ⬜ |  |
| K11 Косметические blood/shell effects отдельно от persistent loot | ⬜ |  |
| K12 Частично: bounded backend catch-up и captured-time continuation; | 🟡 | backend offline scheduler/routes/encounters (Codex); engine adapter нет |
| K13 Full↔Coarse boundary у события не разрешает бой дважды | ⬜ |  |
| K14 Приёмка: 20 минут без игроков, другой первый наблюдатель, | ⬜ |  |

## L

| Пункт | Статус | Что есть |
|---|---|---|
| L01 Abstract Anomaly State с ID/type/position/radius/intensity, | ⬜ |  |
| L02 Anomaly prewarm создаёт gameplay volumes до replication; | ⬜ |  |
| L03 Route anomaly risk учитывает опыт, faction, экипировку и знания NPC | ⬜ |  |
| L04 Детерминированные offline anomaly injuries/deaths/item consequences | ⬜ |  |
| L05 ArtifactID и одно authoritative состояние world/inventory/container | ⬜ |  |
| L06 ArtifactSpawnEvents после EmissionEnd определяются заранее, | ⬜ |  |
| L07 Safe deterministic artifact placement при hydration | ⬜ |  |
| L08 NPC ищут артефакты offline с equipment/experience/danger/task | ⬜ |  |
| L09 Артефакт остаётся у NPC, затем в corpse inventory после смерти | ⬜ |  |
| L10 GroundLootCluster уменьшает число активных entities; | ⬜ |  |
| L11 Safe ground placement: поверхность, rotation и downward validation; | ⬜ |  |
| L12 Persistent stash: содержимое, lock/owner/version/discovery/quest links | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L13 Loot seed фиксируется при создании; открытие/рестарт не reroll | ⬜ |  |
| L14 Частично: backend route discovery/редкость/общие contact reserves | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L15 Stash access: PlayerOnly/QuestProtected/NPCAccessible/FactionAccessible | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L16 Scavenging ограничен carry capacity/needs/value/faction; | ⬜ |  |
| L17 Смена оружия NPC оставляет прежнее оружие с тем же item identity | ⬜ |  |
| L18 Containers имеют authoritative inventory/owner/lock/version; | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L19 Corpse: entity ID, death time/cause, inventory и quest association | ⬜ |  |
| L20 Ragdoll→static→abstract corpse без постоянной удалённой physics | ⬜ |  |
| L21 Частично: native online/offline detach и backend cleanup есть; | 🟡 | backend corpse batches; TTL отключены; живые NPC сохраняются в мире (save теперь работает) |
| L22 Loot generation policy зависит от world events/economy/выброса, | ⬜ |  |
| L23 Mutant territory/food/aggression/migration/species relations | ⬜ |  |
| L24 Persistent dens/nests, food/threat/capacity; автопополнение | ⬜ |  |
| L25 Лёгкая экология меняет опасность маршрутов и события без Full AI | ⬜ |  |
| L26 Trader money/inventory/supply/demand/restock с configurable economy | ⬜ |  |
| L27 Поставки/караваны/редкость связаны с world events и ledger | ⬜ |  |
| L28 Campfire active/fuel/start/end: состояние рассчитывается по времени; | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L29 Door open/lock/destroyed state сохраняется и влияет на offline route | ⬜ |  |
| L30 Важные destructibles сохраняют INTACT/DAMAGED/DESTROYED | ⬜ |  |
| L31 Trap owner/type/armed/charges и offline trigger с version check | ⬜ |  |
| L32 Persistence/Simulation/Replication classes реализованы в общих policies | ⬜ |  |
| L33 Event связи emission→artifacts→NPC→trade, mutants→routes→loot, | ⬜ |  |
| L34 Частично: штатный smart-terrain/SMR NPC/mutant replenishment | ✅ | spawners night/guards/bounty и replenishment отключены (live лог) |
| L35 Сохранить полное состояние живых NPC/мутантов при restart | 🟡 | backend corpse batches; TTL отключены; живые NPC сохраняются в мире (save теперь работает) |
| L36 Частично: release_item_manager и native inventory/weapon/grenade | 🟡 | backend corpse batches; TTL отключены; живые NPC сохраняются в мире (save теперь работает) |
| L37 Новое наполнение тайников: редко, обычные consumables/materials/ammo; | 🟡 | мебель/тайники/визиты в тайники/костры в серверном Lua (цикл заработал только 2026-10-06) |
| L38 Проверить цепочку artifact→NPC→corpse→player→trader→player | ⬜ |  |

## M

| Пункт | Статус | Что есть |
|---|---|---|
| M01 Метрики frame p50/p95/p99/max: AI/physics/replication/IO отдельно | 🟡 | метрики кадра avg/max, профиль ai/replication/items |
| M02 Metrics по LOD/chunks/online entities и очереди hydration | ⬜ |  |
| M03 Prewarm latency/deadline и достаточный reserved budget | ⬜ |  |
| M04 При перегрузке сначала дальняя replication/Reduced/Coarse, | ⬜ |  |
| M05 Bounded backlog, event age, admission limits и cooldown возврата качества | ⬜ |  |
| M06 Тесты 32/64/128 настоящих игровых sessions в hot location | 🟡 | 16 ботов на сервер; нужно 32/64/128 |
| M07 512 sessions по 25 локациям; пустые локации остаются abstract, | 🟡 | план кластера на все 33 карты (порты, стартовые точки, лимиты), сторож по плану; нужна многомашинная установка и боты |
| M08 Суточный сценарий NPC/loot/stashes/emission/trade/transfer | ⬜ |  |
| M09 Инварианты zero duplicate IDs/one owner, bounded RSS/backlog, | ⬜ |  |
| M10 Сравнить плотный и рассредоточенный сценарии с legacy baseline; | ⬜ |  |
