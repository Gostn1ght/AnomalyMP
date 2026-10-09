# 45. Handoff для Codex (кластер локаций, 2026-10-05)

Этот файл — самодостаточное задание для продолжения работы, если сессия
Claude остановится по лимитам. Обновляется после каждого шага.

## Координация (Claude снова активен с 2026-10-05 23:30)

Claude и Codex работают в одной папке `engine-steamnet` и одной ветке.
Каждый коммитит только свои файлы (`git add <path>`, не `-A`), перед push
делает `git pull --rebase gostn1ght menu-3d-hideout`.
- Codex: `backend/**`, `netcoop_transit*`, stash visits, wallet/account store,
  player-transfer fixtures.
- Claude: replication/interest management в engine (`xrServer.cpp` snapshot,
  doc 43 D), трафик на игрока, установка билдов и самотесты на реальных exe,
  3D меню (плакат).
Если нужно тронуть чужую зону — записать здесь строку перед изменением.
- Claude 23:50: H11-lite в `zz_netcoop_world_rules.script` — в режиме кластера
  один раз на мир (после fill_start_position) release generic отрядов чужих
  карт (story/companion/scripted остаются). После установки этого билда
  копии чужого населения в location process исчезают; Codex может решить,
  достаточно ли этого, чтобы включить `-netcoop_npc_transit` по умолчанию.
- Claude: статус серверов `netcoop_cluster/status_<port>.txt` (players/capacity,
  TTL 30 с); переход/redirect не ведут на выключенный или полный сервер.

## Правила владельца (обязательно)

- Codex FINAL physics-skeleton scoped PASS (2026-10-08): source
  c8716c4c1f70d1a96e6a5e6aff549c82a5bd38bb, Foundation37727137941 and
  full DX1137727137945 SUCCESS; artifact11528723681 validated source/ZIP/
  built-from/exe manifest (both exes212BA94B...). Actual separate runtime
  CPhysicsSkeletonObject checkpoint now saves stock mask/root/flags/bodies
  and XYZ pose. New helper, actual traversal and refused-base-spawn tests
  passed GCC+ASan/UBSan/MSVC. First fixture compile failed due to reused
  matrix variable name; fixed without weakening assertions. Private native
  4fa control reproduced full pose reset1.885136m/0.988977 after SAME restart,
  CSE had no saved bones, common healthy proof PASS. Four earlier impulse
  targets were nonbreakable and generated no fragments: NOT accepted as a
  fracture test. Native fixed private test-only section uses unchanged stock
  bucket visual with actual physics-skeleton class. Full initial body poses
  exactly match control; original0.05m/0.04 gates unchanged. Fixed SAME-world
  restart PASS, two bodies retained0.002883m/0.009167; CSE mask31/root0/count2,
  source/startup/identity retained. Final1/1both,0retries/errors. No natural
  joint-fracture/velocity/RPC/offline/all-model acceptance. Doc65 and private
  native-summary.json retain8pre-stop log hashes plus package/config/control
  proofs. Processes stopped/debug channels empty; all4primaryFE829 exes and
  config prefixes unchanged, no rollout. L30 stays PARTIAL;188counts remain
  22complete/37code/70partial/59notstarted. Next medium persistence issue:
  CDestroyablePhysicsObject accumulated health lacks a CSE field; investigate
  a backward-compatible adapter without corrupting stock binder client_data.

- Codex BEFORE physics-skeleton checkpoint edit (2026-10-08): actual
  CPhysicsSkeletonObject is separate from CPhysicObject and omitted by the
  authority checkpoint traversal. Extend ONLY this class to capture stock
  CPHSkeleton body/mask/root/flags and XYZ pose into existing
  CSE_ALifePHSkeletonObject, with complete decode before replacement and the
  same packet bounds. Preserve source/identity/client data; no save/wire
  version or AI cadence change. Reject unresolved flSpawnCopy. Preserve
  stock flNotSave disposal rather than resurrect temporary debris. Add the
  failed inherited-spawn guard before collision/physics mutation, matching
  the already-guarded prop/breakable classes. Actual methods/traversal fixture
  and full native build remain Actions-only. Private native4fa joint-fracture
  baseline is running with zero damage/stock impulse on four objects; no
  live acceptance yet. Main exes/world/account data remain untouched.

- Codex 2026-10-08 FINAL scoped breakable PASS: source4fa43fe7d0231df3c5ff4fce4a6bb3c5af70342f,
  Foundation37719768733 + full DX1137719768724 SUCCESS. Artifact11525896846,
  validated source/ZIP/exe manifest; both exesC5D8B349... Only private
  breakable-fixed-4fa43fe7d and breakable-pending-fixed-4fa43fe7d installed.
  Same failed88d controls/initial states/original health gates:15508 retains
  health0.610000014 across SAME restart and breaks on0.5 follow-up. Naturally
  removed15509/15510 stay absent. Atomic pre-removal case saves BOTH broken
  objects present with CSE health0; SAME reload completes normal removal
  before admission, no intact objects return. Both strict native PASS, final
  1/1both phases of each,0terminal/Lua/fatal/shader/save/capture,2recovered
  phase1 admission retries total. Existing GAMMA loadout warnings remain.
  Doc64/native-summary.json retains8pre-stop log/result/driver hashes and all
  earlier failures (including invalid separate post-save removal observation).
  Initial CI allocator-double failure fixed; actual failed-base-spawn path
  defect exposed and guarded without weakening assertions. That failure path
  has fixture proof, not a forced live failure. Processes stopped/debug empty,
  all4primaryFE829 exes unchanged, no rollout. L30 now PARTIAL for this stock
  breakable type; general destroyable physics health, fractures/trajectories/
  velocities/offline routing/graphical RPC stay OPEN. No64/512/full-stage
  closure; completed188 count does not increase from subcase acceptance.

- Codex BEFORE breakable checkpoint edit: private native88d baseline
  breakable-restart-before-88d72cfea reproduces damage loss for Cordon15508.
  Stock server fire-wound0.3, control15510 breaks with0.3+0.5 in one session;
  actual saved CSE health stays1.0, SAME world loads, target survives0.5.
  Strict overall FAIL/common healthy proof PASS; naturally removed15509 and
  control15510 stay absent, final1/1both,0Lua/fatal/save,1recovered entry retry.
  Scope: CBreakableObject health->existing CSE_ALifeObjectBreakable.m_health
  before checkpoint; broken shell maps to0 (including strike with positive
  fHealth), restore zero-health as broken ONLY with-netcoop. Actual methods
  and selection fixtures on GHA, unchanged baseline thresholds/controls,
  plus pre-removal broken-state test. No new wire/save format, no NPC/AI,
  broad physics integration, primary install or general destructible claim.
  Save failure retains prior committed snapshot. Detailed tracking doc64.

- Codex 2026-10-08 additional saved-open PASS (same88d GHA): fresh private
  door-open-xyz-88d72cfea uses stock close preparation then stock use_callback
  to OPEN15921. Rotation change1.003311, SAVE committed/SAME world_b loads,
  all script/physical flags equal, both-body error0.000691m/0.007873 under
  original0.05m/0.04 gates. Final1/1both,0terminal/Lua/fatal/shader/save/capture;
  one recovered phase1retry, none phase2. Door's default is open, so this is
  complementary physical/state coverage, not a new negative binder control.
  FOUR total native cases PASS,2recovered retries total. Doc63 and retained
  native-four-case-summary.json record16 pre-stop log/result hashes; original
  three-case summary retained. Processes stopped/debug empty, four primary
  FE829 hashes unchanged. Saved open/closed/configured lock states covered;
  destruction/velocities/offline route/graphical RPC remain OPEN, L29 partial.
  No deployment, no64/512/188-counter closure.

- Codex 2026-10-08 FINAL door/prop native scope PASS: source88d72cfeaa6ba9fce94175fbc8e61cfe82906c84,
  Foundation37700338252 + DX1137700338212 SUCCESS; artifact11518765311,
  validated exact source/ZIP/exe manifest (both exes0AF38FFF...). Only private
  roots door-lock-xyz-88d72cfea, door-restart-xyz-88d72cfea and
  prop-table-xyz-88d72cfea installed. Trader15923: stock configured lock and
  actual NPC lock survive SAME world restart; both-body error0.006922m/
  rotation0.011048. Original full initial matrix equals failed ba82 control.
  Wooden15921: stock server use callback closes initially open door; remains
  ph_door@close/physically closed after SAME restart,0.007575m/0.007873.
  Original table16773 full initial matrix equals ff78 failed control; force
  moves3.398434m/rotation1.329826, pose retained0.001266m/0.008451 after
  SAME restart. Original gates0.05m/0.04 unchanged, all3strictcomparators PASS.
  Final1/1both phases of all3;0terminal/Lua/fatal/shader/save/capture errors,
  one recovered admission retry (wooden phase1). Existing GAMMA NPC Loadouts
  warnings retained. Doc63/native-summary.json records12 pre-stop log/result
  hashes and exact package provenance. All processes stopped/debug empty;
  all4primaryFE829 exes/worlds/accounts unchanged, no rollout. L29 remains
  PARTIAL for destruction/fracture, moving velocities, offline-route
  enforcement and graphical player RPC/use-distance.64/max-view/512 and
  historical188 totals stay OPEN/unchanged. Next follow easy→medium→complex
  ordering, preserve normal entry; do not install broad overlays/exes merely
  from these3private cases. Prior failures/controls remain intact.

- Codex BEFORE Euler correction:780 native wooden door15921 PASS state+both
  body poses (0.005344m/0.007873rotation), but trader15923 lock test overall
  FAIL despite script/NPC lock now retained: leaf shifted1.991m/rotation1.026.
  Actual cause identified: adapter getHPB writes yaw into x, while existing
  CGameObject::net_Spawn uses setXYZ(o_Angle), expecting pitch in x/yaw in y.
  A yaw90 doorway spawns joints rotated90 around the wrong axis; saved global
  bones cannot repair wrongly built joint axes. Scope: getXYZ and actual
  xrCore matrix+actual adapter/spawn setXYZ roundtrip fixture, no spawn or
  simulation changes. Preserve both failures, same native controls after GHA.

- Codex BEFORE door logic changes: actual Cordon15921 wooden door, stock
  authoritative use callback ph_door@open→ph_door@close, physical close proven,
  SAVE committed, SAME retained world loads; restart resets script section to
  ph_door@open and reopens it (rotation error1.008357). Native baseline FAIL,
  logs clean, evidence _build/live/door-restart-before-ba82c7734 retained.
  New scope: ONLY initialized ph_door props serialize their own generic binder
  chunk plus shell enable byte into CSE client_data; physics adapter unchanged
  for furniture. Call door binder directly so exceptions propagate (ordinary
  CScriptBinder::save clears binder and hides errors). No Actor/task/inventory
  net_Save, no whole ClientSave or simulation/AI changes. Stage classifier in
  zz_netcoop_world_rules; actual adapter/selection/exception tests, GHA build
  then SAME native door control and furniture regression, primary unchanged.

- Codex 2026-10-08 FINAL scoped physics pose PASS: exact ba82c7734 GHA
  Foundation37688229874 + DX1137688230023 SUCCESS, validated artifact11513411413;
  both exes844FA785... Private prop-table-fixed-ba82c7734 tests ORIGINAL
  table16773, initial matrix EXACTLY equals failed ff78 baseline. Force moves
  3.509865m/rotation1.191007, saved/moved equal, SAME slot_b retained restart
  error0.000701m/rotation0.004414 inside predeclared0.05m/0.04. Final1/1both
  phases,0terminal/Lua/fatal/shader/save/capture errors;1recovered phase1retry.
  First fixed nearest-prop run selected a vise16838, insufficient movement;
  rejected acceptance retained, thresholds not relaxed. First private package
  launch lacked supplementary GAMMA DLLs; stopped before any world/log,
  stock libraries supplied with hashes. Detailed evidence/limits doc62.
  Processes stopped, debug empty, four primaryFE829 exes unchanged. NO full
  L29/188 or graphical64/max-view closure. Next: actual door on another map
  (Marsh jointed props are vise/projectors, no door); check binder/lock state
  and offline route separately, keep primary unchanged until rollout validation.

- Codex 2026-10-08 resume after accidental poweroff: physics checkpoint source
  ba82c7734a6b17796365d934cd9fad6fcb61a863 pushed. Foundation37688229874
  SUCCESS GCC/sanitizers + MSVC. DX1137688230023 native checks PASS, full
  engine building. First1c1 CI Windows failed only mock warnings under/WX;
  successor changes fixture names/typed keys, not runtime. Capture actually
  decodes SPHBonesData into temporary storage (same CSE_PHSkeleton codec),
  then replaces bones/flags/root pose; metadata/source ID retained.
  Private fixed root _build/live/prop-restart-fixed-1c1d4e383 prepared;
  probe.json pins exact ba82. No binaries installed there yet. Next download
  validated package (built-from+manifest), copy only bin/dedicated into that
  new root, run run-prop-restart.ps1 then compare-pose.py. Original baseline
  fails same strict comparator (3.811m, rotation1.0084); tolerances declared
  before fixed run:0.05m/0.04matrix coefficient. Primary four exesFE829...
  unchanged, no game process. L29 and64/max-view still OPEN.

- Codex 2026-10-08, L29 baseline FAILED: prop16773 mar_physic_object_0008,
  actual world checkpoint committed, SAME world loaded, pose вернулась ТОЧНО
  в initial (3.811m от saved). До изменения кода записываю scope: PhysicObject
  wrapper для стандартного CPHSkeleton::SaveNetState→CSE_PHSkeleton::load,
  server-only capture перед ALife checkpoint; без inherited net_Save/Lua actor
  hooks/общего ClientSave (раньше падал на dedicated). Actual adapter/selection
  fixtures и fail-closed world-store case, компиляция только GHA. Primary не
  менять. Original failure/logs/matrices сохранены в prop-restart-before-ff78b4197.

- Codex перед L29: только native probe в НОВОЙ папке prop-restart-before-
  ff78b4197, verified ff78 exes. Один игрок, выбираю движимый nonbreakable
  obj_physic, сохраняю матрицы ВСЕХ физических тел до/после force и после
  netcoop_world_save, затем restart SAME world/character без cleanup/reseed.
  До результата source physics/world-store не менять; whole L29 не закрывать
  только по совпадению object position (у hinged doors важны body rotations).

- Codex doc61 bounded64 завершён: final64/64,4recovered admission retries,
  0terminal/Lua/fatal/save ошибок.45NPC/27mutants, все64 рядом с9friendlyNPC.
  Dense last6 p5013–14/p9570–96ms, main/callback gaps остаются большими.
  Безопасного быстрого решения не найдено,64/max-view OPEN; по последнему
  указанию владельца перехожу к остальному. Никакой primary promotion.
  Ordinary primary-FE process/login-UI startup прошёл в private appdata;
  full3D/Firebase вход НЕ проверены, primary account/draft hashes неизменны.
  Ошибка$fs_root$ была BOM только в тестовом конфиге; исправлена и сохранена
  как negative harness evidence. После выключения ПК probe повторён успешно
  в пределах process/UI initialization. Данные/логи _build/live/64-baseline-
  ff78b4197 и menu-smoke-primary-fe829. Следующая средняя задача L29:
  сохранность физического prop/двери при рестарте, только в новой private папке.

