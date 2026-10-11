# 95. Автономное продолжение 2026-10-11

Движок собирается только в GitHub Actions. Игра, сервер и боты не запускаются.
Новые статусы 🔧 означают код/fixtures, не игровую приёмку.

## Патроны: обычные снимки

`CWeapon::net_Import` уже сохранял магазин владельца, но два других пути
обходили защиту: `CWeaponAmmo::net_Import` возвращал поздний count коробки,
а `CWeaponShotgun::net_Import` перезаписывал mixed cartridge types владельца.
Теперь оба пути потребляют packet без изменения его predicted ammo. Observer
и freeplay получают обновления. Box count ограничен box size; shotgun читает
extension только при достаточном размере, пропускает неизвестные типы и
индексы вне магазина. Explicit full item snapshots сохраняют прежнюю роль.

Actual native fixture `check-native-ammo-import.py` проверяет последовательность
расхода коробки с поздними снимками, mixed shotgun cartridges владельца,
observer/freeplay path, count/type bounds, short packet и cursor consumption.
Подключена к DX11 и Foundation (GCC/MSVC; Linux ASan/UBSan).

Полный server authority магазина не закрыт: state events и item reports всё
ещё принимают client counts; reload/unload и full snapshots требуют общего
протокола подтверждений. Исправление обычных imports не заявлено решением всех
рассинхронизаций.

## Проверки CI

В Windows checks-блоке DX11 добавлены отсутствовавшие проверки errorlevel
после projectile/voice/PDA/hands fixtures. Ошибка любой отдельной проверки
теперь останавливает job, даже если следующая команда успешна. Предыдущий
Foundation подтверждал эти fixtures отдельно; результаты не аннулированы.

Коммит `ec9f1cf1d`: [DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38128861739),
[Foundation GCC/MSVC PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38128861722).
Движок локально не собирался; игровая приёмка остаётся открытой.

## L22 — политика первоначального лута NPC

Новый `netcoop_loot_policy` хранит seed в мировом script state и snapshot
контекста/шансов в se vars конкретного NPC. Контекст включает GAMMA `loots`,
время последнего завершённого выброса, последнее локальное сражение и их
периоды влияния. После появления NPC его контекст не обновляется. Генераторы
GAMMA продолжают создавать сами предметы; шансы допуска каждого этапа
настраиваются в `configs/netcoop/loot_policy.ltx`. Economy не умножается повторно
на community/private lists, где её уже применяет GAMMA.

Региональный факт боя сохраняется отдельно от 512-entry журнала: массовые
death events не снимают его влияние. Завершение выброса сохраняет game hour.
Изменение действует только на первоначальные наборы обычных NPC; story NPC,
`dont_spawn_loot`, существующие предметы и rare stash transfers сохраняют
свои пути. Материалы после выброса/боя становятся реже в новых наборах, а не
исчезают у уже живущих NPC.

Генерация использует локальный deterministic RNG с Lua 5.1 integer bounds.
Глобальная `math.random` восстанавливается и после ошибки. Переходы offline/
online, рестарт или ошибка не генерируют инвентарь заново. Прежние condition
rolls теперь используют persistent world seed; раньше seed зависел от времени
старта процесса. Полный ItemLedger и глобальная экономика кластера не закрыты.

