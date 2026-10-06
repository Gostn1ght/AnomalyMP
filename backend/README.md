# Lost Zone World Backend

Модульный backend на Python 3.13 и стандартном sqlite3, без внешних
зависимостей. Это новый слой хранения и команд; текущий игровой engine
ещё не отправляет сюда свои authoritative изменения. Проверки модуля
не означают готовность межсерверных переходов в игре.

## Реализованное ядро

- Один service process на локальный DB-файл: OS lock, SQLite WAL,
  synchronous FULL, foreign keys, rollback и schema check.
- Durable WorldID/seed/epoch, monotonic calendar, event-time highwater,
  freeze downtime и непрерывная смена положительного time scale.
- Location leases с fencing/capacity; rollback local lease clock
  закрывает mutations. Это один host, без distributed election/SMB/NFS.
- Журнал с aggregate sequence; outbox, consumer ACK, atomic inbox
  и durable command results с проверкой совпадения payload.
- Entity registry и ItemLedger: одна containment-запись на вещь;
  version/access/capacity checks, постоянная смерть, все оставшиеся
  вещи corpse→ground сохраняют IDs.
- Персонажи, sessions и prepare/claim/commit/abort/status для handoff.
  Target reservation, подписанные tokens, claim recovery под новым
  location fence; claimed transfer не возвращается source по expiry.
- NPC и группы сохраняют прежние member IDs и сведения о потерях.
  Тела погибших остаются в локации смерти; с патрулём переходят живые члены.
- Consistent backend snapshot/checksum/journal watermark. Снимок
  не содержит ALife/Lua; общий engine/backend recovery впереди.

Ownership принимает доверенный server principal. Дистанция pickup,
input/combat restrictions, safe placement и hidden target spawn должны
проверяться engine adapter; backend не принимает их из player client.
Population/item creation требует проверенного bootstrap, не пересоздания
IDs при каждом подключении.

Повтор CommandID не заменяет текущую авторизацию. Location create/recover/
renew и abort проверяют действующий lease/fence до выдачи сохранённого ответа.
Entity update/death/cleanup, session disconnect/resume, quest grant/progress,
pickup и trade также проверяют текущего writer по metadata; старый source не
получает entity result после handoff, даже если его собственный lease ещё жив.
Старую CAS version и alive/session state повторно не проверяют: их мог изменить
сам уже исполненный запрос. Поэтому законный retry сохраняет прежний ответ и
не повторяет изменение. `location_claim` дополнительно сверяет сохранённый
grant fence: после expiry/takeover для нового захвата нужен новый CommandID.
Эти guards относятся к backend. Engine adapter должен сверять текущие session/
entity generations; исторический command result не является свежим snapshot.

## Проверки

```powershell
python -m unittest discover -s backend/tests -v
```

Python-тесты действительной SQLite реализации проверяют конкурирующий
pickup, потерю ACK, fence, restart, OS lock из другого процесса и
аварийное завершение процесса до/после commit. Native engine и fixtures
компилируются только в GitHub Actions.

## Следующие подключения

Локальный authenticated HTTP endpoint, private credentials, bounded worker
pool и rate limit уже реализованы. Дальше: read-only engine bridge →
согласование WorldID/clock/ownership → shadow comparisons → durable mutations.
Два несогласованных реестра/календаря не являются единым World Service.

Spatial index netcoop_spatial_grid.h подключён как диагностика
`-netcoop_chunk_shadow`: раз в 200 мс сравнивает sphere query с legacy
snapshot set; логирует `[chunk-shadow]` раз в 10 с. Пакеты, spawn, AI
и ownership не меняет. Ядро поддерживает move/erase, отрицательные
координаты, location scope, 128-bit IDs, 3D sphere/capsule query и
персональные visible/prewarm sets. Shadow adapter использует временные
engine handles, а не durable registry.

Полные Chunk Manager/LOD/hydration и handoff в работающем engine
не объявляются выполненными этим первым подключением.

## Сервис и интерфейс

Из каталога backend:

