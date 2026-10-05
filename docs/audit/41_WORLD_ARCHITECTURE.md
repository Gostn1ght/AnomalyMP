# 41. Архитектура живого мира: World Service, серверы локаций, Simulation LOD

ТЗ владельца 2026-10-05 (62 пункта). Главный принцип:
**полная симуляция только там, где её кто-то может наблюдать**; всё
остальное живёт на более дешёвом уровне и плавно, заранее переходит
обратно. Различаются четыре вещи: **существование** (EXISTENCE),
**симуляция**, **репликация** и **отрисовка**.

Документ — проект и план реализации. Порядок работ — снизу вверх
(§27 ТЗ): часы → состояние мира → сервер локации → чанки/AOI → LOD →
владение сущностями → хранение → переходы → квесты → погода/выброс →
продвинутая офлайн-симуляция.

---

## 0. С чего начинаем (что уже есть в движке и в netcoop)

| Есть | Где | Как используем |
|---|---|---|
| X-Ray ALife: каждый объект мира существует как серверная сущность (`CSE_*`), онлайн (игровой объект, ИИ, физика) или офлайн (только данные). Офлайн-отряды ходят по графу локаций, смарт-террейны дают им задачи, ALife умеет сохраняться/загружаться целиком | `alife_*`, `sim_board` GAMMA | **Готовый LOD 2/3 внутри локации** и формат снимка мира. Не переписываем — оборачиваем |
| Онлайн/офлайн по расстоянию до **ближайшего игрока**, гистерезис `online_distance` / `offline_distance` | `alife_dynamic_object.cpp` (`netcoop_nearest_actor_distance`) | Основа Chunk/LOD-менеджера; расширяем до 4 уровней и prewarm |
| Сервер — авторитет: урон, лут, торговля, предметы с uid и версиями, транзакции переноса, сохранение персонажей | этапы 1–8 (док 40) | Переносится без изменений в Location Server |
| Модуль «мастер» внутри сервера (план 38 §6): выброс ведёт сервер (`netcoop_emission.script`), часы мира не останавливаются без игроков | `netcoop_*` | Становится World Service (сначала модулем, потом процессом) |
| AOI по дистанции в рассылке снимков, частота по дистанции у физики | `xrServer::SendGameUpdateTo`, `server_physics_update` | Interest Management |
| Частота ИИ по расстоянию до игроков | `CCustomMonster::shedule_Scale` (этап 12) | Основа LOD 0/1 |

**Чего нет и что критично:**
- сервер стартует каждый раз с **новой игрой** (`server(.../alife/new/...)`):
  мир между перезапусками не сохраняется вовсе (ни NPC, ни трупы, ни
  тайники) — нарушены §20–21;
- одна локация на процесс есть, но **нет** второй локации, сервиса мира,
  перехода между процессами;
- нет уровня LOD 1 (дешёвый онлайн) и prewarm: онлайн включается по
  дистанции `online_distance` (~150–200 м), а видно с оптикой до ~1000 м;
- офлайн ALife сжимает время («тикает» отряды каждый апдейт), но не
  делает **catch-up по событиям** и не записывает World Event Records.

---

## 1. Схема сервисов

```
                       ┌──────────────────────────────┐
                       │ Gateway / Auth (уже: логин,  │
                       │ Firebase, роли)               │
                       └──────────────┬───────────────┘
                                      │ Transfer Token
┌─────────────────────────────────────▼──────────────────────────────────┐
│                         WORLD SERVICE (мастер)                          │
│  WorldClock │ WorldState │ Weather │ Emission │ Factions/Territory │    │
│  GlobalEvents │ SquadTravel (межлокационные отряды) │ WorldSeed         │
├───────────────┬───────────────┬────────────────┬───────────────────────┤
│ Quest Service │ Player Persist│ Transfer/Session│ Persistence DB        │
└───────┬───────┴───────┬───────┴────────┬───────┴──────────┬────────────┘
        │       Event / Message Bus (надёжная очередь, номера сообщений)
┌───────▼───────┐ ┌──────▼────────┐ ┌─────▼─────────┐        ┌▼───────────┐
│ Location      │ │ Location      │ │ Location      │  ...   │ до 25+     │
│ Server: Marsh │ │ Server:Cordon │ │ Server:Garbage│        │ процессов  │
│ ─ Chunk Mgr   │ │               │ │               │        │            │
│ ─ LOD Mgr     │ │               │ │               │        │            │
│ ─ AOI/Repl.   │ │               │ │               │        │            │
│ ─ ALife (LOD2)│ │               │ │               │        │            │
│ ─ Entities    │ │               │ │               │        │            │
└───────┬───────┘ └───────────────┘ └───────────────┘        └────────────┘
        │ SteamNet (GameNetworkingSockets), до 128 игроков на процесс
     Клиенты
```