- Уточнение владельца после приоритета64: если безопасного решения пока нет,
  оставить64 OPEN и перейти к остальному; главное сохранить штатный вход.
  Codex: проверяю ordinary graphical client на SAME primary FE829 exe,
  client/config/scripts, но с отдельной appdata без auth credentials/characters.
  Затем один ограниченный64 baseline+profile на verified ff78 private exes;
  никаких изменений поведения ИИ без доказуемой эквивалентности, no primary
  promotion. Новые измерения/ограничения записывать в doc61.

- НОВЫЙ ПРИОРИТЕТ владельца 2026-10-07 после doc60 PASS: автономно сначала
  максимально закрывать64игрока/плавность, потом остальные пункты. Это
  заменяет прежний порядок easy→medium→hard и следующий L29 ниже. Не снижать
  население/частоту ИИ/скорость игроков и не закрывать max-view только по ботам.

- Последний итог Codex 2026-10-07: ff78b4197 GHA37665981680/37665981691 PASS;
  private checksum-fixed-ff78b4197: mixed NCH7→NCH8 и retained restart PASS.
  По20/20 переходов в каждом прогоне (40всего), final4/4 в обоих; 0ошибок.
  96captured observations, все24UID/full encoded item state и5profile fields
  совпали с оригиналом; startup SHA совпал с последним файлом предыдущего
  прогона; storage revisions monotonic, никаких исключённых плохих записей.
  Доказательства и предыдущие провалы сохранены; подробности/ограничения doc60.
  Probe процессы остановлены, primary exe FE829FF4... без изменений.
  Ниже pause/resume/pending записи исторические. Следующая средняя задача:
  L29 — проверить сохранение открытых дверей/сдвинутых props после рестарта
  в НОВОЙ private папке. Старый run-prop-test.ps1 удаляет appdata recursively;
  его нельзя запускать на retained worlds, нужен безопасный isolated driver.
  После средних задач — сложная64/max-view. Не закрывать её по bot reliability.

- Возобновлено по просьбе владельца 2026-10-07. Foundation37665981691 и
  DX1137665981680 завершились SUCCESS на exact sourceff78b4197. Скачиваю
  проверенный пакет для подготовленного private fixed probe; затем mixed
  NCH7 migration и retained NCH8 restart со строгим сравнением всех записей.
  Предыдущая пауза ниже — историческая запись, запрет запуска снят владельцем.

- ПАУЗА по прямой просьбе владельца 2026-10-07 21:21. Source исправления
  item-readiness: ff78b4197c8ec08c42da6edc68b496ea56161318, уже pushed.
  Foundation37665981691: Linux PASS, Windows ещё идёт; DX1137665981680:
  checks PASS, full engine ещё идёт. Сборки не отменены. Игровых probe
  процессов нет; новые тесты не запускать до просьбы продолжить.
  Следующее действие после возобновления: проверить оба CI, скачать и
  валидировать exact ff78 package через _build/live/quick-transitions/
  fetch-artifact.py (API per-request resolve140.82.121.5; при необходимости
  обновить через официальный HTTPS DNS), затем private fixed probe
  _build/live/checksum-fixed-ff78b4197. Там уже подготовлены те же четыре
  mixed NCH7 входа и оба сохранённых мира, bin/dedicated ещё нет.
  install-verified-package.py ожидает cache _build/gha/checksum-fixed-ff78b4197,
  run37665981680/sourceff78. Запустить run-checksum.ps1 с Runtime этой папки,
  GameWorkingDirectory ../gamma-runtime, Bots4/BotProcesses2/Minutes3,
  BotsBelowNormal, ServerArgs '-dedicated -netcoop_world_save_period=30',
  BotArgs '-dedicated -netcoop_fake_loss=5 -netcoop_fake_lag=120'; параллельно
  capture-items.py. После завершения inspect-upgrade.py, prepare-restart.ps1,
  run-restart.ps1 (те же параметры) + capture-restart-items.py, затем
  inspect-upgrade.py и final-acceptance.py. Нельзя исключать плохие observations.
  Не пересоздавать legacy-before/inputs: они готовы. Старый провал и rev60
  сохранены в _build/live/checksum-ed08716d3. Doc60 acceptance НЕ закрыта.
  Все четыре primary exe остаются FE829FF4...; 64/max-view всё ещё OPEN.

- Codex 2026-10-07: NCH8 native migration PASS, но restart strict observer
  поймал промежуточную запись nbot_002 с UID0/default medkit (rev60), затем
  rev61 исправилась. Приёмку НЕ закрываю. Трогаю item readiness/character
  restore+capture guards и actual-method fixtures: структура/parent уже
  готовы раньше budgeted item scan, поэтому старый admission gate снимается
  до применения saved UID/portions. Оригинальные logs/history сохраняю.

- Codex 2026-10-07: следующая средняя задача — NCH8 с явным canonical raw
  CRC32C и чтением NCH3–7 обоих старых CPU вариантов. Трогаю character I/O,
  scoped helper/header, actual-reader/writer fixtures и CI/project registration.
  xrCore/crc32 и форматы архивов/мира оставляю без изменений; world digest уже
  FNV64. Новый формат только private до native проверки миграции/рестарта.

- Codex 2026-10-07, последний итог: source5fded GHA build37653762280 PASS;
  четыре бота/две карты/5% loss/+120ms: 32/32 завершённых перехода, final4/4,
  0 terminal/Lua/save ошибок. Все24 UID и полное encoded item state неизменны
  после рестартов и переходов; native bounty cause/fix доказан (док59).
  World-rules Lua установлен в primary; новые exe только private.
  Сложная64/max-view плавность открыта. Следующая средняя задача: совместимость
  checksum character/world между SSE4.2 CRC32C и IEEE fallback, с миграцией;
  не менять общий crc32 движка без fixtures/совместимости архивов и сохранений.

- Codex 2026-10-07: native BountyRetireProbe PASS (реальная event queue,
  старый spawn callback удалён, late callback завершён, state callback тот же).
  Ставлю только repo world-rules Lua в обе primary server/scripts после
  проверки совпадения с предыдущим repo вариантом и резервного копирования.
  Основные exe остаются прежними; native bot-fix build ещё идёт.

- Codex 2026-10-07: bad-network probe выявил два дополнительных дефекта:
  bot update объявлял disconnect до чтения уже полученного handoff; таймер
  bounty spawn обращался к nil actor, хотя создание bounty уже запрещено.
  Трогаю `netcoop_bots.cpp`, его actual-method fixture и world-rules guard/
  fixture; сохраняю обычный disconnect как провал и existing bounty state.

- Codex 2026-10-07: продолжаю native selftest в отдельной private-папке:
  переходы двух карт при 5% loss/+120ms и состояние предметов (condition,
  portions, magazine, ammo stack) до/после рестарта. Производственные exe,
  население и частота ИИ не меняются; старые доказательства сохраняются.

- Приоритет владельца 2026-10-07: сначала закрывать лёгкие и быстрые задачи,
  затем средние, затем сложные. Трудную оптимизацию64/NPC сохранять в очереди,
  пока есть более быстрые полезные исправления; не выдавать её за завершённую.

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
6. Плакат «Революционный проект «Фолк Восянка»» в 3D меню: генератор готов
   (`tools/make-soviet-poster.py <фото>` → `client/textures/netcoop/poster_folk.dds`),
   `build-lostzone-room.py` вешает его на заднюю стену (x -1.6..-1.0, y 1.36..2.26)
   только если DDS есть. Ждёт фото от владельца (файл не сохранён на диск);
   после генерации: пересобрать комнату, overlay patch, коммит. Комната: `scripts/build-lostzone-room.py`,
   задняя стена Z1=3.0, текстура в `scripts/netcoop-overlay/client/textures/`.

## Журнал

- 2026-10-06 (Claude) — память сервера локации: DX11 грузил все текстуры (2.2 ГБ) на
  dedicated → исправлено в `2f55034`; prefetch моделей держал 2.8 ГБ вершин в shared
  memory → все запуски серверов с `-noprefetch`. Итог: ~3–3.5 ГБ → 1.4–1.9 ГБ рабочей,
  private 5.1 → 2.4 ГБ. Кластер 3 карт (Болота/Кордон/Свалка, `-Maps`): 73 и 53
  перехода ботов без ошибок; release чужого населения 114 отрядов.

- 2026-10-06 02:40 (Claude) — `5b444d1` установлен в gamma-runtime и
  LostZone-3D-Hideout (клиент владельца). Контрольный кластерный прогон: 28
  переходов, 0 отказов, 1 таймаут переподключения бота в момент остановки теста.
  Чек-лист владельца: doc 46. Сообщения об отказе перехода — по-русски
  (st_netcoop_passage_*).

- 2026-10-06 02:20 (Claude) — реальные серверы, overlay `5cf8161` на exe `5302a58`:
  «released 129 squad(s), 218 NPC(s) of other maps» (H11-lite работает), switch
  distance 650 м, 16/16 переходов, fatal 0. GAMMA printf подставляет только %s —
  все %d/%.2f в overlay заменены, статическая проверка в CI. Codex: копий чужого
  населения в location process больше нет — можно решать про включение
  `-netcoop_npc_transit` по умолчанию.

- 2026-10-06 01:50 (Claude) — кластер на `5302a58`: 97 переходов без ошибок, сохранения
  мира на обоих серверах, календарь догоняет (factor до 40). БАГ: в GAMMA
  `SIMBOARD.squads[id] = true`, а не объект отряда — release_foreign_population
  и `netcoop_transit.depart` индексировали boolean. Исправлено в обоих (transit —
  зона Codex, правка минимальная: `alife():object(id)`), фикстуры теперь
  моделируют `id -> true`.

- 2026-10-06 01:20 (Claude) — билд `5302a58` установлен в gamma-runtime.
  `scripts/run-world-restart-test.ps1`: «[world] saved selftest_restart_a (periodic)
  in 207 ms» → перезапуск → «loading saved world selftest_restart_a», игровое время
  продолжилось. ПЕРВОЕ успешное сохранение/загрузка мира на реальном сервере.

- 2026-10-06 00:10 (Claude) — самотест на билде `8d586d8`: 96 переходов, 0 ошибок.
  НАЙДЕН БАГ: в `netcoop_server_compat.script` цикл AddUniqueCall вызывал
  `owned_objects_update/stash_visits_update/keep_switch_distance`, объявленные
  `local` ниже по файлу → nil globals, ошибка каждый кадр, ни одна из трёх
  функций (мебель/тайники/визиты в тайники/switch distance) в игре НЕ работала.
  Исправлено forward-объявлением (`2139a01`), CI-проверка
  `scripts/check-netcoop-lua-scope.py`. Codex: lupa-фикстуры вызывают функции
  напрямую и такое не ловят — проверять и сам цикл.
  World save: ни одно сохранение мира не прошло ни в одном логе (owner/selftest).
  Причина: `Level().ClientSave()` в `world_store_save_now` падал (SEH, catch(...))
  в Objects_net_Save на dedicated до первого M_SAVE_PACKET (которые netcoop и так
  отклоняет). Убрано в `846664a`; ждёт проверки на реальном сервере.

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

- Codex: backend contact corridor index + admin offline_contacts now selects
  candidates by spatial cells and segment time windows, uses continuous narrow
  phase, excludes group members, reserves pending combat, commits earliest
  disjoint pairs atomically. Overflow fails whole admission (no truncation).
  Full local backend 90 PASS; native/runtime files not changed. Route-change
  subscriber/replanning, large-map windowing/native adoption still pending.
- DX11 8d586d8f9 / 37367011993 attempt 2 SUCCESS, artifact verified present.
  Installation/selftest remains Claude's area; no installer/runtime edits by
  Codex. This package has v2 transit API and wallet/account durability fixes.

- Native fixture follow-up: latest a5702564c DX11 run 37371467639 failed before
  engine compilation, because cluster_move now calls cluster_target_problem
  and the isolated player-transfer fixture had not included that dependency.
  Codex updated its fixture to extract the ACTUAL target availability helper
  and TTL (rather than return a hard-coded success), plus tests for unreadable,
  stale, malformed, full and available target status. Native verification must
  run on Actions; no local compiler used. Runtime installation remains Claude.

- Codex backend Hazards: offline_hazard, captured anomaly/trap state, full
  individual/item/motion captures, equipment condition protection, deterministic
  avoidance, permanent death/same-ID corpse loot, cooldown/one-charge/evidence
  transaction. Group-member trajectories preserve turns and offsets. New
  arrivals priority 10 after contact priority 0; old arrivals not rewritten.
  14 new tests, full local backend 104 PASS. Not adopted by native AI/volumes;
  discovery/replan/emission/shelter/artifact effects still pending. No runtime
  or native engine source edits. gamma-runtime marker now 8d586d8f9 (read-only).

- Codex: quest/locked stash protection at plan+commit, individual catalog/item
  quest markers for automatic take/deposit; shared corpse quest pin query.
  Added byte admission to combat/hazard captures and streamed inventory/member
  limits. Six new tests, full local backend 110 PASS. Native/GAMMA flags still
  need adapter mapping. fc0ef544a Foundation 37372547105 SUCCESS GCC/MSVC;
  DX11 37372547180 queued. f40d63326 backend 37371605344 Windows SUCCESS (90),
  Linux failed runner acquisition (no tests executed); new backend pending.

- Coordination note before edit: Codex is fixing silent player inventory
  truncation in netcoop_characters.inc (character-save/transfer safety), with
  actual native helper coverage in its existing player-transfer fixture.
  Claude's replication/world-store/Lua-scope/runtime changes are left alone.

- Native player snapshot completeness: netcoop_characters.inc now preflights
  all child IDs/parents/inventory types/cycles/depth/count before clearing the
  previous snapshot. Invalid/over-limit capture refuses save, so transfer abort
  preserves source/old file instead of losing some items. Actual helper tests
  included in check-netcoop-player-transfer.py; local syntax only, native Actions
  pending. Foundation now triggers on netcoop_characters.inc as well. Other
  actor's dirty world-store/Lua-scope/overlay files excluded from this commit.

- Codex: death/last-member group events enqueue durable quest failures in the
  death transaction. Consequences run without player polling in atomic batches
  of 64, preserve original evidence across restart/handoff, release corpse pins
  after failure, and never reward/respawn. Shared per-World scheduler handlers;
  bounded legacy recovery via admin quest_reconcile/after_entity/next_after.
  Missing death evidence stays held and cannot block cursor progress.
  Native quest event/UI adoption remains separate.
  Full local backend 117 PASS; native/runtime paths untouched in this change.
- Verification: 6dd10b37b Foundation 37373918198 SUCCESS GCC/MSVC; DX11
  37373918186 checks SUCCESS, engine compiling. b317ac297 backend
  37372725746 SUCCESS Windows+Linux (104). 2a12b6de6 / 37373382669 Windows
  SUCCESS (110), Linux cancelled. Backend-only follow-up will not cancel DX11.
- NPC transit default decision: H11-lite does not prove full old-world state
  migration/unique global population, and mailbox WorldID/cross-host fencing,
  mod-state remapping and real paired-checkpoint failure acceptance remain.
  Keep -netcoop_npc_transit opt-in; no launcher/default changes by Codex.
  Do not count generic foreign-map release as acceptance of automatic transit.