```powershell
python -m lostzone init --config runtime/config.json --location hidden_base --location cordon --location jupiter
python -m lostzone serve --config runtime/config.json
```

Init создаёт приватный config один раз и не заменяет существующие tokens.
В stdout secrets не выводятся; runtime исключён из Git. Сервис слушает
только 127.0.0.1:38477; серверы других хостов потребуют TLS/mTLS gateway.
Credentials именуют principal и явный список его локаций. Principal нельзя
назначить из request body. Player clients эти credentials не получают.

Для native shadow bridge существует отдельная роль `observer`: bootstrap/clock
доступны, mutations всегда запрещены. `init` выдаёт отдельный observer token.
Экспорт приватного файла в server userdata (не клиентский overlay):

```powershell
python -m lostzone bridge-config --config runtime/config.json --destination <server-userdata>/netcoop_world_bridge.json
```

Экспорт никогда не заменяет существующий файл и не использует admin/location
credential. Движок читает файл при запуске и получает /v1/bootstrap на worker
через WinHTTP loopback без proxy/redirect. Bounded wire parser и LocationClock
проверяют WorldID/seed/epoch/schema/sequence/holdover; main thread только
сравнивает estimate с ALife clock. `[world-bridge-shadow]` не назначает backend
владельцем и не изменяет календарь, inventory или AI. Файл конфигурации и DB
мира должны согласовывать identity отдельно; несовпадение закрывает observer.

GET /v1/clock, /v1/bootstrap; GET /v1/location?id=...&fence=...;
GET /v1/transfer?id=...; admin GET /v1/events?after=...&limit=...;
POST /v1/command: command_id (128-bit hex), operation, arguments.
Каждая mutation возвращает durable result до HTTP ACK. Ошибки 400/401/
403/409/429/503 не содержат tokens/tracebacks. Body limit=64 KiB;
16 workers, token bucket по principal. Недоступный scheduler/checkpoint
закрывает command admission до успешного восстановления.

Operations: world_scale/world_state/timeline_schedule (admin),
location_claim/renew/recover, entity_create/update/death, corpse_cleanup,
item_create/move, session_disconnect/resume, transfer_prepare/claim/commit/
abort, quest_grant/progress. World bootstrap согласован по DB transaction
с clock, state revision и journal watermark. Inbox/outbox реализованы
как внутренние интерфейсы Store; сетевой subscriber ещё предстоит.

Schema v1→v2→v3 мигрируется транзакционно, включая прежний состав групп;
неизвестная/пустая существующая DB останавливает запуск. Gameplay items
не имеют TTL. Смерть сохраняет tombstone, cleanup переносит весь corpse
loot с прежними IDs/состояниями и сохранённой drop position.

Quest definitions — доверенный config, не player-provided rewards.
Квесты используют committed objective events, stable entity links,
version/CAS и одну транзакцию награды с прогрессом. Нужные тела защищены
от cleanup. Погода/выброс — durable timelines, phases и bounded catch-up;
локальная фаза/переход рассчитываются аналитически. Damage/shelter/artifact
effects и GAMMA playback ещё не подключены к этим backend timelines.

Engine bridge должен явно согласовать WorldID/seed и adopt authority:
запуск standalone backend с новой DB не переключает игровые часы сам.

## Абстрактное движение

`dehydrate` принимает полный capture группы, CAS каждого живого
члена и сохраняет state до передачи writer в offline authority. Dead
members остаются на месте смерти. Location recovery не забирает offline
records. `route_start` (admin) задаёт bounded polyline, speed_real и seed;
позиция между событиями рассчитывается аналитически, без тиков каждого NPC.
World scale rebase сохраняет скорость в метрах за реальную секунду и
оставляет одну pending arrival. Restart замораживает downtime и меняет
offline fence, не создавая новых персонажей.

`hydrate` возвращает положение и прежнее состояние под текущим
location fence. Engine adapter должен безопасно разместить объекты,
восстановить Reduced AI и открыть replication только после готовности;
backend ownership ACK сам по себе этого не подтверждает. Пока эти
операции не вызываются действительным игровым сервером.

