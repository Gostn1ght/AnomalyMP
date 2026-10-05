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
- NPC и группы переходят с прежними member IDs, включая погибших членов.
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

Удостоверенный localhost endpoint → read-only engine bridge → согласование
WorldID/clock/ownership → shadow comparisons → durable mutation paths.
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