Actual Lua fixture: economy/emission/local battle, 600 событий с вытеснением
журнала, разные карты/истёкшие и будущие события, модульный рестарт при новом
wall clock, неизменный snapshot, generator failure, story/dont_spawn_loot,
восстановление глобального RNG и реальный `build_npc_inventory`.
Дополнительная проверка закрыла зависимость от первого наблюдателя:
контекст фиксируется по `server_entity_on_register` даже для offline NPC,
с картой его game graph vertex. Engine запускает script callbacks до ALife
load, а script state и часы загружает до регистрации объектов. Поэтому
restart registration сохраняет старый snapshot; старые миры фиксируют
отсутствующие snapshots при загрузке. Первое online появление только
исполняет сохранённые seed, stage gates и экономику; это не snapshot полного
списка предметов и всех GAMMA inputs. Контекст дополнительно проверяет имя
NPC при повторном использовании object ID. Fixture проверяет offline birth,
другую карту сервера, спустя 20 часов первого наблюдателя и повторный register.
Отдельно проверен bootstrap экономики: GAMMA инициализирует `factors_eco`
в `on_game_load` уже после регистрации NPC. Политика читает saved `diff_eco`
overrides/preset и `plugins/difficulty.ltx` непосредственно; старый module cache
не перекрывает настройки нового мира. Fixture покрывает uninitialized factors,
saved override/preset, stale cache, NaN и fresh-world preset до первого игрока.
Обнаружена также зависимость actual `create_item_list` от общих local tables:
GAMMA заранее умножает шансы на экономику и перемешивает списки после NPC.
Для первоначальной генерации адаптер временно подставляет canonical lists из
`itms_manager.ini_death` с сохранённой экономикой, учитывает `exclude_from_multi`
и сохраняет исходный выбор профиля/проверки GAMMA. Старые cache и shuffle counters
восстанавливаются после успеха и ошибки; другие вызовы генератора продолжают
работать как прежде. Fixture выполняет неизменённую функцию GAMMA из
`scripts/fixtures/loot/create_item_list.lua`: stale scale/order/counters не меняют
результат, нулевая экономика сохраняет excluded items, ошибка восстанавливает
upvalues и RNG. Полный immutable inventory plan остаётся за рамками L22.
Items/emission/world-events/Lua scope PASS. L22: ⬜ → 🔧; текущий учёт
188 требований: ✅ 27, 🔧 42, 🟡 66, ⬜ 53.

## Выносливость владельца

В Anomaly mode `UpdateSatiety` прибавлял stamina только внутри
`CanBeHarmed`, а тот требует `OnServer()`. Поэтому чистый клиент тратил
stamina в `ConditionStand/Walk`, но не восстанавливал её по сытости.
Теперь восстановление по сытости разрешено также собственному control actor
pure client. Health delta остаётся внутри серверного gate; чужим акторам,
legacy multiplayer, protected freeplay и menu GodMode исключение не добавлено.
Коэффициенты сытости/сна/расхода GAMMA и max power clamp сохранены.

`check-native-stamina-recovery.py` выполняет actual `UpdateSatiety`,
`ConditionStand`, `CanBeHarmed` и inherited `CEntityCondition::UpdateCondition`:
последовательные кадры восстановления, предел max power, голод/сон, отсутствие
client health regen, чужой actor/отсутствующий control actor, protected freeplay,
legacy MP и menu GodMode. Подключена к DX11/Foundation GCC/MSVC;
локальная компиляция не выполняется. README ⬜ → 🔧, мировые счётчики прежние.

## L28 — топливо, спички и повторное подключение

Проверен оставленный Claude таймер костра игрока (3 игровых часа). Исправлены
два обхода: пустая/уничтожаемая коробка спичек больше не принимается, неверный
boolean в запросе отклоняется. `net_Stop` очищает campfire maps после удаления
объектов и отключения транспорта: прежние fuel deadlines, sync marks и pending
состояния с переиспользованным object ID не переходят в новую сессию.
Тушение через лагерную логику также снимает прежний fuel deadline: костёр,
впоследствии зажжённый NPC, не наследует старый таймер игрока.

Новая fixture выполняет весь actual `netcoop_campfire.inc`: distance/alive,
расход одной порции, повторный запрос без повторного расхода/продления топлива,
пустая/уничтожаемая коробка, точный game-time deadline, тушение, late join,
малформированные пакеты, deferred spawn и reset с откатом часов новой сессии.
Подключена к DX11 и Foundation GCC/MSVC. L28 остаётся 🔧; игрового запуска нет.

## Торговля — серверные условия GAMMA

