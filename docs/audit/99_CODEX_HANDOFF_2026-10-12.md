# 99 — Передача работы (Codex/GPT), 2026-10-12

Ты продолжаешь работу Claude над Lost Zone (мультиплеер GAMMA/Anomaly на X-Ray, репозиторий `engine-steamnet`). Владелец пишет по-русски: все сообщения ему — на русском, коротко и по делу. Сначала прочитай doc 97, doc 98 (`docs/audit/`), чек-лист в начале `README.md` и этот файл.

## Жёсткие правила владельца
- Движок НЕ собирать локально. Только push → GitHub Actions «Lost Zone DX11» → артефакт. Каждый push отменяет идущий прогон, поэтому пушь пачками.
- Новые fixture-скрипты добавлять в `.github/workflows/lostzone-dx11.yml` (нужен `git add -f`).
- Никогда не выводить пароль админа (`keys\ADMIN_PASSWORD.txt`), не публиковать `keys\secret.key`, `Compressor\private`, `hoster\master\runtime` (приватные ключи).
- Не кликать мышью по рабочему столу владельца, не трогать диалоги ОС и брандмауэра.
- Не удалять аккаунты, персонажей и миры.
- Не добавлять строки атрибуции NEAREST-STAGE/alistairfox.
- Оптимизации не должны делать NPC глупее, чем во freeplay.
- Проверять на реальных exe (srvtest + логи), а не только fixture'ами.
- Сервер и игру сейчас НЕ запускать для игрока: владелец тестирует дома сам. Серверы в srvtest для проверки логов запускать можно, потом выключить.
- Патчи только с новыми номерами. Следующий свободный номер — **000006**.

## Состояние на момент передачи
- Последний коммит — `5e57b0787` (чистые консоли: без hitch-трасс, без HOM на сервере, тихие отказы конфигов, разрешены оптические/тепловизорные команды GAMMA — фикс чёрных и прозрачных прицелов). Он запушен; проверь, что CI зелёный, и скачай артефакт.
- **Не закоммичено** (закоммитить первым делом):
  - `src/xrEngine/xr_ioc_cmd.h` — `CCC_Vector4::parse` принимает 3 значения (w=0);
  - `scripts/make-gamma-overlay-fixes.py` — генератор копий скриптов GAMMA с фиксами в `scripts/netcoop-overlay/{client,server}`. Он уже запускался, результат лежит в overlay: `ui_mcm`, `callbacks_gameobject`, `liz_fdda_redone_consumables_ssfx_dof`, `mosin_carbine_reload_script`, `ui_hud_dotmarks`, `treasure_manager`, плюс серверные заглушки `ssfx_water` и `ssfx_wetness`;
  - `-dbg` убран из `scripts/netcoop-cluster/netcoop_cluster_watchdog.ps1` и `scripts/dist/Start Locations.cmd`. `-dbg` включает DEV_DEBUG GAMMA, на продакшене его быть не должно.
- Логи srvtest (`J:\LostZone_Work\_work\srvtest\appdata\server\logs`) старые: старый exe `a50026e1c` и запуск с `-dbg`. Многие строки из них уже исправлены или выводятся только через printdbg.

## Задача 1 — ноль ошибок в консолях сервера и клиента (владелец: «даже незначительные»)
Добавь в `scripts/make-gamma-overlay-fixes.py` (минимальная правка, комментарий `-- Lost Zone: причина`, CRLF, latin-1) и перезапусти его:
1. `gamma_dynamic_radiation_areas_from_arzsi.script`: `level.vertex_id(smart.position)` заменить на `smart.m_level_vertex_id`. Причина: сотни строк «Invalid position for CLevelGraph::vertex_id» — смарты с других уровней.
2. `smr_pop.script`:
   - в `retarded_squad_names` добавить `["ecolog_sim_squad_alpha"]="ecolog_sim_squad_veteran"` и `["zombied_sim_squad_alpha"]="zombied_sim_squad_veteran"` (это убирает «alife_create | section [ecolog_sim_squad_alpha] is invalid»);
   - убрать trace «level %s not found, returning nil».
3. `craft_use_in_tooltip_mcm.script`, `grok_artefacts_random_condition.script`: убрать первую строку `printf("1057 error fix")`.
4. `warfare.script`: убрать printf «~ Warfare is not loaded…».
5. `release_restr_in_x16.script`: `alife_release(sobj, true)` заменить на `alife_release(sobj)`.
6. `xrs_rnd_npc_loadout.script`: убрать printe «wrong ammo_type… ammo_class». Fallback на 0 остаётся: у lapua700 после deer_hunter один патрон, а у monolith в loadout стоит ammo_type 3.
7. `smart_terrain.script`: убрать printf «validate_patrol_path WARNING» (битые вершины патрулей в данных карты Pole; работа и так пропускается).

DLTX/конфиги кладутся рассыпными файлами в `scripts/netcoop-overlay/{client,server}/configs/`:

8. Звуки:
   - `![wpn_toz34_teivaz_snd_shoot]`: snd_1_layer..snd_1_layer3 → `weapons\toz34\mono\toz34_teivaz_mono_very_close1..4`;
   - `![wpn_pm_custom]`: snd_reload_empty → `weapons\pm\pm_reload_empty`;
   - `![wpn_glock]`, `![wpn_glock_modern]`, `![wpn_oc33]`: snd_close → `weapons\walther\walther_close`;
   - `![wpn_m4_tac]`: `!snd_shoot` и `!snd_silncer_shot` (наследуется от wpn_m4_sounds, так же сделано у xm4 в wstfg).
   - Файл, например, `mod_system_zzzzzzzzzzzzzzzzz_lostzone_sound_fixes.ltx`. Проверь, что он грузится последним.