- Codex: offline_hazards location discovery via budgeted 3D corridor queries,
  exact individual member paths/offsets, hazard radius/cooldown/immunity.
  Common combat/hazard reservations now cancel stale captures before their due
  time and atomically replan; journal failure rolls cancellation back too.
  Bounded streaming backlog/state capture, no silent truncation. Ten new tests;
  full local backend 127 PASS. Still explicit passes, not automatic route-change
  subscriber or globally ordered combat/hazard planner; no native adoption.
- Confirmed: 6dd10b37b DX11 37373918186 SUCCESS, Foundation 37373918198 SUCCESS;
  285c569c6 backend 37376503077 SUCCESS Windows+Linux, 117 tests. Installation and
  real exe testing remain Claude's area; Codex did not overwrite runtime.

- Coordination before native edit: Codex is fixing the local-host account
  claim race/stale resumed writer using an OS-held per-account ownership file,
  plus storage front-end cross-location exclusivity and auth-failure release.
  Areas: netcoop_cluster.inc, finish_auth in netcoop.cpp, isolated Actions
  ownership fixture/workflows. Runtime/world-store/replication left alone.

- Native lifetime account ownership now holds an exclusive OS file handle
  through the whole session/save drain. Concurrent/local duplicate claims,
  TTL stealing of a stalled process and non-owner release are refused;
  create/fsync/rename failure releases without admitting. Slot-zero storage
  claims/refreshes/releases account state; rejected character selection releases.
  Actual Windows subprocess/barrier/crash/I/O fixture added to Actions; syntax
  only checked locally. Every cluster process needs the matching new binary;
  old servers ignoring ownership files and cross-host writers are not fenced.

- Verification: 5302a58f4 Foundation 37378444819 SUCCESS GCC/MSVC, actual Windows
  ownership fixture PASS after correcting a strict fixture-only variable
  shadow warning. DX11 37378445074 native checks SUCCESS, engine compiling.
  1d8004572 backend 37377564300 SUCCESS Windows+Linux (127).
- Codex combined offline_plan: one planning instant, globally earliest
  combat/hazard choice, preempts later valid captures when a new earlier trap
  appears; retains prior RNG/EventID at equal time. Atomic cancel+replace,
  bounded admission, no health/ammo mutation during planning. Eight new tests;
  full local backend 135 PASS. Route-change subscriber/native adoption pending.

- Coordination: Codex follows up netcoop_characters.inc with bounded background
  save count/bytes, pending complete-snapshot coalescing, in-flight accounting
  and process-unique temporary names, plus actual helper Actions coverage.
  Will preserve the running 5302a58f4 DX11 build before the next native push.

- Coordination: native disconnect cleanup currently erases/destroys a tracked
  Actor even if its synchronous character save failed. Codex will retain/retry
  that Actor and ownership until the snapshot commits, with actual cleanup
  function coverage in the player-transfer fixture. netcoop.cpp area noted;
  world-store/runtime/replication remain untouched.

- Prepared native follow-up: bounded 256-pending/32-MiB commit queue (in-flight
  bytes included), complete pending snapshot replacement, process/u64 unique
  temp names and rejected/failed temp cleanup. Actual threaded helper and
  Windows fsync/rename fixture added; Actions pending.
  Failed tracked logout save now retains Actor/link/ownership and requeues
  cleanup; success alone releases/removes, corpse/moved/untracked policies
  preserved. Actual cleanup and ninth-leaf ownership tests in transfer fixture.
- Backend geometry work now shares the broad/narrow budget. Full local 136
  PASS; 9f26f5b92 backend 37379314800 SUCCESS Windows+Linux (135).
- 5302a58f4 DX11 37378445074 SUCCESS, full package includes ownership and
  846664a26 world-save fix. Running build completed before this native push.
  Installation/native world-save/restart acceptance remain Claude's area.

- Coordination: Codex will make native progress capture fail closed before
  Actor/inventory mutation in character_save_actor (netcoop.cpp and
  netcoop_characters.inc). Missing/throwing Lua capture and oversized tasks or
  progress currently silently save an old quest snapshot as success. Coverage
  extends the existing Actions player-transfer fixture; runtime unchanged.
- 024fbef42 corrects fixture-only MSVC narrowing in the disconnect test; native
  Actions pending. f4803b1c0 backend 37380934586 SUCCESS Windows+Linux (136).

- 024fbef42 Foundation 37381694426 SUCCESS GCC/MSVC, queue/disconnect tests
  pass. DX11 cancelled by README push 1c7099246; not a compile failure.
  Progress capture now refuses missing/throwing Lua or oversized task/info/
  script/origin data before Actor/inventory mutation; transfer fixture includes
  actual progress function, 512/513 boundary and previous-snapshot retention.
  Python syntax only locally; progress native checks pending on next push.

- ad4725002 Foundation 37382384401 SUCCESS GCC/MSVC: actual progress capture
  checks pass. DX11 37382384355 checks SUCCESS, engine compiling.
- Backend contact entry avoids catastrophic quadratic cancellation for small
  spheres/long routes; combat shares hazard boundary tolerance. Geometry and
  actual captured-fight regressions added, full local backend 139 PASS.

- Backend group contacts now index living individual corridors/formation
  offsets/turns and reserve one group pair; intra-group pairs excluded, centre-
  only phantom combat refused before damage/ammo. Participant/segment/byte/
  broad+narrow admission retained. Five tests, full local 144 PASS.
  7fac62827 backend 37382911385 SUCCESS Windows+Linux (139); native build left
  running. Still whole-group coarse outcomes, no route-change subscriber.

- Coordination: Codex will bound repeated failed logout capture to once per
  Actor per second (wrap-safe timer, duplicate disconnect IDs coalesced) in
  destroy_pending_actors. Synchronous character temporary files will also be
  removed on write/fsync/rename refusal, with actual Actions fault coverage.
  Areas: netcoop.cpp/netcoop_characters.inc and existing two fixtures.
  Will wait for ad4725002 native build to finish before the next native push.

- ad4725002 DX11 37382384355 SUCCESS, full package produced; Foundation
  37382384401 SUCCESS GCC/MSVC. 3ad35e0ca backend 37383338666 SUCCESS
  Windows+Linux (144). Runtime left to Claude.
- Prepared follow-up: failed logout capture retries once/second per Actor;
  duplicate callbacks coalesce, u32 wrap handled, ownership held until save.
  Synchronous save completion removes refused temps (old durable file stays).
  Actual helper fault/boundary fixtures expanded; native checks pending.
  Previous full native build completed before pushing this follow-up.

- 970ef6658 Foundation 37384373144 SUCCESS GCC/MSVC, actual backoff/duplicate/
  u32-wrap and Windows synchronous write/fsync/rename/temp-removal tests pass.
  DX11 37384373508 checks SUCCESS, engine compiling; runtime left to Claude.
- Backend snapshots now account exact canonical UTF-8 envelope/escaped rows
  during cursor reads before retaining oversized records. 128-MiB default,
  trusted smaller budget, old snapshots/journal preserved on refusal.
  Exact-boundary/Unicode and guarded early-read tests, full local 146 PASS.
  No total-RSS claim; no native checkpoint change.

- d68758147 backend 37384735948 SUCCESS Windows+Linux (146).
  Offline/combat/hazard/scavenging constructors now reject foreign World or
  Scheduler before changing handlers. Two real-DB composition refusal tests;
  full local 148 PASS. Not distributed native world fencing.

- 67dea8b64 backend 37385134369 SUCCESS Windows+Linux, 148 confirmed in logs.
  Living-member capture now projects dead state as NULL in SQLite, avoiding
  unnecessary blob reads; stored casualty state/roster untouched. Existing
  full suite remains 148 PASS locally after this change.
- 970ef6658 DX11 37384373508 CANCELLED by 5cf816177 overlay push (not compile
  failure). Current DX11 37385428435 includes all native fixes: checks SUCCESS,
  engine compiling. Latest successful native package ad4725002/37382384355.
  Please preserve the running package build; backend/docs-only pushes are safe.

- Final check before the current usage window is exhausted: 4b8a20285 backend
  37385808762 SUCCESS Windows+Linux (148). Current native 37385428435 is still
  compiling; its completed checks and 970ef6658 Foundation are SUCCESS. No
  native runtime installation by Codex. All Codex changes committed/pushed.
- Next safe priorities: inspect completion of 37385428435 without starting a
  competing native build; actual runtime acceptance belongs to Claude. Then
  gate target player readiness on successful full progress restore (capture
  now fails closed, restore still swallows Lua failure). Keep native NPC transit
  opt-in until mailbox WorldID/fencing/global population/mod-state acceptance.
- Backend automatic contact planning needs an event-time mutation barrier:
  merely queueing a pass and using current time can skip a contact crossed
  while processing was delayed, or invalidate an earlier route before combat
  applied. Preserve old physical capture/history and resolve due dependencies
  before changing routes/representation. Do not enable an unproven timer scan
  as a substitute for that barrier or claim native chunk/LOD adoption.

- Resume verification: 5b444d198 DX11 37386643593 and Foundation 37386643524
  SUCCESS; 1b56f2e6c DX11 37389490303 SUCCESS. These include the last Codex
  native fixes; Claude recorded installation of 5b444d1 for owner testing.
- Coordination before edit: Codex is fixing target character restore refusal
  (Lua failure currently swallowed), complete saved inventory admission and
  pending-character gameplay packet gating. Areas: netcoop.cpp,
  netcoop_characters.inc/netcoop.h, narrow OnMessage gate in xrServer.cpp,
  Actions restore fixture. No replication policy/world-store/runtime edits.

- Prepared target restore barrier: whole saved/starter inventory tracks runtime
  parentage and complete creation; progress returns false for missing/throwing
  Lua or invalid scalar/footer envelopes. Pending entry retained/retried once
  per second, gameplay packets/task publication/autosave/wallet held.
  Actual helper/caller fixture added to Actions; Python syntax only locally.
  No invisible spawn/full task-binary validation/arbitrary Lua rollback claim.
  Permanent failures stay held for repair/restart; unfinished-login cancellation
  needs safe runtime item rollback before releasing account ownership.

- b3fbca66e Foundation 37410997235 SUCCESS GCC/MSVC, full DX11 37410997168
  SUCCESS. No Codex runtime installation. Follow-up keeps pending net_Ready
  metadata and validates/consumes input sequence without queuing movement, so
  a restore longer than the 10,000-command window cannot lock out control.
  Actual decoder fixture covers 12,000 commands, malformed/replay/angles/window,
  wrap and first-ready input. Native follow-up awaiting Actions after push.
- Backend world-state/scale/timeline/route/dehydrate/hydrate admission now
  settles prior due events at one frozen cut in the command transaction.
  Atomic refusal on stale capture/error/64-event or 5-ms exhaustion, background
  batches unblock retry. Local suite 159 PASS. No automatic contact planner
  or native AOI/LOD adoption enabled; resolver execution fencing/duration and
  native authority bridge still open. Backend Actions pending after push.

- be790c22c Foundation 37412839032 SUCCESS GCC/MSVC, backend 37412839047
  SUCCESS Windows+Linux (159). DX11 37412839020 checks SUCCESS, compiling.
  Do not cancel by a native push; upcoming backend/docs-only push is safe.
- Prepared optional trusted `offline_planning` observer on route/dehydrate/
  hydrate/scale/relations: same-cut/same-Tx discovery, deterministic source
  identity, max-25 locations/time admission and journal. Default remains off
  for native shadow authority. Only configured horizon is covered; durable
  continuation and resolver/AI-driven replanning remain open. No runtime
  install, native population/replication edits or claimed task-43 closure.
- Automatic subscriber complete local suite 171 PASS, including the real
  authenticated HTTP route->hazard discovery transaction. Actions pending.

- 38d674d0d backend 37413594493 SUCCESS Windows+Linux (171).
  Native 37412839020 still compiling with successful checks; no native push.
- Durable OfflineContactsWindow follow-up: one continuation per location
  while a physical route extends beyond the configured horizon; discovery
  starts at captured due time despite late processing. Atomic source mutation
  replacement, restart/missing-policy refusal, deterministic generation/RNG,
  priority 20 after contact0/arrival10. Moving-root filter/no routes stops
  stationary fight loops. Local full 179 PASS. Actions pending after push.
  Next open work: AI decisions after outcomes and native adapter adoption;
  do not turn on NPC transit or native authority merely because fixtures pass.

- a9c913f7f backend 37414060576 SUCCESS Windows+Linux (179).
- Coordination before edit: Codex is tightening character_save_actor's cache
  lookup, so a missing immutable capture cannot create a default Character.
  Areas: netcoop_characters.inc and actual restore/caller fixture. No actor
  teardown/runtime/replication edits. Push native only after 37412839020 ends.

- 37412839020 full DX11 SUCCESS. Before native push Codex is also moving
  disconnect wallet commits onto main-thread Actor cleanup: the transport
  callback currently touches restore/account maps concurrently. Wallet save
  refusal must retain Actor/account ownership, like character-save refusal.
  Areas: netcoop.cpp and actual player-transfer/wallet fixture. No replication,
  ALife teardown or runtime installation changes.

- Prepared native patch: existing-only character cache helper refuses pending/
  missing/repointed capture; no operator[] insertion on save. Transport callback
  no longer reads restore/account maps or saves wallet. Main-thread tracked
  slot-1 logout commits wallet only after character capture, before ownership
  release; account failure retains Actor/dirty wallet and retries. Actual
  cache/wallet/disconnect fixtures expanded; syntax only locally, Actions next.

- 45377df6c GCC pass, MSVC /WX caught account-variable shadowing a fixture
  global; 268caa26d renamed it. Foundation 37414908176 SUCCESS GCC/MSVC;
  DX11 37414908195 checks SUCCESS, compiling. No native push until it ends.
- Backend Transfer Prepare now streams exact canonical checkpoint admission
  before token/freeze, membership metadata before full blobs, reuses encoding.
  Default one MiB unchanged, smaller trusted constructor budget. Local 182 PASS,
  exact UTF-8 boundary and guarded early inventory/group reads; Actions pending.
  Native character/account files are still independent commits; coherent
  world/player crash transaction and every native transfer wallet path remain
  open. No new runtime installation or task-43 whole-stage closure claimed.

- b54a82bda backend 37415278999 SUCCESS Windows+Linux (182).
  Native 268caa26d/37414908195 still compiling; no native push.
- Prepared causal outcome refresh: Scheduler invokes observers after APPLIED
  within source Tx; RouteArrived/combat/hazard/stash queue physical-time
  refresh priority5. Arrival no longer loses a later encounter; queue failure
  rolls source back, restart preserves time, no active routes skips discovery.
  Same-location/time PENDING refreshes coalesce with journal links; later
  sources after APPLIED get new IDs. Local full 188 PASS (tests, not tasks),
  backend Actions pending after push. New AI choices/native bridge still open.

- 0fca6dd9f backend 37416191989 SUCCESS Windows+Linux (188).
  268caa26d full DX11 37414908195 SUCCESS, Foundation 37414908176 SUCCESS.
- Automatic stash discovery integrated into shared contact Planner/HTTP with
  same authority/catalog. Actual NPC/group-offset paths; earlier combat/hazard
  wins shared root, stash reservations prevent simultaneous visits. Protection,
  per-NPC + per-stash cooldown, existing light item IDs only; no new loot/respawn.
  Bounded discovery and streamed visit admission; guarded oversize rollback/retry
  and forbidden weapon exclusion. Local full 198 PASS, Actions pending after push.
  Native adapter/new AI route choices/4 LOD/AOI remain open. No native launch,
  installation, runtime overwrite, automatic NPC transit or whole-stage closure.

