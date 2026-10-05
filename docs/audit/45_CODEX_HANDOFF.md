# 45. Handoff для Codex (кластер локаций, 2026-10-05)

Этот файл — самодостаточное задание для продолжения работы, если сессия
Claude остановится по лимитам. Обновляется после каждого шага.

## Правила владельца (обязательно)

- Сборка движка только через GitHub Actions: `git push gostn1ght HEAD:menu-3d-hideout`,
  workflow «Lost Zone DX11», артефакт `LostZone-DX11-client-server`
  (`gh run download <run> --repo Gostn1ght/AnomalyMP -n LostZone-DX11-client-server`).
  Новый push отменяет идущий DX11 run (cancel-in-progress) — не пушить во
  время сборки, если её результат нужен.
- Lua overlay ставится только из этого репозитория:
  `scripts/patch-gamma-netcoop-overlay.ps1 -RuntimeRoot ..\gamma-runtime`.
- Runtime владельца: `..\gamma-runtime` (сервер `dedicated\`, клиент `bin\`),
  клиент с 3D меню: `..\LostZone-3D-Hideout`. Старые exe: `gamma-runtime\backup-e90a2d2`.
- Нет респавна NPC/мутантов; сна нет; мебель только в помещениях вне безопасных
  зон; всё сохраняется после рестарта (см. doc 41 конец, doc 43).
- Отношения фракций игроки не меняют; репутация per-player.
- Коммиты: в конце `Co-Authored-By` строка ассистента; не добавлять чужие файлы.
- Lua-проверки локально: `python scripts/check-netcoop-items.py`,
  `python scripts/check-netcoop-world-rules.py` (нужен `pip install lupa`).

## Что сделано (код, в игре не проверено)

Кластер локаций — `src/xrGame/netcoop_cluster.inc` (+ хуки в `netcoop.cpp`,
`xrServer.cpp`, `level_changer.*`, `netcoop_characters.inc`, `netcoop_bots.cpp`):
- один dedicated процесс на карту из одной runtime папки; адреса карт —
  `$app_data_root$/netcoop_cluster.ltx` `[locations] k00_marsh = host:port`;
- M_CHANGE_LEVEL клиента → сервер проверяет переход (`g_lchangers`, радиус+10 м),
  замораживает игрока, синхронно сохраняет персонажа в точке прибытия,
  пишет HMAC-билет `netcoop_cluster/ticket_<login>_<slot>.txt`, снимает lease,
  шлёт клиенту `netcoop_transfer host|port|level`; клиент делает
  `start client(host/name=login/port=port)`;
- lease аккаунта `netcoop_cluster/online_<login>.txt` (heartbeat 10 с, TTL 30 с);
- вход на сервер другой карты → `redirect|host|port|level` в auth result;
- общий `netcoop_accounts.txt` сливается между процессами (named mutex, mtime);
- `zz_netcoop_world_rules.script`: generic цели отрядов только на своей карте;
- задания помнят карту выдачи (`CGameTask::m_netcoop_origin`), другие серверы
  их не вычисляют;
- облачный (Firebase) вход теперь отправляет auth при подключении (`client_can_login`);
- запуск: `gamma-runtime\netcoop_cluster_start.bat` (Болота 1267, Кордон 1277);
- самотест: `scripts/run-cluster-selftest.ps1 -Runtime ..\gamma-runtime -Bots 4 -Minutes 12`
  (порты 1367/1377, `appdata\selftest`, флаг `-netcoop_cluster_selftest`).

Дополнительно (коммиты после `a3bf4e0`, ещё не собраны на момент записи):
- `092b269` общий календарь кластера: каждый сервер пишет `netcoop_cluster/clock_<port>.txt`,
  отстающий ускоряет время (до 4x) до догоняния — без скачков;
  generated задания с целью (не story) на другой карте отменяются
  (`netcoop_server_compat.cancel_task_on_other_map`);
- `c59a005` общее расписание выброса для кластера (`netcoop_emission.script`,
  слот частоты + детерминированный час, слот помнится после рестарта);
- `837632e` `scripts/netcoop-cluster/netcoop_cluster_watchdog.ps1` — перезапуск упавших серверов;
- `gamma-runtime
etcoop_1_server.bat` поднят до maxplayers=16 (бэкап `.bak_cluster`).
- Компаньоны при переходе остаются ждать на старой карте и снова следуют,
  когда игрок вернётся (уже так по `get_script_target`); перенос NPC между
  серверами — H09, не сделан.

## Очередь задач (по приоритету для ЗБТ)

1. Прогнать самотест, починить найденное (логи `gamma-runtime\appdata\selftest\logs`,
   `appdata\selftest_bots\logs`, строки `[cluster]`, `[bots]`).
2. Общее время/погода/выброс кластера (doc 43 B09–B13, J). Решение владельца
   нужно: идёт ли время, пока сервер карты выключен. Часы `netcoop_alife_clock.h`
   запрещают скачки — нужен catch-up API, не отключать проверку.
3. Задания между картами (doc 43 I): цели на другой карте должны выбираться/
   проверяться на сервере той карты (story id), награда идемпотентна.
4. NPC transit между серверами (H09/H10) — после 2–3.
5. Нагрузка 16–32 игроков: `-netcoop_bots N -netcoop_bots_addr 127.0.0.1/port=1267`.
6. Плакат «Революционный проект «Фолк Восянка»» в 3D меню: ждёт фото от
   владельца (файл не сохранён на диск). Комната: `scripts/build-lostzone-room.py`,
   задняя стена Z1=3.0, текстура в `scripts/netcoop-overlay/client/textures/`.

## Журнал

- 2026-10-05 23:35 (Claude) — нагрузка, билд `1566b38`, один сервер Болот, 16 ботов,
  8 мин: 16/16 играют, 0 отвалов; кадр сервера avg 9–14 мс, max 127–209 мс;
  трафик ~110 КБ/с на игрока (~1,7 МБ/с на 16) — для интернета много, нужна
  экономия snapshot (задача). Следующее: установить DX11 `8d586d8` и повторить
  кластерный самотест (изменения Codex в player transfer/wallet).

- 2026-10-05 22:10 — самотест на билде `1566b38` (реальные exe, 2 сервера, 4 бота,
  10 мин): 88 переходов Болота↔Кордон, 0 отказов/ошибок/падений, прибытие в точку
  перехода (Кордон -273,-22,-274; Болота 558,2,-181). Счётчики `leaves/arrivals`
  в сводке занижены: логи серверов не сбрасываются на диск при Stop-Process.

- 2026-10-05 22:00 — билд `1566b38` установлен в gamma-runtime; `a3bf4e0`
  (облачный вход + заморозка заданий) собирается; самотест запущен.

- Продолжение Codex 2026-10-05: `95a4f2c9f` DX11 Actions 37362306316 SUCCESS.
  Новый NPC adapter имеет paired source/target checkpoints + durable mailbox
  ack/tombstone и crash/retry Lua fixtures. Старые destructive-read/partial-loot
  пути убраны. Автоматический transit выключен до H11/global ownership;
  `-netcoop_npc_transit` только для изолированных испытаний. Подробности и
  незакрытые критерии — doc 44, раздел «исправления аварийного перехода».
  Не переносить Lua v2 поверх старых exe: API put изменён, нужны id/ack bindings.

- Новый набор: запрет late source wallet overwrite, fail-closed account save
  (mutex/fsync/rename) и abort player prepare при его ошибке; physical stash
  reach 2 м, combat/wounded/observer guards, настоящий CTime cooldown + legacy
  migration. Lua PASS. Нужен итоговый Actions build; не ставить частичные overlays.
  Foundation 57535cd5c / 37366256415 полностью SUCCESS (GCC/MSVC).

- Backend следующий блок: admin-only offline_contact (continuous bounded 3D
  contact для известной пары), durable encounter schedule, route capture fence
  при world-scale rebase, restart/retry checks. Broad phase / автоматическое
  перепланирование / native ownership adapters всё ещё нужны.
- `8d586d8f9` Foundation 37367127157 SUCCESS GCC/MSVC (включая wallet/account
  fault checks). DX11 37367011993 в очереди, runtime не обновлён. Следующий
  backend-only commit не меняет native/overlay code и не отменяет этот build.

- HTTP fix: ранний POST отказ на Windows мог дать TCP reset вместо JSON error.
  Respond теперь flush/half-close + bounded tail drain; повторные реальные HTTP
  tests и полный локальный backend run: 75 PASS. ab98e1811 backend Windows
  Actions 37368019662 SUCCESS (74 tests, до fix); Linux queued.

- Stash follow-up: own/group motion dependencies captured, stale route/scale
  plans cancelled without moving items or consuming cooldown; restart-only
  fences do not cancel valid plans. Full local backend 80 PASS. Backend
  2802baa3f / 37368996036 SUCCESS Linux+Windows (75 tests). DX11 8d586d8f9
  run 37367011993 attempt 1 failed runner admission, not compilation; attempt 2
  checks SUCCESS and actual engine build running. Runtime still 1566b38 in
  gamma-runtime / 79263abd5 in LostZone-3D-Hideout; no partial overlays installed.