**Этап 1 развёртывания (сейчас):** World Service, Quest, Player
Persistence, Transfer — модули внутри процесса сервера с интерфейсами
`IWorldService`, `IQuestService`, `IPlayerStore`, `ITransferService`;
шина — очередь в памяти с тем же форматом сообщений. **Этап 2:** World
Service — отдельный процесс (тот же код, транспорт TCP + надёжные номера
сообщений), Location Server на каждую локацию.

## 2. Ответственность сервисов

| Сервис | Authority для | НЕ отвечает за |
|---|---|---|
| World Service | WorldTime, календарь, WorldSeed, погода (глобальное состояние и переходы), выбросы и пси-штормы, глобальные события, отношения группировок между собой, контроль территорий, межлокационные отряды (в пути между локациями), экономика (если включена), реестр уникальных NPC | позиции NPC, пули, физика, анимации, тики ИИ, движение игроков |
| Location Server | всё внутри локации: сущности, ИИ, физика, урон, лут, предметы, контейнеры, трупы, аномалии, LOD чанков, репликация игрокам, локальный catch-up | глобальное время (только локальная экстраполяция), чужие локации |
| Quest Service | квесты на игрока, прогресс, уникальные квестовые сущности (какая локация ими владеет) | исполнение ИИ квестового NPC |
| Player Persistence | персонаж: инвентарь (с uid), деньги, ранг, репутация/отношения на игрока, статистика, локация/позиция, тайник | живой актор в мире |
| Transfer/Session | владение персонажем (какой процесс), токены перехода, идемпотентность | содержимое персонажа |
| Persistence DB | хранение снимков и журналов событий | логика |
| Event Bus | доставка сообщений с номерами, повтор, подтверждение | смысл сообщений |

---

## 3. Классы сущностей (§59) — одна таблица вместо отдельной системы на тип

Каждый тип объекта получает три класса (поле в конфиге секции
`netcoop_persistence/simulation/replication`, с умолчанием по классу движка):

| Тип | Persistence | Simulation | Replication |
|---|---|---|---|
| Пуля, гильза, частицы | EPHEMERAL | FULL_ONLY | NEAR |
| Обычный NPC, мутант | PERSISTENT | LOD_CAPABLE | VISIBLE |
| Уникальный NPC | CRITICAL | LOD_CAPABLE | VISIBLE |
| Отряд/стая | PERSISTENT | ABSTRACTABLE | — (через членов) |
| Артефакт | PERSISTENT | ABSTRACTABLE | VISIBLE |
| Квестовый предмет | CRITICAL | ABSTRACTABLE | OWNER_ONLY/VISIBLE |
| Предмет на земле (Tier 0–3, §33) | CRITICAL…TEMPORARY | ABSTRACTABLE | VISIBLE |
| Контейнер, тайник | PERSISTENT | EVENT_ONLY | VISIBLE |
| Труп | PERSISTENT (decay) | ABSTRACTABLE | VISIBLE |
| Аномалия | PERSISTENT | LOD_CAPABLE | VISIBLE |
| Дверь, разрушаемый объект, костёр, ловушка | PERSISTENT | EVENT_ONLY | VISIBLE |
| Погода, выброс | PERSISTENT | EVENT_ONLY | GLOBAL |

Правило §61: объект находится на **самом дешёвом представлении**,
достаточном для текущей ситуации:
`DB/abstract → prewarm → server entity (не реплицируется) → replicated → full interactive → inventory data`.

---

## 4. Simulation LOD

### 4.1 Уровни