- 1dd83e4c3 / 37417841819 Windows SUCCESS (198), Linux failed in existing
  HTTP delivery test: response arrived before workers finished bounded socket
  drain/close, legitimate overload503 versus expected400. Test now synchronizes
  cleanup admission; new gated real-socket regression proves response delivery
  does not prematurely free slots and normal admission resumes. Product worker
  cap unchanged. Local full 199 PASS, follow-up Actions pending.
  Task-43 H historical TTL description marked superseded; current native/backend
  proof and open hidden spawn/cross-host/NPC/1000-transfer acceptance documented.

- d3da468b5 / 37418041291 backend SUCCESS Windows+Linux (199 each).
  Follow-up HTTP synchronization/gated cleanup tests passed. Stash discovery
  backend verified, native adoption and W8-W12 whole-stage acceptance open.
  Checkout clean after exact-file documentation commit; no runtime changes.

- Current backend replay authority tightened: Abort/location create/recover/
  item create/renew check lease before cached result. Metadata-only entity writer
  checks for update/death/cleanup/session/quest/requester/trade; stale source
  denied after handoff even with live source lease. Legal retry excludes old
  CAS/alive/session state. Claim replay validates saved grant fence; expired or
  replaced grants require new CommandID. Local full 205 PASS, including broad
  legal/expiry/same-owner-new-fence/new-owner/handoff/real-HTTP proofs.
  Task43 F06 partial only; native adoption/generations/cross-host fencing open.
  Actions pending after push; no native runtime or replication changes.

- 69213eabf backend 37420503094 SUCCESS Windows+Linux (205).
- Coordination before native edit: Codex adds a fair non-destructive next-record
  selector for NPC transit, with declaration/Lua binding in netcoop.h and
  level_script.cpp only. Also reject incoming persistent IDs already present
  in target ALife before spawn. Areas transit queue/Lua/actual fixtures; no
  replication/interest/ALife initializer/runtime changes, default remains off.

- NPC arrival follow-up prepared: new next(level,after_id) Lua binding rotates
  held records without deleting/ACKing them, exposes corrupt ID with empty
  payload and preserves legacy take. Actual Lua fixture PASS for held-head
  progress and new-nonce target persistent-ID collision refusal before spawn.
  Local mapping checked against ALife, not a global registry/fencing proof.
  Windows actual queue fixture extended (syntax only locally); native CI next.
  Full file-name enumeration still linear; no runtime install/launch/default
  NPC transit changes or H09/H10 whole-stage closure. New binding fallback
  preserves older installed runtime compatibility until its upgrade.

- 24b36893b Foundation37420952363 SUCCESS GCC/MSVC; DX11 37420952355
  checks/Windows actual fixtures SUCCESS, compiling. No native push to cancel it.
- Backend corpse cleanup now64 rows/4 MiB admission per atomic batch, durable
  continuation with actor/fence/version; final corpse_removed only when empty.
  Pickup, quest pin/stale owner checked each batch. Removed corpse inventory
  cannot accept new items; repeated removal no-op. Schema4 ordered holder index,
  atomic v1-v4 migrations/snapshot wire1 preserved. Full local216 PASS including
  actual migration process crash, query plan, partial progression/restart and
  queue/journal/oversize faults. Backend Actions pending after push.
  Native body removal must await complete; retention/engine adoption remain open.
- Temporary test folder tmpmcn9mpdo cleanup blocked by automatic review; no
  detailed reason or bypass. Unclosed probe corrected; successful216 run unaffected.

- 6682357ba /37421890399 backend SUCCESS Windows+Linux(216).
  24b36893b full DX11/37420952355 SUCCESS; Foundation37420952363 SUCCESS.
  Matching client/server/overlay artifact available. No runtime install/launch.
- Backend readiness now checks due backlog at startup and after every bounded
  worker batch. Remaining overdue events keep normal admission closed; future
  events don't. Safe admin-only /v1/status remains readable in recovery, with
  metadata sample1024+1/first pending/error class/last cycle/processed count;
  no payload/token/checkpoint/exception text. Clock failure yields null observed
  time, durable diagnostics retained. Full local222 PASS incl actual HTTP and
  existing real CLI restart. Actions pending after push; native adoption open.

- 1495b17f0/37423433421 backend SUCCESS Windows+Linux(222).
- Hydration projection now streams encoded rows/envelope admission before
  position/writer changes, default1 MiB and conservative19-digit event reserve.
  No truncated members/starter items. Shared members4 MiB admission, dead-state
  CASE/roster preserved, foreign writer checked before parse. Local full229 PASS
  including mid-route rollback/retry, guarded reads, clone byte boundary, journal
  fault/item ledger preservation and permanent casualties. Actions next.
  E11 partial only; chunked captures/native restore/Reduced/replication still open.
- Native24b package download targets ignored _build/artifacts/24b36893b, no
  runtime installation/launch/overwrite. Prior temp cleanup policy block unchanged.

- bac88d387/37424664770 backend SUCCESS Windows+Linux(229).
- Downloaded native24b artifact verified: built-from commit and2 manifest
  SHA256s match; identical client/server monolithic exe includes new binding;
  transit overlay matches. No separate xrGame.dll; earlier assumption corrected.
  No runtime install/launch or overwrite. Package:_build/artifacts/24b36893b.
- Whole-world ScaleChanged routes now stream into bounded8192-row/8 MiB
  admission before updates; refusal keeps old routes/arrivals/clock/anchor.
  Local full231 PASS with population/guarded-read faults and prior scale tests.
  Actions pending after push; chunked rescale/native authority/4 LOD still open.

- 479914f98/37426282814 backend SUCCESS Windows+Linux(231).
- NPC target arrival now holds mailbox before spawn if any connected player is
  within150m of entrance (inclusive boundary). No receipt/checkpoint/ACK on hold;
  cursor rotation allows other entrances, receipt retries never respawn or wait
  on later player proximity. Actual Lua PASS incl restart, two-player boundary,
  another entrance progress and delayed ACK. DX11 Actions next, no local native
  build/install/launch. Proximity only, not PVS/optics/observed transit animation;
  H10 still open and NPC transit still opt-in pending authoritative adapter.

- Backend location-scoped quest requirement projection: authenticated location
  role/allowlist/current lease,64 metadata rows, frozen-time due consequences,
  existing IDs/current registry location/death/version/writer/quest version.
  Cursor(character,quest,entity)+epoch/revision refuses mixed/stale scans;
  consumer replaces only completed scan, no spawn permission or private state.
  Local full238 PASS incl66-row pagination, migration/frozen writer, death/body
  pin/restart and actual HTTP scope/roles/expiry/query rejection. I03 partial.
  Actions next; native subscriber/delta/busy-world stability/query CPU open.
  21ea79c1c/37427274553 DX11 checks SUCCESS, engine compiling; no runtime action.

- OWNER OVERRIDE 2026-10-06: remove old story/quests and quest-only items; replace
  quest loot in stashes with ordinary consumables. Preserve existing traders.
  Latest amendment: keep a small selected set of former quest NPCs as faction
  mini-traders, with NEW difficult contracts designed from scratch. Old quest
  requirements in43/42 are superseded for legacy story, not justification to
  retain it. Codex edits dedicated sandbox Lua/trade profiles and narrow trade
  hook in server_compat; no replication/interest/runtime install/launch changes.
  General backend quest transaction machinery can support the new contracts;
  old story content/definitions must not be used as new contracts.

- 2026-10-06 13:40 (Claude) — нагрузка «все игроки в одной точке» (Болото, боты =
  настоящие сетевые клиенты-игроки, NPC как во фриплее): 32 — кадр 15 мс, 4 МБ/с;
  64 — 37 мс, 10,7 МБ/с, 2 таймаута рукопожатия; 128 — обвал: все новые персонажи
  спавнились в одну точку (капсулы друг в друге → кадр 0,5–5 с → SteamNet 5003).
  Исправлено: `netcoop_free_spawn_spot` (game_sv_single.cpp) — ближайшая свободная
  точка по кольцам 1,5 м на AI-сетке. Перепроверка 128 после сборки.
  Владелец: игроков НЕ замедлять (никаких 15/10 Гц для дальних игроков) — сделано:
  игроки до 300 м каждый тик, overload/бюджет их не трогают. Неизменённое состояние
  не-игроков не пересылается (пульс 0,5 с). Сервер не рендерит D3D при активном окне.
  Новое: `run-cluster-selftest.ps1 -Spread` (по -Bots на каждую карту, 512 = 4×128 —
  только на целевом ПК 20–30 ядер), `-netcoop_bots_first`, боты повторяют неудачный
  вход до 3 раз; `run-world-crash-test.ps1` + `-netcoop_world_crash=<point>`
  (before_alife/after_alife/pointer_temp/after_pointer) и `-netcoop_world_save_period`.
  Отряды одиночек (`netcoop_squads.script`, вкладка F6 «Отряд»), ЗЗ гп для лидера/
  замов/допущенных. Профайлер памяти `-mem_profile[=bytes]` + `tools/symaddr.py`
  (PDB назван в exe LostZoneDX11.pdb — инструмент делает hardlink).
  ВНИМАНИЕ: «shared strings: memory» в логе — это ЭКОНОМИЯ от общих строк, не расход.
  До загрузки уровня процесс уже 1040 МБ (на старте DLL 226 МБ) — ищем профайлером.

- 2026-10-06 15:30 (Claude) — память сервера: GAMMA ставила звуковой кэш 512 МБ и на
  выделенном сервере → 8 МБ (SoundRender_Core.cpp). Болота: private 2,4 → 1,96 ГБ,
  куча 1,53 → 1,02 ГБ. 128 игроков в одной точке: стеки [hitch]/[hitch-mt] показали
  запись аренд всех игроков в одном кадре (теперь 4 за 250 мс), UI-подсказку костра GAMMA
  на сервере (start_tutorial — no-op на dedicated), Lua-чтения общего хранилища на каждого
  игрока (теперь порциями), перерисовку GDI-консоли (не рисуется свёрнутой, реже),
  и залп «весь мир каждому входящему» → очередь входа: 4 одновременно (xrServer_CL_connect.cpp).
  Краш-тест сохранений мира PASS на реальном сервере (G13).

- 2026-10-06 18:30 (Claude) — профиль главного потока сервера (`-netcoop_sample_profile`,
  `tools/profile-report.py <exe> <log>`), 64 игрока у базы ЧН: ИИ сталкеров 35% (лучи
  зрения 8%, Lua-планировщики GAMMA 8%, память 6%), Lua всего 29%, репликация ~5%, сон ~10%.
  Сделано: бюджет лучей зрения NPC на dedicated (≤30 м — каждый раз, дальше 12 за
  обновление по кругу). Пространственный индекс репликации ускорен (сортированный массив
  ячеек), но по умолчанию выключен: на толпе не быстрее полного перебора; включать
  `-netcoop_chunk_index` для рассредоточенных игроков. Гибернация пустых серверов
  проверена (1424 → 151 МБ), WARP-устройство на сервере проверено. 64 игрока: кадр
  21–26 мс, 0 отказов; 128: 126 играют (на 4-поточном ПК вместе с ботами).

- 2026-10-06 23:30 (Claude) — сервер без игроков: найдено и исправлено, что (1) Lua-мир
  стартовал только с первым игроком; (2) level_weathers.valid_levels пустой на сервере →
  ни выбросов, ни пси-штормов; (3) часы от 0 года во float (шаг ~1,1 ч) ломали расписание
  выброса/погоду — теперь от 2012; (4) укрытия GAMMA не загружались → в конце выброса гибли
  все онлайн-NPC вне surge-смартов; (5) safe_release_manager не работал (actor_on_reinit);
  (6) полная блокировка респавна оставляла карты без мутантов → теперь каждая секция смарта
  заполняется до фриплейного лимита один раз, погибшие не восполняются. Трупы: удаляются с
  лутом при рестарте и после 40 мин без игрока в 100 м (netcoop_corpses), engine-detach
  лута трупа только с -netcoop_corpse_drop. Личный ПДА (PAW без ALife, метки в хранилище
  "pda"), карта клиента показывает метки по объектам/позициям, метки заданий следуют за
  целью (taskpos). Живые тесты: run-world-persistence-test, run-emission-restart-test (PASS),
  run-emission-cover-test, run-world-day-test (сутки мира без игроков).

- 2026-10-07 02:00 (Claude) — ночь, сервер без игроков и нагрузка:
  * Онлайн-смарты на dedicated не обновлялись (биндер не работает) → респаун и логика
    смартов на своей карте не шли, мутантов 0. Теперь `update_online_smarts` раз в 1 с;
    респаун только смартов своей карты и не рядом с игроком. Болота без игроков: 41 NPC,
    31→45 мутантов. Это вскрыло Lua-панику: звуковые темы GAMMA (`sound_theme.script:217`)
    берут `db.actor` → `xr_sound.set_sound_play/play_sound_looped` на сервере без игрока
    идут с якорным актором (id 0), ошибка — в лог, не падение.
  * Профиль 16 ботов: 9% главного потока — `cluster_lease_write` (fsync + WRITE_THROUGH
    на каждый пульс аренды), 7% — таймер GDI-консоли (перерисовка каждые 100 мс в обход
    лимита). Пульсы аренды/часов/статуса теперь без сброса на диск (захват сессии —
    по-прежнему с ним); таймер консоли через `RefreshIfChanged`. Кадр 20–22 → 12 мс
    (вторая правка — в сборке 68274a8e9).
  * Новое: `-netcoop_ai_far/-netcoop_ai_combat/-netcoop_ai_path` (E04), PREWARM
    `-netcoop_prewarm=<с>` (E09, точка «через 4 с» для движущихся игроков в
    `netcoop_nearest_actor_distance`), боевой пин `-netcoop_combat_pin=<м>` (E18:
    NPC в бою с игроком не уходит в офлайн), перцентили кадра `[frames] p50/p95/p99` (M01).
  * Отладочный канал по карте: `netcoop_debug_<map>.lua` (несколько серверов в одном
    runtime съедали общий файл первым).
  * Живые тесты PASS: `run-emission-cluster-test.ps1` (J10: два сервера, рестарт Кордона
    посреди выброса), `run-world-living-test.ps1` (L35: 77/77 живых с теми же id/отрядами/
    235 предметами; болты не сравниваются — движок выдаёт новый при выходе в онлайн),
    `run-world-day-test.ps1` теперь проверяет инварианты (сироты, потерянные члены
    отрядов, дубли story id) и ловит Lua-панику.