Положительная `GetItemPrice` сама по себе не запрещала предмет ниже порога
износа торговца. Поддельный запрос мог также передать quest/nontrade item или
неполную коробку/многоразовый товар, который GAMMA скрывает на стороне NPC.
Теперь весь basket проходит `CanTrade` и actual `utils_item.get_item_trade_status`
с текущим серверным профилем NPC до `OnPerformTrade` и `TransferItem`. Условие
проверяется в том же `ServerVictimScope`, что цены и персональные отношения.
Отсутствующая функция/профиль и исключение не разрешают сделку. Native price,
TransactionID/locks и прежние проверки денег/ownership сохраняют свои роли.

Lua fixture выполняет неизменённую функцию GAMMA: порог износа и равенство ему,
quest/nontrade, запрет секции, полные/неполные ammo и multiuse, anim/fake stock,
неверный профиль, мёртвый/отсутствующий NPC и отсутствие игрока. Частичные
ammo/uses по-прежнему можно продавать согласно GAMMA; запрет покупки скрытого
товара не переносится на продажу. Native fixture проверяет фактический helper,
fail-closed ошибки и положение admission pass до эффектов сделки; GCC/MSVC в CI.
Также исполняется actual price/admission loop для смешанной корзины: запрет
второго предмета, zero price и исключение прерывают весь pass до commit witness.
L26 остаётся 🟡: dynamic supply/demand/restock events и cluster ItemLedger не
реализованы этим исправлением. Учёт 188 требований не изменён.

## Подтверждение продолжения

Защита торговли `89c34bd28`:
[Foundation GCC/MSVC PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38135294040),
[DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38135294031),
в обеих platform logs есть PASS actual native trade admission и mixed basket.

Первый L22 (`e5d11da55`): [DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38130460606).
L22 с сохранённой экономикой и canonical GAMMA lists (`c518bf095`):
[DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38133859152),
включая actual Lua generator fixture и Windows checks перед сборкой.
Итоговый код `2cab06c88`: [Foundation GCC/MSVC PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38132068951),
[DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38132068954);
в логах обеих платформ есть PASS actual stamina recovery и PASS actual campfires.
Предыдущие Windows-прогоны остановили `/WX` из-за типов ID и имени глобальной
заглушки новой campfire fixture; исправлены именно заглушки, строгость сохранена.

Учёт 188 уникальных строк повторно проверен: ✅ 27, 🔧 42, 🟡 66, ⬜ 53.
Полный протокол server shot/reload/unload acknowledgement остаётся открытым;
исправление ordinary imports не повышает этот пункт до закрытого.

## Отдельная консоль мастера — уточнение владельца

Владелец подтвердил целевую схему: отдельная консоль запускает мастер;
мастер ведёт общий календарь/погоду/глобальные события и переносы NPC/персонажей;
серверы локаций выполняют локальные physics/combat/AI. Character identity,
инвентарь и индивидуальный состав NPC сохраняются при переходе; source и target
не владеют ими одновременно. Новая DB не подменяет существующий игровой мир.

Добавлен `python -m lostzone console --config ...` и отдельный Windows launcher
`backend/Start Lost Zone Master.cmd`. Console запускает существующий World
Service с HTTP/checkpoint workers и единственным OS-locked SQLite store.
Status, clock, locations, characters, NPC/mutant/group counts, transfer states
и последние 10 event metadata читают настоящий backend. Registry summaries
ограничены выборкой до 1024 записей, locations — до 64; наличие остальных
записей отмечается явно. Нет полного сканирования реестра под store lock. Private payloads,
tokens и checkpoints не выводятся. Scale использует существующий admin
dispatcher и durable mutation barrier, закрыт при recovery. Quit/EOF/Ctrl+C
ведут через общий final-save/shutdown; signal handlers восстанавливаются.

Семь focused Python tests выполняют настоящий Store/World/Dispatcher,
calendar continuity, recovery/stale epoch, private output, bounded registry summaries, EOF/interrupt и
service lifecycle/restart. Listener в lifecycle fixture заменён заглушкой:
игра, native server/bots и рабочая консоль мастера локально не запускались.
Full backend suite выполняется Linux/Windows workflow.