| LOD | Где | Что работает | Представление | Частота |
|---|---|---|---|---|
| **0 Full** | чанки в радиусе R0 от любого игрока (по умолчанию 0–250 м) и бой с участием игрока | ИИ, восприятие, путь, бой, физика, анимации сервера, аномалии с уроном | онлайн-объект | ИИ 10–30 Гц (planner `t_min`), физика 20 Гц |
| **1 Reduced** | R0–R1 (250–800 м) **и** открытые сектора видимости до R1o (до 1200 м, §24) | движение по маршрутам, патруль, смена точек, упрощённые стычки; восприятие раз в 0,5–1 с, путь из кэша/по графу, без баллистики на сервере (стрельба — по таблице попаданий), без серверных анимационных вычислений | онлайн-объект в «дешёвом режиме» | ИИ 1–5 Гц |
| **2 Coarse** | дальше R1 внутри локации, где нет игроков | отряд = одна запись: состав, ресурсы, маршрут, задача; движение аналитически; стычки — детерминированный encounter | офлайн ALife-отряд + `GroupState` | событийно; планировщик ≤ 1 Гц на отряд |
| **3 Statistical** | локации без игроков; очень далёкие чанки | популяции, логова, отряды в пути, таймеры, события по расписанию | числа и события | только запланированные события |

Все радиусы — конфиг `configs/netcoop/simulation_lod.ltx`, подбираются по
профилю (`[profile]`). Главное неравенство: **R_prewarm > R1 ≥ дистанция
наблюдения (с оптикой) > R0**.

### 4.2 Чанки

- Локация делится на квадратные ячейки 100×100 м (`ChunkId = (level, ix, iz)`);
  размер — конфиг; ячейка хранит списки сущностей (переиспользуем
  индекс уровня `level_graph` по вершинам → ячейка).
- **Видимость сектора (§24):** при сборке уровня (оффлайн-утилитой) для
  каждой пары ячеек считается приблизительная видимость по карте высот
  (несколько лучей по `level_graph`/`ObjectSpace` между центрами и
  верхними точками) → `VisibilityPVS[chunk] = список ячеек, видимых с
  открытой местности до 1200 м`. Хранится файлом рядом с уровнем; в игре —
  только чтение. NPC за горой в 900 м остаётся Coarse, на открытом поле —
  Reduced.

### 4.3 Желаемый LOD чанка

```
desired(chunk) = min over players p of:
  dist(p, chunk) < R0                          -> 0
  dist(p, chunk) < R1 || chunk in PVS(p.chunk) && dist < R1o  -> 1
  chunk in prewarm_set(p)                      -> PREWARM (цель 1)
  else                                          -> 2 (3 если в локации нет игроков)
combat(chunk) с участием игрока               -> 0
```

`prewarm_set(p)` (§7): ячейки по направлению движения на
`v·T_prewarm + R1` вперёд (T_prewarm 20–40 с), соседи текущей, ячейки,
видимые с точки, куда игрок придёт (высоты). Направление камеры/оптика —
только подсказка: увеличивает радиус в конусе взгляда до R1o, никогда не
уменьшает (клиент не может «выключить» мир).

### 4.4 Переходы и гистерезис (§8, §23)

```
COARSE --(desired<=1)--> PREWARM --(hydrated, AI started)--> REDUCED --(desired 0)--> FULL
FULL --(desired>=1, 10 s)--> REDUCED --(desired>=2, 60-120 s)--> COARSE --(no players in location, 10 min)--> STATISTICAL
```
- Повышение — сразу; понижение — после выдержки (cooldown по уровню), и
  только если ни один игрок не вернулся.
- Граница «мягкая»: решение принимается по объекту, а не по ячейке
  (сущность, вышедшая из ячейки с LOD 0, остаётся LOD 0, пока не
  удалится на R0 + 50 м). Нет NPC, «появившихся на границе».
- **Never wake visibly (§6):** сущность не реплицируется игроку, пока её
  чанк не прошёл PREWARM; репликационный радиус ≤ R1 < R_prewarm.

### 4.5 Менеджер LOD (Location Server)

- Данные в RAM: `ChunkState { id, lod, target_lod, since, last_sim_time,
  entity_ids[], groups[] }`, ~1000 ячеек на локацию.
- Пересчёт желаемых LOD: 5 Гц (позиции игроков из кэша), переходы
  выполняются с бюджетом (не более N гидраций за кадр, по приоритету
  ближайших к игрокам).