## Торговля и посещения тайников

Config `items` задаёт для section доверенные `category`, `price` и `weight_g`;
`traders` — именованные профили с `buy_categories`, `buy_bp`, `sell_bp`,
`min_condition_bp`. Entity торговца выбирает `trade_profile`, хранит свой
wallet и действительный inventory. `trade` с BUY/SELL сохраняет одновременно
одну ledger-запись вещи, деньги обоих участников, versions, journal и
command result. Продаётся/покупается весь stack; цена — целое число с учётом
quantity/condition. Проверяются предпочтения, средства, место и carry
capacity. `price_limit` защищает согласие с ценой; `quote_only` сохраняет
предложение без изменения предмета/денег. Частичные stacks и GAMMA UI
ещё требуют engine adapter. Пустой catalog не создаёт выдуманные цены.

Admin `stash_visit` планирует событие для offline NPC и offline STASH.
Проверяются ownership, CAS, защита тайника, положение в момент события,
редкость и capacity. По умолчанию chance=8%, cooldown=6 игровых часов;
один визит может перенести одну существующую вещь. Deposit разрешён
только для FOOD/MEDICINE/AMMO/JUNK/TOOL из доверенного catalog; оружие,
броня и артефакты исключены. Никакого генератора нового лута/respawn/TTL.
Hydration до события отменяет abstract visit. Epoch fencing при restart
не меняет семантическую revision capture; visits сохраняют frozen input.
Capture также содержит собственный маршрут и группу/маршрут группы для
идущего с отрядом NPC. Замена пути или world-scale rebase отменяет старое
событие до переноса предмета и изменения cooldown, даже если NPC всё ещё
рядом с тайником. Старые планы без motion capture отменяются.
Закрытый тайник (`entity.state.locked=true`) и тайник, связанный с активным
quest requirement, исключены из NPC visits. Проверка повторяется при
разрешении события: новый квест/замок отменяет ранее запланированный визит.
Catalog `quest_protected=true` и item.state `quest_item`/`quest_protected`
защищают конкретные вещи от автоматического take/deposit. Эти правила не
изменяют разрешения игрока; native adapter ещё должен передавать эти flags.
Общий planner теперь обнаруживает тайники вдоль действительных маршрутов NPC
и членов групп, включая formation offset. Включённая `offline_planning`
подписка ставит визит без отдельной `stash_visit` команды. Бой, опасность и
тайник конкурируют за один motion root: более ранний контакт выигрывает,
тайник также резервируется от одновременных посещений. Действительный capture
сохраняет EventID/RNG при пересчёте; исход визита запускает causal refresh.
Cooldown проверяется и у NPC, и у тайника, поэтому смена тайника не обходит
редкость. Автоматический выбор новых маршрутов/целей NPC и GAMMA adapter впереди.

Обнаружение ограничено 256 тайниками/256 NPC, 8 MiB encoded state admission,
8192 сегментами, 4096 кандидатами и общим ContactIndex work budget. Визит читает
кандидатов потоком (по 64 take/deposit) с общим 4 MiB encoded capture budget;
oversize откатывает весь исход и оставляет событие pending, без потери вещей.
Категории, запрещённые для deposit, исключаются до разбора item.state. Это
границы admission, а не измеренный предел RSS. Trusted embedding может
уменьшить `Scavenging(..., capture_limit=...)`; клиент этот лимит не задаёт.

## Дальние бои

Admin `offline_combat` сохраняет immutable encounter capture: WorldID/seed,
EventID, время, конкретные участники, revisions, враждебность и состояние
оружия из ItemLedger. `relations` в WorldState задаёт hostile faction pairs;
другой observer, повтор или restart не становятся входом RNG. Coarse model
ограничен 64 бойцами на сторону и 64 inventory items на бойца. Он учитывает
индивидуальное здоровье/опыт, condition и power оружия из catalog, записывает
ранения и расход действительных magazine rounds, death tombstones, corpse
loot и durable evidence одной транзакцией. Пустой погибший отряд не движется;
состав с casualty IDs сохраняется. Hydration/смена capture/отношений отменяет
абстрактный бой до damage. Нет тиков пуль и нового population.