9. `configs/environment/effects.ltx` — полная копия, в которой `nature\wind_05` → `nature\wind_04`, `nature\wind_07` → `nature\wind_06`.
10. Звуковые файлы в gamedata патча: копии `material\bullet\collide\bullet_hit_dirt_2.ogg`/`_3.ogg` под именами `bullet_hit_dirt_02.ogg`/`_03.ogg` и `material\dropper\collide\water_1.ogg` → `material\dropper\collide\collide\water_1.ogg`. На эти пути ссылается gamemtl.xr.
11. `anomaly\teleport_work_2.ogg` — 96 кГц, «Invalid source rate». Пересэмплировать в 48 кГц (например, `uv run --with soundfile --with numpy --with scipy`), сохранив vorbis-комментарий X-Ray, если он есть.
12. Пустые работы MLR (скрипт проверки: scratchpad-логика из `check_exclusive.py`; перенеси её в `scripts/check-gamma-exclusive-jobs.py`):
   - `configs/scripts/military/smart/mod_mil_smart_terrain_7_7_zz_lostzone.ltx`: `![exclusive]` + `!mil_7_7_xcvb_day_9`;
   - `.../mod_mil_smart_terrain_7_4_zz_lostzone.ltx`: удалить `mil_2_2_xcvb_day_1..6` и `night_1..6`, добавить `mil_7_4_xcvb_day_1..6` и `night_1..6` = `military\mil_smart_terrain_7_4_smart_logic_xcvb.ltx`;
   - `configs/scripts/dead_city/smart/mod_cit_killers_vs_bandits_zz_lostzone.ltx`: `![exclusive]` + удалить `cit_killers_vs_bandits_xcvb_night_1..7`.

Ещё осталось:
13. `!load_var: Warning: no db.storage for 0` на сервере при старте. Якорный актёр id 0 (Actor_Network.cpp:1162). Временно оберни `_G.load_var`, выведи callstack при id==0, найди вызывающий код и исправь там, либо создавай `db.storage[0]` для якоря (см. `bind_actor` в `netcoop_server_compat.script`).
14. `~WARNING : Failed to load '', falling back to equipment_box_01_case.ogf` — найти тайник/ящик с пустым visual.
15. Клиент: предупреждение заглушки heatvision.ps; шум в консоли мастера (`backend/lostzone`).

Проверка: новый exe из CI → srvtest (удали exe перед заменой, там хардлинки) → запуск карт с продакшен-аргументами (без `-dbg`) вместе с мастером → посчитать строки `^!`, `^~`, `STACK TRACEBACK`, `ERROR` по всем 33 картам. Цель — ноль. Потом всё выключить.

## Задача 2 — незакрытые этапы doc 43 (19 ⬜ плюс частичные; список в doc 43/48/97/98)
Главное — серия H: перенос предметов, NPC и мутантов между картами через мастер (H11 — ALife split). Мастер уже обязателен: карты без него не пускают игроков, погода, выбросы и пси-шторм идут от мастера (`backend/lostzone/director.py`, `netcoop_world_bridge.inc`, `netcoop_master.script`). Транзит (`server/netcoop_transit.script`) должен идти через журнал мастера с подтверждением, без дублей и без потерь. Бэкенд-тесты: `python -m unittest` в `backend` (сейчас 283 OK). После каждого закрытого этапа обновляй отметки в README и doc 43.

## Задача 3 — обновление папки сервера (формат владельца)
Друг накладывает сервер ПОВЕРХ установленной игры. Нужна одна папка `J:\LostZone_Work\Lost Zone Server`, которую владелец заархивирует и отправит другу. В ней:
- dedicated exe из CI;
- `hoster` (панель `netcoop_cluster_panel.ps1` со всеми 33 картами и карточкой мастера, watchdog, `netcoop_master_control.ps1`, портативный мастер из `scripts/dist/make_master_runtime.py`, но БЕЗ `hoster\master\runtime` и ключей);
- серверные configs/scripts;
- серверные патчи 000001/3/4/5 + новый **000006_server**;
- `Start Locations.cmd`;
- README с инструкцией «что сделать другу»: распаковать поверх игры с заменой → запустить Start Locations / панель → мастер стартует первым.

Это НЕ standalone (`make_standalone_server.py` — не тот формат). Отдавать только после задач 1 и 2.

## Задача 4 — обновление клиента в лаунчере
Рецепт есть в памяти `lost-zone-release-state.md`:
1. `git diff` `scripts/netcoop-overlay` от последнего отгруженного коммита.
2. `*.script` → `Compressor\lzpack.py patch --role client|server` (вход — `client/scripts`, `server/scripts`) → патч **000006**.
3. Текстуры и звуки клиента → `gamedata/`.
4. Конфиги рассыпными файлами поверх `client\configs` (в архивы нельзя: моды читают их через io.open).
5. Клиентский exe — из CI.
6. Собрать `packer pack` (`Kall\launcher`) в `J:\LostZone_Work\publish`.

Перед публикацией в лаунчере спроси владельца (публикация — внешнее действие). Старые файлы сохраняй в `J:\LostZone_Work\_work\before_*`.

## Что владелец проверит дома (не заявляй это как проверенное)
- бартер (смотришь на игрока + F → приглашение, второй смотрит и принимает);
- подсказки Interaction Dot Marks;
- прицелы (снайперские были чёрные, остальные слишком прозрачные; исправлено whitelist'ом консоли и пресетом `r__3Dfakescope`);
- графические аддоны (пресет `graphics_gamma.ltx` применяется один раз).

В конце коротко отчитайся владельцу по-русски: что сделано, что проверено на реальном exe, что ждёт его проверки.