- Метрики: число ячеек по уровням, время гидрации, очередь prewarm.

---

## 5. Гидрация / дегидрация (§8)

```
HYDRATION (чанк в PREWARM):
  1 load persistent state (из RAM-кэша локации или БД)
  2 abstract state: группы, популяции, трупы, кластеры лута, аномалии
  3 CatchUp(chunk, last_sim_time -> now)   // §58, по событиям
  4 positions = route.at(now)               // аналитически
  5 materialize entities (ALife switch_online + safe placement)
  6 assign routes/tasks, restore health/ammo/inventory
  7 start Reduced AI
  8 mark chunk REDUCED -> replication allowed
DEHYDRATION (после cooldown):
  Full -> Reduced (AI дешевле) -> GroupState (позиции -> маршрут+прогресс,
  ресурсы, раненые) -> ALife offline -> Statistical (популяции/таймеры)
```
- Материализация группы: члены ставятся вдоль маршрута около
  `route.at(now)` в «строю» (формация по seed), на валидных вершинах
  `level_graph`, вне поля зрения игроков, если возможно.
- Важное при сворачивании не теряется: трупы → CorpseState, предметы →
  GroundLootCluster (с индивидуальным состоянием ценных), раненые →
  поле `wounded` группы.

## 6. Catch-up и детерминизм (§10, §58)

```
CatchUp(chunk, t0, t1):
  events = scheduler.events(chunk, t0, t1)  sorted by time    // O(важных событий)
  for e in events: apply(e)                                    // прибытия, encounters,
                                                                // выбросы, спавны артефактов,
                                                                // decay трупов/лута, логова
  for g in groups(chunk): g.position = g.route.at(t1)
  population.regen(t0, t1) analytically (logistic)
  chunk.last_sim_time = t1
```
- Встречи групп в офлайне находятся **аналитически**: пересечение
  маршрутов во времени (отрезки движения с временами входа/выхода в
  ячейку) → событие `Encounter(t)` ставится в расписание при старте
  движения, а не ищется каждый тик.
- `Seed = Hash64(WorldSeed, EventID, ChunkID, WorldDay)`; генератор
  внутри события — xoshiro256** от seed. Результат зависит только от
  состояния и seed, не от того, кто пришёл первым и на каком сервере.
- Результат события пишется как **World Event Record** до применения
  последствий (журнал → состояние), повторное применение того же EventID
  — no-op (идемпотентность).

## 7. Offline-группы, encounter, аномалии, артефакты (§3, §29–32, §45–47, §55)

`GroupState { id, kind(squad|pack), faction/species, members[{npc_id,
health, wounded, inventory_ref}], resources{ammo, med, food}, strength,
route{nodes[], t_start, speed}, task, destination, seed, last_update }`
- `strength = Σ(rank_k · health) · equipment · ammo_factor`; Encounter:
  вероятности исхода из отношения сил, детерминированный бросок по seed,
  потери распределяются по членам, ресурсы списываются, создаются
  Evidence (трупы с реальным инвентарём, оружие) и EventRecord.
- Маршрут = путь по графу локаций с весами `distance + risk·k(npc)`,
  `risk` из AnomalyField/логов мутантов/территорий; опытные и хорошо
  экипированные выбирают безопаснее (§29). Проход через поле аномалий →
  событие `GroupEnteredAnomalyField` (ранение/смерть/потеря предметов по seed).
- Артефакты: `ArtifactState` в одном месте (`WORLD`/`NPC_INVENTORY`/…),
  рождаются из `ArtifactSpawnEvent` после выброса (сектор поля + seed),
  точная позиция определяется при гидрации допустимым размещением в
  секторе. Офлайн-поиск: событие при проходе группы рядом с полем
  (`DetectionChance` по опыту/детектору) → атомарный перенос `WORLD → NPC_INVENTORY`.
- Мутанты: `PackState` с территорией, голодом, агрессией; логова
  `Nest { species, population, capacity, regen_rate, last_update }`;
  убийства игроков уменьшают популяцию, восстановление — аналитическое.
- Выброс (§55): при `EmissionWarning` каждая группа выбирает достижимое
  укрытие (граф + время), ставит событие прибытия; не успела → потери по seed.

## 8. Interest Management и репликация (§12)