Это baseline resolver, требующий настройки баланса и engine адаптера.
Admin `offline_contact` принимает пару кандидатов, их revisions, seed,
`horizon_ms` (1..86 400 000 игровых мс) и radius (0.1..200 м). Он вычисляет
первое сближение по непрерывным 3D маршрутам, включая повороты и неподвижную
сторону, и сохраняет тот же combat capture в одной транзакции. Далёкие
конечные точки не скрывают пересечение между ними; разные высоты учитываются.
Работа ограничена 1024 сегментами на маршрут, без тиков каждого NPC.
Route version/active state входят в capture: world-scale rebase отменяет
старый план до damage/ammo, а restart без изменения маршрута сохраняет его.
Планы старой версии без route capture отменяются консервативно.

Admin `offline_contacts` выполняет один проход по offline roots локации
(`location`, `horizon_ms`, `seed`, `radius`). 3D corridor index по ячейкам
отбирает только пространственно и во времени пересекающиеся сегменты, затем
continuous narrow phase вычисляет действительное сближение. Для групп индекс
использует пути живых членов со смещением и поворотами; пары внутри одной
группы исключены. Контакт резервирует group root один раз, а не каждого бойца
как отдельный отряд. Пересечение только центров групп не создаёт бой, если
все члены прошли мимо. Существующие pending бои резервируют участников. Сначала
планируются ранние непересекающиеся пары; `deferred_contacts` сообщает число
встреч, требующих перепланирования после боя. Все планы сохраняются одной
транзакцией; retry/restart сохраняет прежние EventID/captures.

Пределы одного прохода: 256 roots/256 живых участников, 8192 сегмента, 131072 cell references,
4096 ячеек на segment/query, 200000 проверок, 4096 candidate pairs, 64 боя.
Переполнение отклоняет весь проход до ACK, не обрезает кандидатов молча.
Индекс поддерживает atomic upsert/erase без перестройки остальных записей,
но текущий admin adapter строит его из bounded DB snapshot на команду.
Автоматический route-change subscriber, дробление больших локаций на окна
и перепланирование ещё нужны; это не утверждение о capacity живого сервера.

Наблюдаемый бой должен принять engine; звуки/визуальные следы не
воспроизводятся по одному факту наличия backend event. Offline
emission/shelter damage впереди.

## Аномалии и ловушки offline

Admin `offline_hazard` планирует физическое пересечение маршрута конкретного
actor/group с конкретной ANOMALY/TRAP: EventID, entity/hazard IDs и versions,
horizon_ms, seed. Доверенное состояние опасности задаёт `hazard_type`, position,
radius (0.1..200), damage_bp (1..10000), intensity (0..100), cooldown_ms,
cooldown_until_ms, active (anomaly) или armed/charges (trap). owner_id и
safe_factions исключают защищённых участников. Проверяются индивидуальные
пути членов группы со смещениями и поворотами, а не только центр отряда.

Capture содержит здоровье/опыт/known_hazards, версии и полное состояние
carried items, движение, состояние опасности и WorldID/seed. Trusted catalog
может задать ARMOR/ARTIFACT `hazard_protection_bp` по типам; учитывается только
equipped=true, один предмет/ID и действительный condition. Применяется лучшая
защита без бесконечного суммирования. Вероятность избежать опасности —
ограниченная baseline policy опыта/знаний, с seed из сохранённого capture;
это не откалиброванная модель GAMMA damage/resistance.

Результат одной транзакцией сохраняет ранения/постоянную смерть, позиции,
сохранение всех вещей с прежними IDs в corpse, состояние группы, cooldown и
однократный расход заряда trap. Маршрут останавливается для нового решения
AI, погибшие члены не respawn. Hydration, смена маршрута/экипировки/опасности
отменяют stale event до damage/charges. Restart без изменения capture
сохраняет исход. Новые RouteArrived имеют priority=10: контакт priority=0 в
самой конечной точке разрешается до arrival CAS. Старые pending arrivals с
priority=0 не переписываются и могут консервативно отменить такой новый план.

