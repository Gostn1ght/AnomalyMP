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