Console `a754a8636`:
[World Backend Linux/Windows PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38136534571).
В обоих platform logs: 248 tests PASS, включая все семь console tests.
[DX11 build/package PASS](https://github.com/Gostn1ght/AnomalyMP/actions/runs/38136534589).
Следующие code commits отправляются только после завершения этого build.

Это первый этап отдельного мастера. Текущий engine bridge остаётся observer;
календарь/погода/персонажи игры используют legacy store, а автоматический NPC
transit выключен до разделения ALife registry (H11). A01 остаётся 🟡,
пункт полного выноса игрового мастера — ⬜; счётчики 188 задач прежние.
Следующее подключение: единые WorldID/clock и backend authority в location
adapter, character/NPC handoff с fencing/ACK, разделение владения ALife и
единый источник world events/weather. Launcher сам не закрывает эти пункты.

## Bootstrap погоды/выбросов в native location observer

Native bridge раньше разбирал clock/identity и отбрасывал `states` из
того же HTTP bootstrap. Теперь weather/emission schedules и event watermark
сохраняются вместе с принятой clock sample. Private/неизвестные world states
не передаются в diagnostics. Parser проверяет schema, envelopes/version,
128-bit TimelineID, cycle identifiers, u64 seed, конечные и строго
упорядоченные phase times, intensity и phase names. Неизвестная фаза,
повреждённая известная timeline или пропущенный watermark отклоняют весь пакет.

Observer не принимает revision/watermark/version rollback или исчезновение
ранее принятого расписания. Schedule с тем же TimelineID неизменяем и при
повышении version; replacement требует нового ID и большей version.
Weather blend/phase и emission phase вычисляются из единого follower calendar,
а не из сохранённого phase, который может отставать при event catch-up.
Последний принятый schedule не заменяется при stale/invalid packet.
При истечении holdover диагностика закрывает ready и не выдаёт активные фазы.

Расширена actual native fixture `check-netcoop-world-bridge.py`:
phase boundaries, malformed schedule, same-ID mutation, replacement,
watermark/revision rollback, restart/stale authority и holdover. На GCC/MSVC
parser читает настоящий SQLite/World/Timelines bootstrap с weather transition
и emission peak; Windows отдельно проверяет WinHTTP и worker diagnostics
через authenticated backend fixture. Fixture выполняется в Foundation и
теперь также в DX11 checks. Native compilation только в CI.

Это read-only подключение глобального state, не применение погоды/календаря
в игре. A01/B08/B10 остаются 🟡; B09 исправлен ⬜ → 🟡, поскольку endpoint/wire
уже существуют, но location adoption/ScaleChanged delivery/remote transport
ещё открыты. Текущие 188 строк: ✅ 27, 🔧 42, 🟡 67, ⬜ 52; новых игровых ✅ нет.
CI этой стадии будет зафиксирован после commit/push и успешных прогонов.

## Явная начальная идентичность мастера

Обычный `init` оставляет генерацию случайной identity первому World bootstrap,
поэтому сам по себе не согласовывает мир с engine observer. Добавлены
`init --world-id ... --seed ... --initial-ms ... --scale ...`:
WorldID/seed задаются парой, проверяются u64/bounds и конечность calendar/scale
до создания credential файла. Другие CLI modes эти options отклоняют, чтобы
начальный параметр не выглядел как live mutation. Старый config не заменяется.

Три focused tests проверяют настоящий SQLite/World restart с максимальными
u64 identity, saved calendar/scale вместо initial defaults, конфликт чужого
WorldID/seed с rollback epoch, отсутствие файла/папки после invalid bootstrap,
CLI init без открытия DB и запрет bootstrap flags в serve/console/bridge-config.
Локально PASS; полный backend suite проверяется Linux/Windows CI.

Это preparation нового backend мира: identity согласовывается явно,
но coherent ALife import, authority adoption и персонажи/предметы не перенесены.
A01 остаётся 🟡, счётчики не меняются. Новых игровых ✅ нет.