Ограничения: 64 живых участника и 64 inventory items на участника, маршруты
до 1024 точек. Автоматическая discovery hazards, NPC replan, engine volumes,
native hydration, emission/shelter damage и artifact spawn ещё впереди.

Admin `offline_hazards` (`location`, `horizon_ms`, `seed`) теперь ищет опасности
для offline NPC/мутантов/отрядов через 3D corridor queries. Затем проверяет
действительные пути отдельных членов, радиус каждой опасности, cooldown и
owner/faction immunity. Первый контакт резервирует root и hazard; следующие
контакты сообщаются как deferred_contacts и требуют нового прохода после
изменения состояния. Бои и опасности используют общие резервы. Новый проход
отменяет устаревшие captures и освобождает участников до старого due time;
отмена и новые планы откатываются вместе при ошибке журнала. Отсутствующий
validator сохраняет чужие резервы консервативно.

Пределы hazard discovery: 256 roots/256 hazards/256 живых участников суммарно,
8192 сегмента, 4096 eligible candidates, 200000 общих spatial/narrow-phase
проверок и 64 disjoint контакта. Combined pending backlog — до 512 планов,
8 MiB encoded payloads; location states — до 8 MiB. Чтение потоковое,
переполнение отклоняет весь проход. Порядок отдельных команд боя/опасностей
задаёт вызывающий authority: автоматический общий выбор самого раннего события
и route-change subscriber ещё нужны; эта команда не запускается на каждом кадре.

Смерть обязательного живого quest entity теперь ставит durable последствия
для заданий в самой death transaction. Scheduler проваливает до 64 заданий
за atomic batch без запроса игрока, сохраняя исходный death ID/time и продолжение.
Награда не выдаётся, NPC не создаётся снова; corpse pins снимаются после провала.
Для старых deaths startup проверяет 64 targets; admin `quest_reconcile` принимает
optional `after_entity`, возвращает `next_after` и `unproven`. Продолжение по
cursor проходит мимо неполных старых записей, не придумывая событие смерти.

Admin `offline_plan` (`location`, `horizon_ms`, `seed`, optional `radius=50`)
выполняет общий earliest-contact проход боя и опасностей в одной транзакции.
Оба поиска используют один planning instant; сначала собираются все варианты,
затем выбираются первые события с непересекающимися roots/hazards, всего до 64.
Действительные pending captures участвуют в выборе: новая ранняя ловушка может
отменить более поздний бой, не меняя NPC и не расходуя боеприпасы. При одинаковом
времени сохраняется старый EventID/capture/RNG; новые точные ничьи выбирают бой,
затем persistent IDs. Повтор с новым seed не перебрасывает прежний валидный исход.
Отмена и замена атомарны; сбой любой части откатывает весь проход. Это явный
authority вызов; автоматическая подписка на изменения маршрутов ещё впереди.

Combat/hazard capture дополнительно ограничивает сумму encoded actor/item
states до 1 MiB (combat: на сторону; hazard: на группу), с резервом metadata.
Inventory читается курсором, отказ происходит до разбора остальных больших
состояний. Слишком большой capture не меняет здоровье, charges или ledger.
Финальный canonical event также сохраняет свой прежний предел 1 MiB.

Backend snapshots допускают до 128 MiB canonical UTF-8; trusted caller может
задать меньший `Store.snapshot(byte_limit=...)`. Размер escaped JSON проверяется
при чтении записей до сохранения превышающей лимит строки, включая envelope,
Cyrillic и разделители. Отказ сохраняет прежние снимки и journal; это ограничение
encoded admission, а не общей памяти процесса. Все сервисы движения, боя,
опасностей и scavenging требуют один World со своим Scheduler: чужой world
отклоняется до регистрации обработчиков или изменения state.

