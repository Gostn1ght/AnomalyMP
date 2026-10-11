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
исполняет уже зафиксированный план. Контекст дополнительно проверяет имя
NPC при повторном использовании object ID. Fixture проверяет offline birth,
другую карту сервера, спустя 20 часов первого наблюдателя и повторный register.
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