- Пространственная сетка = чанки. Для игрока `relevant = чанки с LOD ≤ 1
  в радиусе репликации Rrep(p)`; `Rrep` = 250 м, в конусе взгляда с
  оптикой — до R1o (только для уже прогретых чанков).
- Частота снимка объекта: < 50 м — каждый тик (30 Гц), 50–150 м — 15 Гц,
  150–400 м — 5 Гц, дальше — 1–2 Гц с интерполяцией; ничего за Rrep.
  Уже есть основа в `SendGameUpdateTo` + `server_physics_update`.
- Приоритеты при нехватке канала: игроки и бой рядом > NPC рядом >
  видимые дальние > предметы > декор (§22).
- Дальний бой без гидрации: `DistantGunfire{direction, distance,
  intensity, event_id}` — звук только для реального события (§53).
- Состояние предметов (этап 1) и транзакции (этап 2) уже в этой модели.

## 9. Владение сущностями и anti-duplication (§42, §57)

- Каждая persistent сущность имеет `uid (u64)` и **одно место**:
  `Location{WORLD(chunk)|PLAYER:id|NPC:id|CONTAINER:id|CORPSE:id|STASH:id|TRADE:id|TRANSFER:token|DESTROYED}` и `version`.
- Любой переход — транзакция: `BEGIN(txid) → проверка места и версии →
  запись нового места, version+1 → журнал → COMMIT`; повтор txid — ответ из
  журнала. Уже сделано внутри процесса для переносов/торговли (этапы 2, 4).
- Межпроцессное владение: сущность может принадлежать **одному**
  Location Server (поле `owner_server` + `lease_until`); передача —
  двухфазная через World Service (см. §12 переходы).
- Уникальные NPC: реестр в World Service (`UniqueNPC { uid, alive,
  location, owner_server, version }`); материализовать может только
  сервер-владелец; клон невозможен, потому что второй сервер не получит
  lease.

## 10. Глобальное время (§16)

- World Service: `WorldTime = epoch_world + (mono_now - epoch_mono) ·
  scale`; меняется только командами (смена scale при выбросе, сон) с
  записью в журнал.
- Location Server хранит `{AuthoritativeWorldTime, LocalMonotonic, Scale,
  Seq}`; синхронизация `ClockSync` раз в 5 с (и при смене scale);
  локальное время считает сам; расхождение < 2 с исправляется
  **сглаживанием** (скорость ±5 %), больше — скачок с событием `TimeJump`
  (только при восстановлении после сбоя).
- Клиенты: то же от своего Location Server (уже есть сглаживание часов
  клиента, коммит 17c7f5a).
- Хранение: `world_clock(epoch_world, scale, saved_at)` в каждом снимке
  мира; после перезапуска время продолжается с сохранённого, плюс (по
  конфигу) прошедшее реальное время.

## 11. Погода и выброс (§14, §15)

- Погода: World Service хранит `WeatherState { seed, current, target,
  transition_start, transition_end, wind, fog, clouds }` на Зону; локация
  применяет локальные модификаторы (`level_weathers`), промежуточное
  состояние считает сама из WorldTime. Сообщение `WeatherChanged` только
  при смене цели.
- Выброс: `EmissionScheduled { id, warning_start, start, peak, end, seed,
  intensity }` заранее всем Location Server; каждый воспроизводит фазу по
  WorldTime; после перезапуска восстанавливает фазу из состояния.
  Последствия (смерти вне укрытий, артефакты, изменение аномалий,
  повреждение предметов, миграции) — World Events.
- Сейчас выброс ведёт `netcoop_emission.script` внутри сервера — переносим
  в модуль World Service с тем же сообщением.

## 12. Переходы игроков и NPC (§18, §19)

Игрок A → B:
```
A: freeze player (no input), flush item reports, serialize character (uid-инвентарь)
A -> Transfer: PrepareTransfer{player, from=A, to=B, character_blob, version}
Transfer: write {token, state=PREPARED, expires}, character.owner = TRANSFER(token)
Transfer -> A: TransferToken ; A -> client: Reconnect{B, token}
client -> B: Join{token}
B -> Transfer: Claim{token}  (CAS PREPARED -> CLAIMED by B, version check)
B: load, spawn, -> Transfer: Confirm{token}  (CLAIMED -> DONE, owner=B)
Transfer -> A: Release{player}  (A удаляет актор без сохранения)
```
- Повтор любого шага с тем же token — тот же ответ. Истёкший токен
  (клиент не дошёл за 60 с) → откат: owner = A, игрок возвращается в A.