- 2026-10-07 04:00 (Claude) — защита A11 и память:
  * `server_remote_event_allowed`: от удалённого клиента отклоняются GE_HIT/
    GE_HIT_STATISTIC/GE_DIE/GE_ASSIGN_KILLER/GE_GAME_EVENT/GE_TELEPORT_OBJECT/
    GE_CHANGE_POS/GE_CHANGE_VISUAL/GE_TRADER_FLAGS/GE_FREEZE_OBJECT/ограничители;
    GE_TRANSFER_AMMO — только если получатель принадлежит отправителю (иначе
    R_ASSERT ронял сервер); GE_DESTROY/GE_INSTALL_UPGRADE/GE_ADDON_* — только вещи
    своего Actor; GE_INFO_TRANSFER — только себе. Честный клиент их не шлёт (пули
    клиента визуальные, урон считает сервер). Если владелец увидит в логе сервера
    `rejected event <тип>` при обычной игре — это легальный путь, который надо
    разрешить точечно.
  * Бот-читер `-netcoop_bots_cheat=<id>` + `run-cheat-test.ps1`: PASS на новом сервере,
    старый (2d878e589) упал на `c_from == c_parent`.
  * Профиль памяти Кордона (`-mem_profile`, блоки ≥4 КБ): конфиги ~180 МБ, CDB ~177 МБ,
    вершины скелетных моделей (_Load_hw) ~50 МБ, анимации ~26 МБ; текстуры 0.
    Кэш DLTX (~80 МБ) сбрасывается через 60 с после уровня на dedicated.
  * Нагрузка на 4-поточном ПК: 64 бота вытесняют сервер с CPU; `-BotsBelowNormal`
    для честного кадра сервера. Плохая сеть: `-BotArgs "-netcoop_fake_loss=5 -netcoop_fake_lag=120"`.
  * Пауза кадра: `Sleep(psNET_DedicatedSleep)` жила в `IGame_Level::OnRender`, которую
    dedicated больше не вызывает (рендер отключён 2026-10-06) → пустой сервер 98% ядра.
    Теперь в `CRenderDevice::on_idle`: кадр короче `-netcoop_frame_ms` (5) досыпает
    остаток, длинный — не спит. Пустые Болота: 30% ядра, p50 6 мс. Во время паузы
    вторичный поток делает шаги Lua GC (`psLua_ParallelGC`, пока `isRendering`).
  * Идея на будущее: скрытый якорный актор (id 0) держит онлайн 450 м вокруг стартовой
    точки даже без игроков (`netcoop_nearest_actor_distance` берёт `graph().actor()`):
    исключить его, когда на карте есть игроки, или совсем — экономия CPU/памяти, но
    проверить мир без игроков заново (выбросы, трупы, респаун).

- 2026-10-07 07:00 (Claude) — итог ночи, установлена 69cf233a1 (gamma-runtime и
  LostZone-3D-Hideout):
  * Суточный прогон PASS: 150 мин, 3 выброса, трупы по правилу 40 мин, инварианты 0,
    ошибок 0, память +31 МБ (Болота ~1,9 ГБ private; после сброса кэша DLTX на 60–90 МБ
    меньше прошлых прогонов).
  * Процессы ботов теперь с паузой кадра 10 мс (~20% ядра каждый). 64 бота: 64/64
    играют, 0 отказов, но сервер 157% ядра, кадр p50 ~110 мс. Профиль: CSheduler 63%,
    CAI_Stalker 33% (Lua биндеры 18%, CActionPlanner 12%), Feel::Vision::o_trace 12%
    (ray_query: каждый NPC трассирует всех игроков ближе 30 м — бюджет лучей нужен и
    внутри 30 м), CBaseMonster 8%. Следующий шаг: бюджет зрения в толпе и частота
    биндеров GAMMA для NPC, которые не в бою.

- 2026-10-07 утро (Claude): владелец — «не делай NPC тупыми ради оптимизации». Бюджет
  лучей зрения больше не касается игроков (O_ACTOR/S_ACTOR трассируются всегда).
  Физпредметы (`CPhysicObject`: двери, бочки, ящики) не реплицировались вовсе
  (`net_Export` пишет 0 в single, а `server_physics_update` брал только предметы и
  трупы) → теперь предмет, сдвинувшийся на сервере (после 30 с оседания уровня),
  отправляется как предметы, спящий — раз в 60 с. `run-prop-test.ps1` PASS, бот
  `-netcoop_bots_watch=<id>`. Сборка c38376323 установлена; 16 ботов: p50 8–9 мс.

- 2026-10-07 (Codex) — owner requests continuing lossless optimizations and
  adapting IX-Ray scheduler. Coordination before edit: xrEngine/xrSheduler*,
  ISheduled initialization, actual scheduler CI fixture/workflows and docs.
  No replication/interest/runtime install/launch changes. Pinned IX-Ray stable
  612b165c97d5e6a50ac0a6d1384ac8c95a63dda5 and develop
  c55dacab6165c0f28fd09479043fcd89a9625357: same queue/interval/budget algorithm
  already present; no claimed magic threading/crowd speedup from replacing it.
  Adapt profiling/tolerant unregister and improve registration/lifetime safety,
  retaining existing update intervals and full player/NPC work. Live64+ result
  required before marking performance acceptance complete. Existing untracked
  backend/tests/test_transfer_stress.py is preserved and not part of this edit.

- 2026-10-07 (Codex) — separate backend handoff validation: finish the previously
  untracked test_transfer_stress.py in its own commit; local Python run PASS
  (1000 player/group commits, 250 aborts, transactional fault injection and
  eight actual process exits before/after each phase). Existing backend workflow
  discovers it on Linux/Windows. See 51_TRANSFER_STRESS.md; H12 stays partial
  until native source/target crash and hidden-spawn acceptance. No runtime edit.

- 2026-10-07 (Codex) — IX-Ray scheduler fixtures PASS: World Foundation
  37578376041, GCC+ASan/UBSan and MSVC, release/DEBUG, exact 32825 callback trace
  against pinned IX-Ray, register-pair/lifetime/address-reuse tests. Native code
  last changed at 9cbec96e8; DX11 run 37578375978 (87cbb2133) is building.
  World Backend 37578376035 PASS 240 tests on both OS, including 1000 handoffs
  and eight process crashes. Do not label the 64-player frame acceptance done.
  Current backend cleanup policy corrected to DESTROYED leftover corpse loot
  per latest owner rule; independent ground/player items preserved. 241 Python
  tests local PASS; see 52_CORPSE_LOOT_POLICY.md, backend CI pending.

- 2026-10-07 (Codex) — final scheduler native source c64e88fbc: RT cancellation
  now marks dirty and compacts once after a batch; unchanged frames skip this
  scan. Actual fixture adds 2048 RT removals. World Foundation 37579014305 PASS
  on both OS/release/DEBUG, including exact IX-Ray trace and sanitizer checks.
  DX11 37579014309 is building; avoid native pushes until its result is known.
  Corpse backend policy 055aa98e7: World Backend 37578839647 PASS 241 tests on
  both OS. Runtime installation/live64 remains separate; original audit counts
  stay unchanged. Doc49 marks its historical 1–5 Hz Reduced AI proposal as
  superseded by owner's no-AI-degradation instruction.

- 2026-10-07 (Codex) — completed source/CI/package scheduler iteration. Latest
  native source 3a95c0dce includes xrCore/profiler.h explicitly (the full build,
  rather than the previous PCH stub, exposed that missing dependency). Fixture
  now imports the real profiler header. World Foundation 37580073705 PASS all
  Linux/Windows release/DEBUG + sanitizers; DX11 37580073704 SUCCESS including
  package/upload. Artifact 11464314210 downloaded to
  _build/gha/scheduler-3a95c0dce; built-from and both exe hashes validated;
  IX-Ray notice matches source. Exe SHA256
  D41B3D55DE56BB62F3DBF6F30F46A4976A04985F88EE7251E43C65E9D6A8EEC5.
  No runtime installation or native launch: keep live64 p50/p95/AI population
  acceptance open. Current backend 241 tests PASS remains 37578839647.
  Next lossless work: profile pure reads first; actor binding functor/depth are
  already cached, and CPropertyStorage's public mutable vector prevents naive
  lookup caching. No added live checkmarks in the 188-point audit.

- 2026-10-07 (Codex) — coordination before direct-ticket hot-loop edit: xrEngine/xrSheduler*, new scheduler ticket helper, actual scheduler CI fixture/project/workflow and documentation. Preserve callback frequency/order/intervals/budget and NPC quantity. Owner explicitly requires smooth, responsive NPCs throughout maximum visibility; distant-NPC live acceptance remains mandatory. No replication, runtime installation or native launch edits. Pinned hash-check baseline is native 3a95c0dce.

- 2026-10-07 (Codex) — owner clarification: no visible frozen/jittery NPCs at maximum visibility. Coordination before foreign-region fix: xrServer.cpp AOI cadence and netcoop_replication_index cpp/h + actual predicate fixture. Existing NPC 1/2/4/16 tiers multiplied by overload conflict with this requirement. Protect creature roots (NPCs/mutants/actors and held objects) every tick at all distances, independent of budget/overload; index must include them globally. Also bypass lossy unchanged hash filtering for these live states. No AI callbacks/population reduction, no runtime install/launch. Native DX11 37584887087 will be superseded by the combined build for this owner-requested fix; Foundation 37584887106 already PASS direct tickets.

- 2026-10-07 (Codex) — combined code d54030213: Foundation 37585364939 PASS on Linux/Windows (actual scheduler/reference/lifetime/ticket checks + actual AOI predicate/index full-rate differential). DX11 37585365023 is building. Windows overhead 64RT/128normal benchmark reduction varied 14.4–26.2% between CI runners (1.85–3.40 us per synthetic frame), NOT a gameplay FPS claim. All creatures/actors and their inventory-root states bypass distance/overload/byte-budget/hash suppression; traffic increases, measure it with live64. Bots do not render NPCs; watch flag tracks physics, so maximum-view smoothness requires a real graphical client. Docs53/54 record proof/limits, doc48 adds a historical-snapshot clarification without new live checkmarks. No running game processes observed; no runtime install/launch.

- 2026-10-07 (Codex) — FINAL combined scheduler/creature replication source
  d54030213cfbf950b5103ab0c275423242ed87a1: Foundation 37585364939 PASS both OS;
  DX11 37585365023 SUCCESS checks/full engine/package/upload. Artifact
  11466733728 (189509686 bytes) downloaded to _build/gha/scheduler-d54030213.
  built-from, both exe manifest hashes and IX-Ray notice validated. Exe SHA256
  36BA115085198F7B5BAF08E384AB306B2174FB19CA861EBFF6187498DCD57395.
  No runtime install/launch. Keep real 16/64 load, traffic/send queue, distant
  NPC movement/reactions and graphical client acceptance OPEN. Full-rate applies
  after existing Net_Relevant/handshake/transport eligibility; do not claim a
  delivery or AI/frame-time guarantee from a passing synthetic fixture. Actual
  benchmarks measured scheduler overhead only, not the 110 ms game frame.
  Current repository code/CI/package substeps complete; 188 live audit counts
  unchanged. Next native runtime testing remains the recorded installation lane.

- 2026-10-07 (Codex) — coordination before native runtime acceptance: isolated GHA d54030213 package staged under _build/live/d54030213, separate appdata/selftest and selftest_bots (resolved cleanup targets verified empty/inside that root); main worlds/accounts unchanged. Existing runtime third-party DLLs copied only when absent from the GHA package. Four critical server overlay modules exactly match repository. Isolated copy of existing load harness uses Hidden server/bot windows and 10-second sleeps. Start with 16 bots then 64; graphical max-view acceptance remains separate. No local compilation. Main runtime promotion with backup follows successful native checks.

- 2026-10-07 (Codex) — native d540 isolated acceptance ran: final16/16 and64/64 playing, no fatal/script errors, admission retries1/6. Near-NPC64 stress windows p50~27-37 ms, p95~72-105 ms, receive/dequeue gaps~0.9-1.5s (larger trailing stop windows). No max-view acceptance or main-runtime promotion: these gaps need attribution. Coordination before netcoop_bots.cpp diagnostic edit: atomic single-producer callback gap vs main-thread bot frame gap, preserved base OnMessage forwarding; explicit destructor joins workers before probe destruction. No gameplay cadence/AI/population/network payload changes. Native fixtures and build remain Actions only. Source profile_ai covers CustomMonster Think, not total stalker Lua/action/vision; do not treat it as inclusive AI profile.

- 2026-10-07 (Codex) — coordination BEFORE device.cpp edit: load-bot processes currently pass the normal client render gate and draw their main menu despite the headless test contract. Reuse existing -netcoop_bots detection before rendering and exclude only those processes from Begin/seqRender/Present; retain their OnFrame/network/input and existing10ms frame cadence. Ordinary graphical clients and dedicated simulation behavior unchanged. This is load-driver fidelity/CPU/GPU cleanup, not an AI downsampling optimization or a proved source of observed gaps.

- 2026-10-07 (Codex) — coordination BEFORE Feel_Vision cpp/h foreign-region edit: owner requires unchanged freeplay NPC behavior. Existing dedicated far_budget=12 still skips distant non-actor targets, slowing NPC/mutant perception of each other. Restore actual o_trace from own pre-budget revision 843e5eef060a0e9bca79ddb537f0e10bfc40b7ae, retaining original per-target ray/triangle caches, order and fuzzy updates; remove unused round-robin cursor. Pin historical function and source-equivalence check in CI, then full Actions/native acceptance. Diagnostic build 37593806421 / source9e256b9b2 continues unchanged; do not supersede while compiling. No AI work moved to unsafe parallel Lua.

- 2026-10-07 (Codex) — coordination BEFORE xrServer.cpp pure-read cleanup: full-rate characters/equipment use neither distance cadence nor distance budget, yet compute per-client square roots. Skip only that unused distance evaluation; existing owner_only and transport eligibility remain. Pin actual d540 cadence as fixture reference and compare native eligible decisions across all tested distances/overloads/tick wrap; assert zero full-rate distance calls. Also omit full-rate entries from optional replication index spatial cells/buckets because the global full-rate list already guarantees them on every tick. Current index remains opt-in until native timing proves benefit. No packet order/cadence/state change; do not cancel current Actions build.

- 2026-10-07 (Codex) — diagnostic9e256b9b2: Foundation37593806445 PASS both OS; DX11 37593806421 SUCCESS full engine/package/upload; package artifact11469784291. Prior build completed, so next native vision-restoration/redundant-distance/index edit may now push without cancelling it. Native9e acceptance staged separately; source-equivalence local check PASS, next actual native predicate/index fixture remains Actions-only.

- 2026-10-07 (Codex) — continuation FINAL: native source9e256b9b2 gap diagnostics/headless render gate, then fa5edb5f2 restores exact pre-budget freeplay o_trace and omits unused protected distances/spatial indexing. Foundation37607469611 PASS GCC/MSVC (actual index vs pinned previous predicate; no protected sqrt/spatial candidates); DX1137607469678 SUCCESS full engine/package/upload. Artifact11476356618 (189396278bytes) _build/gha/vision-fa5edb5f2; both exe SHA256794316757B231F71467194E358084588DB93963E0B0225346C412686AE212113, built-from/manifest validated. Native final16/16 (3admissionretries),64/64 (8retries),0terminalfailures/fatal. Near13NPCs64 framep50=57–76ms,p95=161–205ms,max646ms, NOT performance/smoothness acceptance. NPC/mutant population measured48/30 before relocation; no final measurement. New64 driver-dedicated mode/world seed/density differs from old8NPC scene, no A/B claim. Post-test profile scheduler74.3%/stalker45.1%/vision23.9%/binder16.7%/planner10.1% inclusive. Bots callback/main-frame gaps persist; menu omission not sufficient. Doc55 corrects missed caught-PDA errors and failed0-playing shader-default fixture (new private bots missing user.ltx; fixed in repeat); profiler histogram250 means >=250ms. All test processes stopped, debug channel empty, primary exe/world/account data unchanged; package remains isolated, NO runtime promotion. Docs55/56 hold full evidence/limits.188audit live counts unchanged. Next: actual pure-read/cache or safe independent static geometry work, bot transport/frame profiling, graphical max-view acceptance; no AI work throttling/population cuts.