Route/dehydrate/hydrate, world-state/дипломатия, scale и замена timelines теперь
сначала разрешают уже наступившие scheduled events в той же транзакции, при
одном зафиксированном времени. Поэтому поздний hydrate или смена дипломатии
не отменяет бой, физически произошедший раньше команды. Будущие stale captures
по-прежнему отменяются. До barrier выполняются authorization/idempotency checks.
CAS conflict, ошибка resolver или превышение 64 событий / 5 ms откатывают всю
команду вместе с catch-up; фоновый runner затем может завершить события, после
чего adapter повторяет команду с актуальной версией. Это bounded admission,
а не обещание завершения обработчика строго за 5 ms.

Опциональная trusted настройка сервиса `offline_planning` включает подписку
общего contact planner на route/dehydrate/hydrate/scale/relations commands:

```json
"offline_planning": {
  "horizon_ms": 86400000,
  "radius": 50,
  "max_locations": 25,
  "budget_ms": 100
}
```

Пересчёт использует то же время и транзакцию, что изменение. Отмена старого
capture, новый маршрут и новые контакты фиксируются либо откатываются вместе.
Seed/EventID получаются из WorldID, seed мира и source command, replay не
перебрасывает результат. `ContactsReplanned` содержит причину и source command.
Отказ по лимиту локаций/времени сохраняет прежний маршрут/резервы/scale.
Повторная регистрация authority отклоняется; включение не доступно клиентским
HTTP-командам. Config загружается при старте backend, без него подписка выключена.

Если действительный маршрут продолжается за `horizon_ms`, один durable
`OfflineContactsWindow` на локацию ставит следующий bounded проход. Catch-up
начинается с **сохранённого due time**, поэтому задержка обработки не пропускает
уже пройденный контакт. После restart pending окна сохраняют время/identity;
отсутствующая или изменённая semantic policy (`horizon_ms`/`radius`) удерживает
событие до восстановления настройки. Work budgets можно менять отдельно.
Изменение маршрута заменяет старое окно атомарно. Контакт имеет priority=0,
arrival=10, window=20; окно не мешает контакту в конечной точке маршрута.
После завершения всех маршрутов цепочка останавливается; continuation проверяет
только контакты с хотя бы одним движущимся root, чтобы не повторять мгновенный
бой неподвижных участников. Это события по времени/локации, не per-NPC ticks.

При успешных RouteArrived/OfflineCombat/OfflineHazard/StashVisited scheduler
сначала записывает исход как APPLIED, затем в той же транзакции ставит durable
`OfflineContactsRefresh` (priority=5). Пересчёт начинается с времени исхода,
отменяет устаревшее окно и сохраняет физически возможные будущие встречи с
движущимися roots. Поэтому раннее прибытие одной группы не отменяет навсегда
её более позднюю встречу с другой. Сбой очереди откатывает и исход; restart
сохраняет pending refresh. Без продолжающихся маршрутов дальнейший проход
останавливается до сканирования всей stationary population.
Одновременные исходы одной локации используют один pending refresh; каждый
source→refresh записывается в `ContactsRefreshQueued`. После APPLIED новый
исход получает новый EventID. Это не создаёт повторных неподвижных боёв и не
меняет RNG уже действительных равновременных captures.

Новое решение AI после завершения боя/опасности, отдельная длительность боя,
укрытия и native world authority/AOI/LOD adapter ещё нужны. Engine bridge
остаётся read-only shadow; этот config не переводит native ALife в Coarse.

Transfer Prepare теперь читает entity/item checkpoint потоком и учитывает
точный canonical UTF-8 размер с escaped JSON, IDs, metadata и разделителями
до удержания превышающей лимит записи. Default limit остаётся 1 MiB; trusted
embedding может уменьшить `Transfers(..., checkpoint_limit=...)`, клиентские
команды этот параметр не задают. Проверка membership читает только metadata
членов, затем state допускается по бюджету. Переполнение отклоняет Prepare
до создания token/transfer и заморозки writer/session, не обрезая инвентарь.
Точные boundary/Unicode и early-read проверки подтверждают сохранение прежних
владельцев и вещей. Большим группам нужен отдельный chunked handoff protocol,
а не увеличение неограниченного capture; native bridge по-прежнему впереди.