- Двойной спавн невозможен: Claim — CAS, второй Claim получает отказ.
- NPC/отряд: если у границы нет игроков — абстрактный переход
  (`SquadTravel{squad, from, to, depart, arrive}` в World Service, на время
  пути отряд принадлежит World Service); если есть — отряд материализован
  и реально проходит переход, затем тот же протокол передачи владения.

## 13. Квесты (§17)

- Quest Service: `PlayerQuest { player, quest_id, stage, data, version }`,
  `QuestEntity { uid, quest_id, location, owner_server }`.
- Выдача на Кордоне: Quest Service создаёт запись и, если нужен
  уникальный NPC на Юпитере, регистрирует требование
  `RequireEntity{uid, location=Jupiter}`. Location Server Юпитера при
  гидрации проверяет реестр и материализует ровно один экземпляр (lease).
- Прогресс меняет только сервер, где произошло событие, через
  `QuestProgress{player, quest, from_stage, to_stage, txid}` (CAS по stage).
- Сейчас задания на игрока ведёт сервер (`server_tasks_update`) — это
  будущий модуль Quest Service.

## 14. Persistence (§20, §21)

- Persistent: см. таблицу §3. Ephemeral не пишется никогда.
- Схема хранения (SQLite на процесс на первом этапе → PostgreSQL при
  выносе сервисов):
  - `world_snapshot(location, seq, world_time, blob)` — снимок ALife
    локации (готовый формат сохранения движка) + наши таблицы;
  - `world_event(event_id, location, chunk, world_time, type, payload, applied)` — журнал после снимка;
  - `entity(uid, class, location_kind, location_id, version, state_blob)`;
  - `group_state`, `corpse`, `ground_cluster`, `container`, `stash`,
    `artifact`, `nest`, `door`, `campfire`, `trap` — по таблице на тип;
  - `player(character, owner_server, version, blob)`, `transfer(token, …)`,
    `player_quest`, `quest_entity`.
- Снимки: раз в 5 мин и при сворачивании локации, в фоне (как сохранения
  персонажей — запись во временный файл, fsync и замена в потоке).
- Важные события пишутся сразу (журнал), до применения.

## 15. Crash recovery и перезапуск (§21, §24 п.24)

```
start: load last snapshot -> replay world_event where seq > snapshot.seq
       -> WorldService.GetState (time, weather, emission, territories)
       -> CatchUp all chunks to WorldTime (событийно)
       -> accept players
```
- Перезапуск сервера сам по себе **не** респавнит лут (§43) и не
  создаёт мир заново: старт с `alife/load` последнего снимка вместо `new`.

## 16. Перегрузка и деградация (§22)

Бюджет кадра делится по приоритетам: LOD 0 и бой у игроков не
урезаются; при превышении целевого кадра (P95 > 33 мс) по очереди:
LOD 1 ИИ 5→2 Гц → гидрация prewarm медленнее (но не отменяется) →
LOD 2 только событийно → LOD 3 только расписание. Метрики `[profile]`
показывают, какой уровень урезан. Возврат — с гистерезисом.

## 17. Масштаб до 512+

- 25 локаций × до 128 игроков на процесс; World Service — один процесс
  (нагрузка — события и часы, не тики); при необходимости шард по
  регионам для Quest/Player.
- Мощные локации (Кордон, Бар) — отдельные машины; пустые локации —
  несколько процессов на машину или «спящий» режим (только расписание
  LOD 3 в World Service, без запущенного Location Server).
- Нагрузочные тесты: боты `netcoop_bots` (есть) 32/64/128 на процесс,
  20/50/100/300 NPC, P95 кадра, ms ИИ/репликации, трафик на игрока.

## 18. Остальные объекты мира (§33–44, §49–54)