- 2026-10-07 (Codex) — owner steering: easy/quick fixes first, then medium, then complex. BEFORE installer/harness foreign-region edits: server PDA discover_spots nil-actor guard after existing timer reset (same behavior with actor); isolated Lua/PS regression; load-harness BotArgs variable collision and strict zero-playing/terminal-failure gate. Preserve actual admission retries as nonterminal, distinguish capped caught-event logs, count unique bots rather than repeated Actor/you lines. Complex vision/Lua hot-loop work queued, no code edited there this turn.

- 2026-10-07 (Codex) — source765a708b0 quick fixes pushed. Foundation37636526831 SUCCESS Linux/MSVC including actual PS driver and patched GAMMA Lua5.1 fixture. DX1137636526929 checks/new PS-Lua step passed, full build pending. Native focused PDA verification used existing GHA fa5edb5f2 exe in fresh _build/live/quick-pda-765a708b0, private scripts/appdata; actual ScanForSpots callback captured by real queue, db.actor=nil, ten successful timer-reset cycles and another probe timer, zero time-event/fatal/debug errors, bootstrap save succeeded. Existing itms_manager.save_state nil-actor handler error1 remains; NO full-clean native acceptance. Strict evaluator applied to archived fa16/fa64 reports correctly counted16/64 distinct bots, final16/64 playing, retries3/8 and rejected both for21 caught Lua records. Probe stopped and debug channel empty. BEFORE focused primary installation: back up and apply ONLY server pda.script in gamma-runtime and LostZone-3D-Hideout; no full overlay installation, no exe/world/account changes. Next easy item is itms_manager personal inventory save with absent local actor; complex64/frame/smoothness remains queued.

