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
Автоматический выбор маршрутов/целей NPC и подключение к GAMMA впереди.

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
continuous narrow phase вычисляет действительное сближение. Отдельные члены
группы исключены, существующие pending бои резервируют участников. Сначала
планируются ранние непересекающиеся пары; `deferred_contacts` сообщает число
встреч, требующих перепланирования после боя. Все планы сохраняются одной
транзакцией; retry/restart сохраняет прежние EventID/captures.

Пределы одного прохода: 256 roots, 8192 сегмента, 131072 cell references,
4096 ячеек на segment/query, 200000 проверок, 4096 candidate pairs, 64 боя.
Переполнение отклоняет весь проход до ACK, не обрезает кандидатов молча.
Индекс поддерживает atomic upsert/erase без перестройки остальных записей,
но текущий admin adapter строит его из bounded DB snapshot на команду.
Автоматический route-change subscriber, дробление больших локаций на окна
и перепланирование ещё нужны; это не утверждение о capacity живого сервера.

Наблюдаемый бой должен принять engine; звуки/визуальные следы не
воспроизводятся по одному факту наличия backend event. Offline
anomaly/shelter/emission damage впереди.