| Объект | Состояние | Офлайн | При гидрации |
|---|---|---|---|
| Предметы на земле | Tier 0–3; `GroundLootCluster{chunk, sector, stacks, important_uids}` | Tier 2/3 по времени жизни; Tier 3 агрегируется сразу | раскладка с безопасным размещением: сохранённая позиция → проверка опоры → короткий луч вниз → свободное место (§35) |
| Тайник | `StashState` + доступ PlayerOnly/QuestProtected/NPCAccessible/FactionAccessible | процедурное содержимое фиксируется seed при создании | как есть |
| Контейнер | `Container{id, version, inventory, lock, owner, respawn_policy}` | респавн только по политике (NONE/TIME/EMISSION/EVENT/ECONOMY) | как есть |
| Труп | `CorpseState{orig_uid, faction, death_time, cause, inventory, important, decay}` | Fresh→Old→Remains→Cleanup, перед удалением — судьба лута (ценное в кластер, часть — офлайн-мародёрам) | статичное тело на месте смерти, рэгдолл только рядом |
| Костёр | `{id, active, fuel, start, expected_end}` | ничего | горит, если now < end |
| Дверь/разрушаемое | `{id, open, locked, destroyed, last}` | маршрут учитывает | в правильном состоянии |
| Ловушка | `{id, owner, armed, charges, expiration}` | офлайн-срабатывание событием | материализуется |
| Аномалия | `AnomalyState{id, type, chunk, pos, radius, intensity, active, cooldown, last_activation, artifact_state, seed, emission_cycle}` | без коллизий и урона | объёмы обнаружения, логика урона на сервере, эффекты на клиентах |
| Торговец | `TraderState{money, inventory, supply, demand, restock}` | поставки событиями (караваны/экономика, отключаемо) | как есть |
| Evidence | от события: трупы/оружие — persistent; кровь/гильзы — косметика только у игроков | — | создаются по EventRecord |

---

## 19. Сообщения (сводка)

| Сообщение | От → кому | Когда | Надёжность |
|---|---|---|---|
| `ClockSync{seq, world_time, mono, scale}` | World → Location, Location → клиенты | 5 с, при смене scale | ненадёжно, последнее важно |
| `WorldStateSnapshot{time, weather, emission, territories, relations}` | World → Location | подключение/перезапуск | надёжно |
| `WeatherChanged`, `EmissionScheduled/Phase`, `GlobalEvent` | World → Location | при событии | надёжно, с seq |
| `SquadDeparture{squad, to, depart, arrive, state}` / `SquadArrival` | Location ↔ World | переход отряда | надёжно, идемпотентно по squad+seq |
| `EntityLeaseRequest/Grant/Release{uid, server, version}` | Location ↔ World | гидрация уникальных/квестовых | надёжно, CAS |
| `PrepareTransfer/TransferToken/Claim/Confirm/Release` | Location ↔ Transfer | переход игрока | надёжно, idempotent по token |
| `QuestProgress{player, quest, from, to, txid}` | Location → Quest | прогресс | надёжно, CAS |
| `WorldEventRecord{event_id, …}` | Location → World/DB | важное событие | надёжно, до применения |
| `DistantGunfire{dir, dist, intensity, event_id}` | Location → клиент | дальний бой | ненадёжно |

Все надёжные сообщения: `{sender, seq, idempotency_key}`; получатель
хранит последний seq отправителя; дубликаты → прежний ответ.

---

## 20. План реализации (этапы W1–W12)

Каждый этап — отдельные коммиты, сборка в CI, тест, запись в этот документ.

### W1. Мир переживает перезапуск (World State + crash recovery, база)
- Сейчас самая большая дыра: старт `alife/new`.
- **Сделать:** серверный «снимок мира» = сохранение ALife движка
  (`CALifeStorageManager::save`) раз в 5 мин и при остановке, в фоне;
  старт: если есть снимок — `alife/load`, иначе `new`. Наши таблицы
  (`netcoop_items` uid, этап 5 флаги NPC через se_save_var — уже в ALife)
  едут внутри снимка.
- Модули: `netcoop_world_store.inc` (`WorldStore::save_async/load_latest`),
  параметр сервера `-netcoop_world=<имя мира>`.
- Тест: убить NPC, выбросить предмет, перезапустить сервер — труп и
  предмет на месте; время мира продолжилось. Нагрузочный: снимок с 5k
  объектов < 50 мс главного потока.

### W2. Global World Clock
- `WorldClock { epoch_world, epoch_mono, scale, seq }`, `IWorldService::clock()`;
  хранение в снимке; `ClockSync` клиентам; сглаживание у клиента (есть).