- 2026-10-07 (Codex) — autonomous continuation, BEFORE foreign-region installer/harness changes: focused itms_manager.save_state guard for absent db.actor only (do not invent a player's bolt data in world state); actual GAMMA Lua5.1 fixture for unchanged actor inventory count/slot and no-actor state preservation. Add pre-shutdown process liveness check so old healthy bot reports cannot hide an exited process; exercise actual cleanup guards. Keep existing DX1137636526929 running to completion before next code push. No hard AI/ray/scheduler changes; native probes private and GHA-built only.

- 2026-10-07 (Codex) — source81ae903c1 Foundation37639441808 SUCCESS (public Actions fallback; local api.github.com connections currently reset), DX1137639441890 building. Native quick-item-save4/4 PASS with0Lua/save/fatal/shader/admission errors. Private two-map quick-transitions (30-second save test flag, normal default still300s) had20leaves/19arrivals,0Lua/save/fatal/lease errors, but1terminalfailed bot; strict gate FAIL. Three private bots seeded with2bandages/1bread late in run for inventory checks, fourth was already failed; do not claim4/4inventory coverage. BEFORE netcoop_bots.cpp medium driver fix: target connection timed out, driver retries went back to initial s_address, then treated valid auth redirect as failure. Real graphical auth redirect already has its own handling. Preserve per-bot last address across retries and queue valid auth redirects outside message-lock disconnect; shared strict target parser and actual native method/loop fixture. This is test-driver correctness, no server/player protocol or AI change. Native compile remains Actions only, current81ae build must finish before next code push.

- 2026-10-07 18:15MSK (Codex) — continuation status: source81ae903c17a6528c49a89bc78aa9833635046d22 Foundation37639441808 and DX1137639441890 SUCCESS (full engine/package/upload; public Actions verified). Local API still resets so neither new package is downloaded/validated. Focused item-save guard installed in both main server script copies with originals under _build/live/quick-item-save/primary-backup, inverse byte equality checked; installedSHA364F6BE9060DF649ACD686FF0C833ECBADEF329C0E0F0D5762A4ADBC9737BF. All four primary exes remain oldFE829..., no game processes, debug channel empty. Local commit8ef6a25f5 (bot retry/redirect actual native fixture + stronger save error gate) NOT PUSHED: three GitHub remote Internal Server Error rejections, including HTTP1.1; ls-remote still81ae903c1. GitHub public status says operational, so do not claim a confirmed global outage. No local C++ compilation or new native PASS. Next: retry normal push when remote accepts; Foundation/DX11 validation; download/verify built-from+hashes; fixed two-map probe with item seeding BEFORE first handoff, not late/frozen-actor injection. Docs57/58 and private result/analysis files preserve evidence. Existing64/max-view acceptance and cross-hardware crc32 compatibility remain open; CRC core not edited.

- 2026-10-07 (Codex) — publication recovered: both8ef6a25f5 and docs c6525f885a7c4c5c562b65e543a1f76610686be8 pushed; remote ref verified. Foundation37642993485 SUCCESS GCC+sanitizers/MSVC actual start/auth/target/retry-loop fixture; DX1137642993484 checks/new native fixtures passed, engine build running. API access workaround is per-request only: local DNS gives api.github.com188.68.214.139 while Google HTTPS DNS gives140.82.121.5; curl --resolve keeps api.github.com TLS/SNI/certificate verification, no hosts/DNS/proxy/global setting edits. Private fetch-artifact.py reads gh token into memory only, auth to verified GitHub endpoint, drops header on signed blob request, checks ZIP digest/paths/built-from/exe hashes. Source81ae artifact11491544969 downloaded/validated _build/gha/item-save-81ae903c1, ZIPf13eda...; both exeD132C8EAB7C0EB747D0BC958B94118B5B4FB7E920F0733160051BA1948E5858C. Next live probe staged under _build/live/roundtrip-c6525f885 (no exe yet): private driver differs only by arm-early-seed call before starting bots; same production result helper/launch logic. Both map servers must belong to private root, debug channel empty, then seed2bandages/1bread once per bot before its first20s handoff. Do not promote primary exes; continue native roundtrip/UID/restart acceptance after c652 package validation.

- 2026-10-07 (Codex) — FINAL quick/medium continuation: sourcec6525f885 Foundation37642993485 and DX1137642993484 SUCCESS. Artifact11494387347 ZIP06731640... (190063170bytes), built-from/manifest validated; both exe7E616CA2282D5FCAF162B9C140FE8A0B6F03EC645CFC46DEC242BC1F7BE677A9. Native two-map/four-bot early-inventory roundtrip PASS: final4/4,24departures/22arrivals,2recovered timeouts,0terminal/Lua/fatal/shader/save/refusal/lease errors. All4 seeded before first departure; original basic items+PDA and nonzero UIDs retained in14/15/11/10NCH7 snapshots. Restart SAME worlds/characters with distinct logs and NO deletion/reseeding; initial combined command blocked by auto-review, safer file-preserving alternative accepted. Restart driver waits for actual clock after restored-world announcement. Post-restart final4/4,12departures/12arrivals,4authredirects followed,0retries/errors;8snapshots each and all4 inventories exactly match pre-restart section/UID multiset. Both maps visited by every bot in each phase. Saved-world loading and repeated world commits confirmed. Test-only30s save period; normal300s unchanged. Doc58/private acceptance.json contain details and scope limits. All processes stopped, debug empty; primary worlds/accounts/exes untouched except the focused server pda/itms guards installed with backups (doc57). NO primary exe promotion, NO graphical64/max-view acceptance or188counter changes. Next work follows owner easy→medium→complex ordering; remaining broader transition/state/512 cases stay open, CRC hardware-compatibility requires migration-aware investigation, hard NPC/vision/Lua performance stays queued.

- 2026-10-08 (Codex) — coordination BEFORE DestroyablePhysicsObject/netcoop.cpp checkpoint edit: calibrated stock wood-box native control qualifies loss of partial damage across SAME-world restart (fire immunity0.5/root scale1; 0.4+0.7 destroys without restart, both split orders survive restart). Preserve health as a bounded versioned owned suffix in existing CSE m_ini_string, exact original INI prefix and client_data/binder untouched; IEEE32 bits, malformed/overflow rejects checkpoint/spawn. No CSE protocol change, no uninitialized binder serialization, freeplay unchanged. Native method/codec/traversal CI + isolated GHA package acceptance required before promotion. Primary runtime/world/accounts remain untouched; L30 stays partial.

- 2026-10-08 (Codex) — FINAL scoped CDestroyablePhysicsObject health continuation: sourcea4b1931db first Foundation37732630257 Linux PASS / Windows fixture-only shadowed mock count FAIL; DX1137732630255 stopped at same fixture before engine. Renamed mock simulated_count only (assertions/engine unchanged), finalsource4b74ba7f2b958ec1d4fad26ec68140bc97154816 Foundation37732900872 PASS GCC+ASan/UBSan/MSVC; DX1137732900805 SUCCESS engine/package/upload. Artifact11531705521 ZIP9db5c78b51039219da3522a521344e6c0fd06d4ffe23c40113d6607c99c3251f; bothexeE4EDE44A70CAEEB43DC9CA00968ECDAE0CF838BDF7D44F4E35341E2EC15FE7A0, built-from/archive/manifest verified. Initial native strike control did not break (uncalibrated, unqualified); calibrated stock wood crate baseline qualifies loss in BOTH split orders:0.4+0.7 same session deletes15781, split by restart15778/15779 survive. Fixed SAME world _build/live/destroyable-health-fixed-4b74ba7f2 PASS: exactoriginalINI/name/class/shell retained, health bits3f19999a/3e99999a restored, same follow-up hits delete both, committed15781 stays absent. Final1/1bothphases,0terminal/Lua/fatal/shader/save,1recovered admission;3old GAMMA loadout records. First fixed launch omitted five base GAMMA DLLs, no journal/world; private executable PID checked/stopped, missing DLLs added from working test root without overwriting package files/exes, unqualified attempt/provenance retained. PreviousGHA c871 loads SAMEfixed world with new footer on actual15780 and committed15781 absent;1/1,0retries/errors,1oldloadout record, format readability only (oldhealthbug remains). Phase2 has no explicit post-hit checkpoint; do not use those later deaths as a rollback oracle. Six sealed journals + native-summary.json/doc66. All88primary exe/config/account/character/world fingerprints unchanged, fourprimaryexeFE829..., no rollout, allprocessesstopped/debugempty. L30 remains partial,188counts22/37/70/59 unchanged. Natural fracture/velocities/graphicalRPC/offlinechunk hydration and64/max-view/512 remain open. Next work should follow owner easy→medium→hard ordering; investigate observed GAMMA loadout configuration or broader integration before hard AI work, without population/cadence reductions.

- 2026-10-08 (Codex) — expanded qualified native L30 acceptance (doc67), source/package4b74 unchanged: retained fresh selftest_destructibles_correlated world,154initial physical objects; all3observed damageable model types (glass15504/wood15778/metal15791) retain exact0.6health and originalINI/name/class/shell after first restart; same0.7hits destroy, explicit checkpoint plus second restart keeps roots absent.151untouched objects retain INTACT/identity;8naturally separated bottle parts preserve IDs/visual/class/source/health/pose, max2.3mm/rotation0.00864. Three phases strict1/1,0terminal/Lua/fatal/shader/save/capture;1recovered admission,7existing GAMMA loadout diagnostics. Previous full trial unqualified due old log-length response correlation; own pending command preserved/verified/cleared, world/logs retained. New driver exact GUID replies and explicit save oracles; full-acceptance.json/common-results.json sealed. L30 accepted for original INTACT/DAMAGED/DESTROYED requirement;188counts now23/37/69/59. Velocities, other maps/models, chunks/graphicalRPC/64/512 remain separate. All88primary fingerprints still unchanged, no rollout. Ordinary graphical startup continuation in private graphic root is not accepted: first long-path graphics invalid_parameter fatal, short-path repeat no actor-ready; quoted CLI start rejected, private menu/trace attempts retained. Current ordinary graphical integration still under diagnosis; no owner login/first3Dpresented claim.

- 2026-10-08 (Codex) — coordination BEFORE Level_start.cpp foreign-region fix: ordinary GHA4b graphical client connects but synthetic login nbot_960 is unknown (actual bot account nbot_961). Its map nevertheless loads/captures input, then net_start6 generic failed-start path deletes g_pGameLevel without releasing it. Sealed mdmp0xc0000005/reading0x30, PDB address14009dac3=CInput::iCapture:655; readonly process query proves valid pInput/dummy but freed prior receiver vtable0x20 before new CMainMenu capture. Not null-pInput initialization. Release input on common failed-start path before any deletion; keep existing errors/checksum/full net_Stop behavior. Actual native method fixture in GHA, rejected-login restart regression and real graphical entry required. Primary unchanged; no blind input pointer validation, no swallowing fatal/auth errors, no role/security bypass. Update private graphical credentials/character to actual synthetic account only; keep original failure dump/logs.
- 2026-10-08 (Codex) — coordination BEFORE PS native-result gate edit: actual graphical UnhandledFilter writes a plain line `at address 0x...` with no FATAL ERROR/Expression token. Existing shared result evaluator could therefore accept a prior healthy bot report while a still-live crash-dialog process has failed. Match only the anchored actual unhandled-exception address line; add negative control for ordinary hitch/profile address lines and native-error regression to actual PS fixture. No engine/network/gameplay edit. Native a428 full DX11 build currently running; do not push source/workflow changes until it finishes.
- 2026-10-08 (Codex) — L30 ordinary peer continuation PASS (doc67): same retained world/GHA4b, actual rendering clients/actors20123 and20239, native first-window-presented markers. Intact15505/shell/3f800000 -> server0.4hit+explicitSAVE -> SAME restart client15505/shell/3f19999a -> server0.7hit -> clientOBS absent+explicitSAVE. GUID replies, actual device frames8444/12113 at944x501, no screenshot or human weapon RPC claim. Previous known-login attempt entered but private Lua OBS had invalid backslash literal; no hit/save, retained. Final observe syntax checked first. Four pre-stop journals sealed in graphic-peer-acceptance.json:0fatal/Lua/caught,2MCM20s script-hang diagnostics and4old loadout records; do not call entire startup clean. All processes stopped/debugempty/all88primary fingerprints unchanged. Native failed-input source4cea with finalfixturea428: Foundation37750844941 PASS both OS; DX1137750844864 passed checks/native fixtures and compiling fullengine. First fixture undeclaredIInputReceiver and then existing iRelease vector-size MSVCwarning failed before fullengine; alias + local legacywarning suppression only, engine/assertions unchanged. No source push while fullengine runs. Private input-recovery-a42873172 stage/driver ready WITHOUT binaries: requires validated successful sourcepackage; unknownnbot960 rejected -> live menu after failure -> validnbot961 native login -> actorready in SAME ordinary client. Reads/writes retained private correlated world only, no owner credentials copied. Native recovery still OPEN.
- 2026-10-08 (Codex) — coordination BEFORE UIDialogHolder cpp native iteration edit: a428 actual rejected-login return now PASS; attempt1 private retry mailbox missed because frontend hides main_menu (own pending nonce preserved/cleared). Attempt2 hooks menu+login original Update; rejected return has7live callbacks, then retry closes native menu during dialog Update. Exact new a428 minidump0xc0000005/address14032c89c=PDB CDialogHolder::OnFrame UIDialogHolder.cpp:256: CleanInternals clears render vector from CMainMenu::Activate(false), invalidating current iterator. Production asynchronous EnterWorld also calls main_menu off during Update. Use index loop rechecking current size without retained element reference; preserve unchanged-dialog callback order/count. CleanInternals also clears pending new dialogs to avoid resurrecting them after close. Actual OnFrame/CleanInternals fixtures on GHA and repeat SAME native unknown->menu->valid-client test; no gameplay/AI/transport changes. Native593c build still running; no source push until complete. Existing rejected recovery PASS does NOT close same-process retry, which failed and is retained. Primary untouched.
- 2026-10-08 (Codex) — coordination BEFORE xrCore do_exit/shared PS gate edit: actual second GHA4b dedicated server competing for a fresh private world remains alive without admission or an error reason in its journal; do_exit is one relevant quiet path (FlushLog then MessageBox, without logging its reason), not yet a qualified diagnosis of this process. Native lock rejection cannot currently be qualified from journals; do not invent PASS from an idle process. Log a constant-prefix message before FlushLog in both existing do_exit implementations, preserve dialog/termination behavior and add actual-method native fixture plus anchored PS gate controls. Retain first unqualified authority probe; repeat interrupted startup/identity/exclusivity/reacquisition with a validated new GHA package. Source e609 full DX11 still running: no source push until completed. Primary unchanged.
- 2026-10-08 (Codex) — completed native continuation: e609 Foundation37756749563/DX1137756749573 SUCCESS, artifact11541183178 ZIP93e019ca... both exe96FB0C81...; ordinary rejected960 after map load -> live menu/form -> GUID native961 retry -> Actor20123 in SAME PID10380+30seconds PASS. qualified-acceptance.json seals pre-stop logs/provenance. Input-release and dialog-vector lifetime fixes accepted for this path; primary NOT promoted.14missing SSFX sounds/normal HUD255/MCM diagnostics remain; doc67 zero-Lua wording corrected, exact persistence evidence unchanged. B03 native fresh private identity4b PASS: exact first bytes sealed before interrupted start, same WorldID13564581398834934011/seed14696362713997730183, epochs1/2/3 and two ready boots, five journals/parser (doc70). Old combined4b contender lacked refusal reason, retained UNQUALIFIED.171473a9940abbfe3e15564bbb2dbb7e63ee5c6c Foundation37759512127/DX1137759512199 SUCCESS, artifact11541814586 ZIPd2018662... both exe2136C663...; actual logged-exit fixture and PS gate PASS. Fresh native171 combined B04 PASS: ready owner, actual contender explicitly locked, no acquired/ready and identity SHA unchanged; owner stays ready, stop/reacquire epoch3+30seconds, six sealed journals/actual records/FNV (doc71). Expected contender exit separate; LOCAL-only, no distributed fencing. Counters25/35/69/59,163 unclosed. ALL own processes stopped, shared debug empty, all88 primary fingerprints unchanged. No pending CI. Read-only asset index finds matching14 SSFX OGG in local165KB mod archive; not installed, profile not changed. Native INI qualifies stale USP/ammo loadout mappings; not patched. HUD255 is normal inactive sentinel; future scoped diagnostic correction must preserve callbacks. Updated complete Claude prompt doc69 per owner request near limits; last snapshot5h77/week81 used, no reset credit spent.
- 2026-10-08 (Codex) — final nearby core acceptance B01 PASS doc72: same validated GHA171 private dedicated server/retained authority-test world, native level.set_time_factor/game.get_game_time, positive6/12/3/1/6. Immediate calendar deltas0, five observed mono/game intervals match rate (max36ms discrepancy); native dates above32bit progress, factor6 restored. Existing actual WorldClock/ALife portable/overflow/monotonic/restore fixtures GCC+sanitizers/MSVC PASS. clock-acceptance.json/sealed pre-stop log retained;0native fatal/SCRIPT ERROR/handler/debug errors, ordinary loadout warnings separate. ALL test processes stopped/shared debug empty/all88primary fingerprints unchanged/no pending CI/no rollout. B01 accepted original LOCAL portable-core requirement only, not distributed ClockSync/location adoption/global barriers. Final counters26/34/69/59,162 unclosed. Owner asked about noisy launches: expected contender lock error distinguished from14missing sound/HUD255/loadout/MCM diagnostics; entire GAMMA startup not claimed clean. Claude prompt doc69 updated with exact results/next simple fixes. Latest quota5h83/week82 used; no reset credit used.
- 2026-10-08 (Codex) — coordination BEFORE player_hud.cpp diagnostic edit: normal inactive script_anim_part is u8(-1)=255, constructor/stop reset both use it. StopScriptAnim wrongly logs it as invalid on unconditional GAMMA startup cleanup. Exclude only255 from warning, preserve all reset/movement/resync callbacks and real invalid3..254 diagnostics. Import actual method into native differential fixture for2048 part/attachment/warning combinations; compile only GHA. This does not fix character blinking or alter animations. Rain sounds native probe still separate: standalone no command consumption retained UNQUALIFIED; first join stopped because server config omitted archive,14server missing diagnostics retained. Second join mounts archive in BOTH private roles, retained world, native acceptance pending; no primary asset/exe/world changes yet.

- 2026-10-08 (Codex) — SSFX rain repair accepted doc73: ordinary GHAe609 client/known961 and matching server restore SAME private correlated world, actual14sound_object durations512–838ms, another15s admitted, sealed logs0missing-sound/native-fatal/SCRIPT ERROR/handler/caught. Original GAMMA archive+CRC/SHA verified, only14 decoded OGG installed under primary sound folder; existing Hideout junction verified. Installer first adds14/repeat0, never replaces custom audio. All88 protected exe/config/account/world fingerprints unchanged; added assets outside88 baseline. No primary EXE/config/overlay rollout, all rain tests stopped/debugempty. b182 HUD CI failed in fixture before engine: renamed diagnostic literal + Windows default decoder. Fixture-only be30 fixes declaration-only rename/latin1, no assertion relaxation; Foundation37773463706 SUCCESS both toolchains, DX1137773463776 fullengine in progress. Native HUD startup acceptance still pending.
- 2026-10-08 (Codex) — coordination BEFORE NPC loadout config repair: native INI confirms9 stale references in5files. Targeted USP_match→USP; Ithaca20x70 3/6→0; DVL_m1 3→0; AK74uM1ISG 6→3/pristine7.62AP. Attachments/weights/chances unchanged; restores previously missing USP to pool, no identical-RNG claim. Byte-preserving installer previews/preflights all rows, exclusive backups+atomic file replacement avoid modifying shared hardlinks. Private loadout-e609 client/server configs only patched; SAME private world/GHAe609 native INI queries and ordinary admission under test. Primary config installation not yet accepted. No NPC population/AI/cadence edit,188counts26/34/69/59 unchanged. Do not push source while be30 fullengine runs.

- 2026-10-08 (Codex) — scoped NPC loadout repair accepted/installed doc74. Final actual GHAe609 native server/client full INI validates9 exact section/key pairs/caliber/pristineAP/randomUSP ammo existence, ordinary known961 Actor26903+20s, SAME retained private world, sealed logs0loadout/missing-sound/fatal/SCRIPT ERROR/handler/caught. Private query path and cross-faction count failures retained, rejected before client launch; final section-qualified ammo assertions unchanged. Original GAMMA script/warnings/population/cadence preserved. Preflight relevant weapon bytes/all rows before primary installation: ONLY5loadoutLTX/9rows per4 active client/server config roots,20files total; exclusive byte backups+atomic replacement, SHA verified/repeat0. All88 protected exe/alias/account/character/world fingerprints unchanged;20LTX outside baseline88, so not all primary configs unchanged. Original GAMMA/fallback gamedata configs untouched, no EXE rollout. All tests stopped/debugempty. be30 Foundation37773463706/DX1137773463776 now SUCCESS; validated package download/private HUD native startup next. Counters26/34/69/59 unchanged.

- 2026-10-08 (Codex) — be30 native HUD diagnostic accepted doc75: Foundation37773463706 both toolchains/2048actual differential cases; DX1137773463776 full SUCCESS. Artifact11549278414 ZIP6f02b5cd... bothEXE4BA75660... validated. SAME retained private world/ordinary known961 Actor20608/PID13152+20s, native first-window frame presented,3stop_hud_motion calls/no invalid-part warning,14PRIMARY-installed rain sounds native lengths with NO extra archive,9targeted INI mappings both roles. Sealed qualified-acceptance.json;0fatal/SCRIPT ERROR/handler/caught/loadout/target-rain-Lua. All processes stopped/debugempty/all88protected fingerprints unchanged; no primary engine promotion. Clarification: earlier broad zero-missing-sound shorthand referred to14target Lua rain exceptions, not all native banks; same probes have38–39other texture and10other sound warnings+MCM. Docs73–75/remaining-resource-warnings.json record scope explicitly. Counters26/34/69/59 unchanged.
- 2026-10-08 (Codex) — next original188 G12 acceptance under way: fresh bootstrap-admission-be30 PRIVATE appdata, no owner worlds/accounts copied or deleted, validated be30 package. Native initial admission refusal, then controlled script_snapshot_matches=false on only THIS private Lua state tests incomplete first checkpoint; restore ORIGINAL checker before native retry/durable pointer, then new bot must play. Three phases201/202/203 with expected preparation refusals; initial fault separate from unexpected errors. Do not mark G12 complete before qualified result/pointer/snapshot hash and sequence checks. Source44730 redundant build37776467719 may run; no native source delta from be30.

- 2026-10-08 (Codex) — G12 ORIGINAL188 accepted doc76: private bootstrap-admission-be30-2/new appdata, validated be30 native package, ONE controller, no owner worlds/accounts copied/deleted. Scoped THIS-server script_snapshot_matches=false exercises native incomplete-checkpoint branch,7failures/no committed pointer; actual nbot202/203 connection-id-specific admission refusals, no Actor/final0playing1failed each. First refusal after initial failed save = pre-COMMIT, not before-first-attempt. Restore ORIGINAL checker; native bootstrap publishes LZW3, independent sizes/FNV64 verify BOTH.scop/.scoc, sealed first files/pointer. Then nbot204 Actor42752+20s/final1playing0failed after server commit log. Six journals/qualified-acceptance.json/native ordering,0unexpected fatal/SCRIPT ERROR/handler/probe/loadout. Expected checker failure/refusal/negativebot terminal separate. Prior root UNQUALIFIED retained: bot only disconnects so original waiter missed server reason; concurrent cleanup interrupted recovery. Final one-controller repeat corrects server correlation/+1bot index, no deleted/reseeded world. All tests stopped/shared debug empty/all88protected fingerprints unchanged; only primary delta14sound+20loadoutLTX docs73/74, no primary EXE promotion. G12 accepted LOCALfirst-commit gate, not disk crash/distributed/every post-admission transaction. Counters NOW27/33/69/59,161 unclosed. Source44730 redundant DX1137776467719 fullSUCCESS; no pending CI. Easy follow-up: inspect remaining38texture/10sound warnings, distinguish UIatlas region keys from actual missing files.

- 2026-10-08 (Codex) — coordination BEFORE UIInventory hidden-stat resource cleanup: current qualified client script16CCF35A... constructs P/N textures for six extra stats (thirst/sleep/br_class/br_mitigation/strike/explosion), absent atlas regions; its updater always hides these and never shows them. Retain all15rows/widgets/text/bars/Show(false), skip ONLY12 unused texture initializations via owned netcoop_inventory_compat helper. Whole-source hash guard,2call-site replacement, original-byte backup/atomic installer; primary scripts not edited yet. Actual-constructor Lua differential PASS: identical widget creation/parents/show states,18valid textures retained. Private inventory-compat-be30 ordinary native15-row GUI/open/screenshot probe pending; first reused-driver query failure retained before client launch, corrected second driver asks real client result/server admission. No NPC/AI/cadence edit, no new188 counter; original resource warnings not all resolved.

- 2026-10-08 (Codex) — hidden inventory-stat texture cleanup accepted/installed doc77. Actual15row constructor differential Lua PASS: all widgets/parents/visibility identical,18valid P/N texture names preserved, only12unused absent-region loads skipped. DX1137785253553/source64e7 fullSUCCESS. Qualified be30 engine+currentLua native ordinary known961 Actor20020+20s, GUI15retained groups and inventory IsShown=true; no12target texture warnings/no fatal/SCRIPT ERROR/handler/caught/loadout. Other27texture/10sound warnings stay separate. Native screenshot command was BLOCKED by existing GAME console policy; no image, printed marker=request only, not pixel PASS. Scoped byte installer original clientSHA16CC... afterBB1F..., ONLY2calls per2active client scripts+ownedhelper each, original backups/afterbytes verified/repeat0; server scripts untouched. All88protected fingerprints unchanged/all tests stopped/shared debugempty/no primary EXE promotion. Counters27/33/69/59 unchanged. Read-only101archive index scan under normalized stored paths finds no48candidates; no extraction/asset replacement, alias/loose-file search still separate.
- 2026-10-08 (Codex) — coordination BEFORE XR_IOConsole.cpp local-capture permission fix: actual native PLAYER screenshot/r_screenshot_mode rejected, while these commands only save own rendered frame/select its local format. Add ONLY exact2safe names to player_internal_command, preserve role/keyboard/full-console gates and all gameplay/server/debug command rejection; power_loss_bias affects EntityCondition, so keep denied. Actual classifier differential fixture imports current+old methods, permits only2new names, retains start-client-only/wireframe and explicit god/noclip/gravity/time/save-all/debug/seed negatives. Native tests/build GHAonly; source64e7 fullengine completed BEFORE next sourcepush. Ordinary local screenshot/image verification remains pending; no primary C++ install.

- 2026-10-08 (Codex) — native local player screenshot permission accepted doc78, source d3323e2fe8999890fa51818d73ec4141ae65fb5c: ONLY2safe names, role/fullkeyboard/gameplay/server/debug gates unchanged; actual747classifier differential GCC ASan/UBSan/MSVC PASS. Foundation37788240462/DX1137788240522 fullSUCCESS. Artifact11556018007 ZIPa537c48e... bothEXE04A76444... validated. SAME retained private world/known961 explicit(player), Actor20569+20s/GUI15groups, actual registered g_god denied, PNGformat/capture accepted and real944x501 PNG saved/verified/viewed. VIEW shows GAMMA LOADING artwork/progress, NOT inventory/world; qualify local capture/file output only, no first3D/focus/AltTab/humanUI pixel PASS. SM_NORMAL ignoresoptionalname and uses datedfilename, exactlyone PNG freshprivate root correlated with role/source/requestnonce/logs. qualified-acceptance.json+prestop logs+image/fixturelogs sealed.0fatal/SCRIPT ERROR/handler/caught/loadout; other assets/MCM open. ALL tests stopped/shared debugempty/all88protected primary fingerprints unchanged/no primaryEXE promotion/no pendingCI. Installed delta14sounds+20LTX+4client script files docs73/74/77; counters27/33/69/59,161unclosed. Handoff doc69 updated; next work keep easy→medium→hard and protect primary game; first3D/actual UI pixel and64 smoothness remain separate.

- 2026-10-08 (Codex) — coordination BEFORE background rendering preference repair: d332 ordinary PLAYER native log rejects user.ltx g_always_active on, startup visible=1/active=0; device skips normal rendering when inactive, explaining retained loading backbuffer in hidden probe. Registration sets ONLY rsAlwaysActive; independent foreground/input cursor capture remains controlled by real activation, exclusive fullscreen excluded. Permit exact local preference name in existing internal classifier; preserve keyboard/admin/gameplay gates. Extend actual classifier differential fixture, GHA-only compile/build, private native same-world screenshot repeat next. Do not call this human Alt-Tab/first3D acceptance; no primary EXE rollout,188 counters unchanged.

- 2026-10-08 (Codex) — coordination BEFORE silent controlled-exit support: both xrDebug::do_exit implementations unconditionally display system-modal MessageBox even with existing -silent_error_mode. Honor that explicit unattended option only for dialog, keeping reason logging/FlushLog/TerminateProcess(1) and ordinary dialog unchanged. Extend actual-method native fixture to ordinary/silent ordering; GHA-only. This enables private negative clock-checkpoint tests without visible dialogs; B06 remains unaccepted until actual exe cases. Sourcepush MUST wait current eca DX11 completes. No primary changes.

- 2026-10-08 (Codex) — coordination BEFORE keypress preference repair: d332 ordinary player log rejects user.ltx keypress_on_start off; registration defaults rsKeypress=true and normal client PreCache(60,true,true) makes GamePersistent::game_loaded wait for input. Permit exact local keypress_on_start preference alongside g_always_active, no timer/AI/server authority changes. Actual classifier differential must allow ONLY4 local capture/startup names relative to original baseline; native eca background test remains separate (no keypress exemption in that package). Pending silent-exit source2c local only; combined next source push AFTER completed eca37798261267. No primary rollout or188 count change.

- 2026-10-08 (Codex) — native ce633 graphics FAILED, preserved background-render-ce633f85e/failed-result.json + sealed logs. Local g_always_active/key_press prefs accepted; frame38 loading >60seconds arms frame-based Lua watchdog, successive normal spawn callbacks get luaL_error, inventory_box construction fatal. No owner rollout. Coordination BEFORE startup watchdog budget repair: preserve20s diagnostics and60s normal gameplay abort; use bounded20min budget ONLY while loading events queued or GPU precache remains, so legitimate GAMMA initial callback/asset work cannot poison later spawn constructors at60s. Native exact-hook boundary fixture/GHA only, then same retained-world ordinary rendering repeat. Owner now explicitly requests AFTER this repair four persistent test servers Cordon/Swamps/Garbage/Bar and separate test ADMIN account; priority before unrelated9 B06 cases (already prepared, not run). Never run nbot_* with cluster_selftest for human play: that auto-transfers every20s. Main88protected unchanged.

- 2026-10-08 (Codex) — BEFORE dedicated watchdog correction: client/server EXEs are the same non-DEDICATED_SERVER DX11 build. Dedicated runtime skips End/render but normal client-start/reload may leave precache_frame=60. Do NOT interpret that as ongoing loading on dedicated server. Loading budget condition must be queued events OR (!g_dedicated_server AND precache); fixture adds dedicated cases and proves60s gameplay protection even with stale server precache. bcc current fullengine still running; next sourcepush wait completed, bcc ordinary CLIENT acceptance can run independently because client predicate unchanged. Owner4-map local test preparation created at LostZone-4Maps-Test: clean bind_stalker restored from exact8b4056... base, qualified server/world_rules/configs, NO probes/selftest autotransfer, fresh own worlds/account test_admin/player-approved with DPAPI auto-login; native server ADMIN grant pending. No passwords/tokens printed/stored in launcher; main88 unchanged. User wants interactive client and4servers LEFT RUNNING when ready, not cleanup of that play session.

- 2026-10-08 (Codex) — doc79 startup continuation: Foundation37811183846 and DX1137811183642/source21351fe49 fullSUCCESS, artifact11565414387/bothEXE91FDA3F3... verified. bcc native completed precache and BOTH real inventory/Cordon PNGs viewed; scoped render accepted, fullprobe failed separately at legacy Gavrilenko GUI_on_show nil speaker. Owned client/server override disables oldstory completion in netcoop, preserves SP/nil safety; actual Lua51+sandbox PASS, CI step added. Owner4map private launch first missing server user.ltx, second short fs_root vs long game_data archive lookup failure; settings/preflight and exact qualified LONG fs_root corrected, failures/logs/dumps retained, third start pending. No owner reseed/primaryEXE promotion/count change. Owner playtest priority, leave requested4servers+interactiveADMIN running on success; B06nine NOTRUN.

- 2026-10-08 (Codex) — owner reports RP Stop button blocked and violent shot props/repeated contact sound/particles; prioritize these before188 continuation. BEFORE Level_input.cpp foreign region edit: RP lock currently returns before UI dispatch for mouse1/2, so Stop never receives click. Forward only to existing top UI receiver when input enabled, then swallow gameplay regardless of UI result; retain movement/fire block, Z/system-menu exceptions. Actual native prefix fixture via GHA and actual Lua stop-button regression next. Four native servers remain running; owner successfully entered test_admin ADMIN (client16940/Actor23591/precache0/worldPNG), then normal disconnect/quit; client currently closed, do not restart while diagnosing without need. Later MCM ShowDialog pure-virtual error is separate from RP input gate; startup scope must be sealed before that. Physics cause still unproved; no speculative mass/impulse/AI edits.

- 2026-10-08 (Codex) — physics finding BEFORE PhysicsShellHolder.cpp replica state edit: buffered pure-client bodies are Fix()ed, but set_State reimports angular velocity/force/torque; only linear velocity cleared. Legacy item follower already clears all4. Real PHElement::set_State reapplies all fields and real FixBody intentionally zeros4 with artificial body mass, so this violates pose-only replica contract and can spin/contact-effect artificial mass between authoritative snapshots. Clear copied replica angular_vel/force/torque alongside existing linear zero; retain authoritative queue velocities/forces, pose interpolation, collision enabled, server physics/mass/hit impulses unchanged. Actual state preparation fixture GHA only; do not claim solved server barrel fragmentation before native evidence. Owner additionally reports weapon pickup/hover, mutant freezes, god/demo teleport; queue these before original188. RP Windows fixture failed only global stub actor shadow under W4/WX; rename stub, keep warning strictness; Linux actual1024-prefix/button PASS.0ed build terminated before engine compile; no new EXE installed.

- 2026-10-08 (Codex) — GHA328 Foundation37824728218/DX1137824728127 SUCCESS; qualified artifact11571787222, separate native lab only. Actual RP prefix1024/button + replica copy10000 cases PASS both compilers. Native first trial exited hands_pockets after actual Z/mouse, but observer module-local counter invalid (retained FAIL); fixed _G and bounded real client object scan, retry25284. Lab long client aliases caused early AV; short appdata/config/script paths eliminate it, unchanged archive spelling pair; originals retained. Owner4 processes later absent, worlds/accounts retained, no primary promotion. BEFORE console allowlist edit: actual owner log rejects cl_cod_pickup_mode/g_multi_item_pickup/g_draw_pickup_item_names before auth, disabling intended pickup UI/callback. Permit exactly3 local preferences and extend actual classifier differential fixture; server ownership authority unchanged. Full ground pickup/hover still unproved. User briefly requested Darkscape then went to sleep and reiterated autonomous completion. See doc80 for exact current scope.

- 2026-10-08 (Codex) — Qualified scoped native RP input/pose exit + actual rotating-server-box/changed settled client pose with local velocities0; same floor weapon42753 before-fix native target1.677m but blocked in legacy/COD, after exact DotMarks-disabled netcoop fallback actual F/FDDA taken by client46080 and authority item journal world->test_admin v2. Later player death dropped it back world v3; wrong se.ID_Parent assertion and late corrected parent assertion retained, not substituted for journal. qualified-gameplay-scope.json records exact scope/caveats. No full hover/wall/fragment smoothness acceptance. Source now includes CPhysicsSkeletonObject in existing authority prop selection (previously skipped); actual-selection fixture extended. Per-connection ADMIN god implemented: native owner/role/alive guards, unsaved Clear(false), per-actor condition/hit/emission query, no ordinary-player pool scans; g_god sends idempotent server on/off, local flag only confirmation/new-auth reset, SP retained. Actual Lua role/args/emission/item/sandbox checks PASS; actual native God methods/predicate fixture GHA only, pending. a39 Foundation37830646398/DX1137830646479 completed SUCCESS before next push. Owner4 worlds/accounts retained; diagnostic processes15352/19644 only. Primary88 MATCH; counters27/33/69/59 unchanged; demo/mutants/hover/wall effects/restore maps still open.

- 2026-10-08 (Codex) — 9043440b8 Foundation37835454753/DX1137835454767 fullSUCCESS after fixture-only BOOL/bool and int/u16 W4/WX repair; package downloading, no primary rollout. Earlier8a full failed before engine, Linux actual God/physics passed. Private328 server19644 really crashed22:49:49, AV module5c6e9f/PDB GetRelationType147; dump read0x8/RBP0/instruction mov rdi,[rbp+8] proves nil who; NPC actor_friend/xr_meet/hit callback trace. Logs/dump sealed, private client15352 stopped, worlds/accounts retained. Native nil relation guard + dedicated nil actor-condition wrappers ready, valid behavior unchanged; actual Lua/AI/items/scope PASS, native fixture GHA pending. ADMIN demo Enter server request only, native role/owner/alive/admission/finite/map bound, reliable owner GE_MOVE_ACTOR; clear old prediction paths without sequence reset. Actual Lua parser/gate cases PASS; actual native requester/helper/MoveActor fixture ready for GHA. See doc81. Mutant split-controller guess rejected as insufficient: update_frame returns inherited before commented split calls; native runtime pose/progress observation needed. No mutant or hover/wall acceptance yet; original188 unchanged.

- 2026-10-08 (Codex) — doc81 continuation: qualified904 package privately installed with old binaries/logs/overlays backed up and20 state files unchanged. Retained world epoch2, server6532/client25468; actual RP Stop PASS again and real server God hit power10 health1->1 PASS; OFF control pending.28a Foundation37838717278 bothSUCCESS, fullDX1137838717247 engine113522491131 FAILED undeclared g_pGamePersistent in FDemoRecord; add required header, preserve failure log. Prepare nil guards BOTH visibility overloads from actual empty-server wounded evaluator failures; valid vision unchanged, actual whole-method fixture expanded. Actor-scoped God for burer/controller stamina/drop, actual fixture expanded. No primary/owner4 promotion, no mutant/hover/wall acceptance, original18827/33/69/59 unchanged.

- 2026-10-09 (Codex) — doc82: owner reports weather/shadow jumps during emission after factor60 test.4e70cc1a4 Foundation37841294377 bothSUCCESS and DX1137841294449 fullSUCCESS, no running-session update. Source display-clock mono/rate slew prevents backward packet corrections that actual WFX TimeDiff treats as almost24h; authoritative gameplay clock unchanged, actual native fixture pending GHA. Live904 RP Stop repeat/God ON hit10 HP1->1/OFF hit0.2 HP1->0.940058 PASS. Seven real fragments from second retained wood box; small fixed-copy solver velocities multiplied by synthetic ODE mass1e8 amplify FX; prepare physical-mass correction scoped to buffered fixed pure-client, actual fixture. God hint rebind central ASPLAYER ownership across respawn, actual block fixture. Three mutants progress in231 distant cached-bone samples; not full smoothness proof. Current owner client25468/server6532 remain running, later dead actor blocks alive-only weather observer; no forced restart. Normalize CRLF byte-only without history rewrite. Original188 unchanged27/33/69/59; native weather/contact/hover/teleport/respawn integration and other cases still open.

- 2026-10-09 07:45MSK (Codex) — ff53e8ff518cc56fd91aa13c993cd3307de893f6 Foundation37883870894 BOTH SUCCESS (Win113669399617/Linux113669399923), DX1137883870820 FULL SUCCESS engine113669496501. Actual mono weather/WFX, physical-mass contact FX and God respawn binding fixtures passed; no owner runtime upgrade yet. BEFORE next PhysicsShellHolder lifecycle edit: central pickup shell destruction and OnChangeVisual left old floor queue and cached replica-shell pointer. Exact allocator address reuse can retain preceding replica identity/pose. Pure-client reset before body destruction clears queue/identity/render timeline and balances only owned processing activation; server/SP retained. Actual reset/destruction fixture adds same-address reuse and idempotence, generation reviewed, GHA pending. Owner6532/25468 remain running; pending user answer about finishing weather test, do not stop silently. Original188 counters27/33/69/59 unchanged; graphical weather/FX/hover, respawn God/demo and mutant scope still open.
- 2026-10-09 14:56MSK (Codex) — resumed after permission-profile/turn interruption: bd5ab8da4 Foundation37885813597 BOTH SUCCESS (Linux113675454645/Win113675454782), DX1137885813675 FULL SUCCESS engine113675536162. Shell reset/destruction fixture passed. Old owner6532/25468 processes absent; last904 logs abruptly end without clean shutdown proof, preserve. bd5 artifact downloading, next retained-world repeat may proceed without interrupting an active game. Additional weather finding: normal GAMMA end_surge(false) deliberately retains WFX recovery tail; client adapter's extra unconditional StopWFX cut it and jumped to cached future weather. Remove only extra stop. Exact stock GAMMA end method fixture through actual client adapter Lua51 PASS (cleanup/factor restore, no client mortality/respawn, duplicate end, manual SP control). GHA pending. Parts-menu root nil se_object.parts requires real server metadata/authority work; no random/default parts or fake local ALife changes. Original188 counters unchanged.
- 2026-10-09 15:46MSK (Codex) — owner regression list recorded doc83; keep client11540/Cordon18680/Garbage16316 live. Same worlds, shared appdata, no reseed or account loss. New live config physically present but native route catalog empty; SDK appdata rescan changes native maps empty -> l02_garbage; nearest changer15726 silent1/enabled targets Garbage. Initial Lua ini_file(abs) false assertion was diagnostic path-prefix error, corrected native proof PASS. Native source adds missing catalog entry refresh + MP confirmation for silent changers; actual method fixture ready GHA, real transfer pending. Exact GAMMA fieldstrip nil-table crash reproduced, pure-client registered predicates guarded without reroll/default parts or authority writes; Lua51 + inventory/items/emission/scope PASS. Guard applied in live private client, OWNER_MENU_GUARD_INSTALLED confirmed, own command cleared. Full parts functionality, blood decals, authority pushes/barrel walls, NPC hostility/death/reputation, boundary and emission smoothness remain OPEN.805 recovery-tail DX1137927028538 fullSUCCESS cached artifact11615358162, not active-game rollout. Original188 unchanged27/33/69/59.

- 2026-10-09 16:10MSK (Codex) — doc83 continuation and current Claude prompt updated. e70 Foundation37933943908 BOTH SUCCESS actual transition/complete prop push checks; DX1137933943683 engine113831313753 still building. Native raw Lua light0 vs native0.154384 proven; SDK fallback reuse source prepared. Accepted owner AIM FireTrace skips ordinary OnShot sound/weapon-fired callback; restore only after validated existing gates, actual branch fixture. Latest owner requests persistent fragments/no visible disappearance and shell+contents mass for crates, barrels discretionary. Source no MP non-entity model autoremove timers and no blood decals on dynamic props prepared, actual fixtures; corpse/SP retained. Dynamic per-crate contents/mass NOT implemented: stock xr_box rolls only when broken; need persisted authority plan, same loot released once and native/CSE mass. Keep three owner processes/worlds, no automatic hits/moves/restart. All native gameplay scopes unqualified remain OPEN;188 unchanged.