- Pseudocode: `now() = epoch_world + (mono() - epoch_mono)·scale`;
  `set_scale(s): epoch_world = now(); epoch_mono = mono(); scale = s; seq++; broadcast`.
- Тест: перезапуск → время продолжается; смена scale при выбросе плавна;
  дрейф клиента < 0,5 с за час.

### W3. World State + модульные интерфейсы
- `IWorldService` (time, weather, emission, factions, events), `WorldStateSnapshot`;
  перенос `netcoop_emission.script` и погоды под этот интерфейс; отношения
  группировок (план 38 §7) — здесь.
- Тест: заменить реализацию на «удалённую заглушку» — локация работает.

### W4. Chunk Manager + AOI
- `ChunkGrid` (100 м), индекс сущностей по ячейкам (обновление при
  перемещении), `InterestSet(player)`; репликация по ячейкам и частоте.
- Тест: 2 игрока в разных концах — каждому идут только свои объекты;
  трафик на игрока не растёт с размером локации.

### W5. Simulation LOD Manager (0/1/2/3) + prewarm
- `SimulationLodManager`, `ChunkState`, конфиг радиусов; LOD 1 — режим
  онлайн-NPC: восприятие и планировщик реже, путь по кэшу; включение
  онлайна (ALife) по R_prewarm вместо `online_distance`, с бюджетом гидраций.
- Утилита `tools/build_visibility_pvs` (оффлайн) → PVS по уровню.
- Тест: бинокль/оптика на 800 м — NPC уже идут, никто не «просыпается»;
  уход игрока — свёртка с выдержкой; профиль: 100 NPC в LOD 1 < 2 мс/кадр.

### W6. Entity ownership (uid + место + версия) для всех persistent
- Расширение этапов 1–2 до `EntityLocation` для NPC, трупов, контейнеров,
  тайников, артефактов; журнал транзакций.
- Тест: принудительный обрыв в середине переноса → предмет ровно в одном месте.

### W7. Persistence DB (SQLite) + журнал событий
- Таблицы §14, `WorldEventLog::append/replay`, снимок + журнал.
- Тест: kill -9 сервера во время боя → после старта состояние = снимок +
  события; нет дублей.

### W8. Group simulation (LOD 2) + catch-up
- `GroupState` поверх ALife-отрядов, аналитическое движение, encounter,
  расписание событий, World Event Records, Evidence при гидрации.
- Тест: оставить два враждебных отряда на одном маршруте, уйти на 20 мин,
  вернуться — трупы, раненые, у победителя меньше патронов; результат
  одинаков при повторе с тем же seed.

### W9. Location Server как отдельный процесс + Transfer Service
- Второй процесс (Кордон), World Service отдельно, протокол перехода
  игрока с токеном, lease уникальных сущностей.
- Тест: переход Болота → Кордон 100 раз с обрывами — нет потерь и дублей.

### W10. Quest Service межлокационный
- Перенос `server_tasks_update` в модуль, `RequireEntity`, `QuestProgress` CAS.
- Тест: задание на Кордоне → NPC на другой локации ровно один.

### W11. Погода/выброс от World Service на все локации
- Выброс с последствиями как World Events: укрытия офлайн-групп,
  артефакты, изменение аномалий.
- Тест: перезапуск локации посреди выброса — правильная фаза.

### W12. Продвинутая офлайн-жизнь
- Артефакты и офлайн-поиск, мутанты/логова/экология, мародёрство трупов,
  торговля/экономика (отключаемо), кластеры лута Tier 0–3, decay.
- Нагрузочный: 25 локаций (часть «спящие»), 512 ботов, сутки мира.

---

## 21. Решения, которые нужны от владельца

1. W1: сохранять ли мир **между** запусками сервера (рекомендую — да; иначе
   «живой мир» сбрасывается при каждом рестарте) и сколько реального
   времени мир «проживает» за время выключенного сервера (0 / реальное /
   ограничено N часами).
2. База данных на первом этапе: SQLite-файл на процесс (рекомендую) или
   сразу PostgreSQL.
3. Размер чанка (100 м) и стартовые радиусы R0/R1/R_prewarm — подберу по
   профилю, но нужна целевая дальность прорисовки клиентов.
