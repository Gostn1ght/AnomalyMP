# Промпт для Claude: продолжить Lost Zone автономно

## Последнее уточнение, 2026-10-09 07:45 MSK

ff53e8ff5: Foundation37883870894 обе SUCCESS, DX1137883870820 fullSUCCESS
(engine113669496501). Weather/WFX clock, FX physical mass, God respawn binding
и остальные actual native fixtures прошли. Новые EXE пока не установлены;
сервер6532/клиент25468 всё ещё904, владелец играет. Вопрос о завершении его
проверки ожидает ответа; отсутствие ответа не разрешает остановить игру.
Следующая точечная правка: очистка очереди старых floor poses/replica identity
перед уничтожением shell при pickup и смене visual; повторный drop может получить
тот же адрес. Actual destruction/reset fixture расширен, GHA ещё pending.
Doc82 содержит границы проверки. Счётчики188 не повышать без приёмки.

## 2026-10-09: новый приоритет владельца — рывки погоды/теней при выбросе

Сначала doc82.4e70cc1a4 Foundation37841294377 обе SUCCESS, DX1137841294449
fullSUCCESS. Текущая игра6532/25468 всё ещё qualified904; владелец играет, не
останавливать ради обновления. God ON actual hit10 HP1->1 и OFF hit0.2 HP1->0.940058
PASS, RP Stop повторно PASS. Части второго ящика реально записаны, fixed-копии
имеют маленькую ODE скорость, а synthetic mass1e8 усиливает звуки/частицы.
Готовится коррекция FX на physical mass только buffered fixed pure-client.
Weather root: backward correction -100ms приводит WFX TimeDiff к почти86400sec,
мгновенно съедает эффект. Новый визуальный clock — mono + rate slew без phase
скачков, gameplay authoritative calendar прежний; native exact fixture готов.
Также God hint rebind при новом Actor после respawn, actual binding fixture.
Следующая GHA pending. Счётчики188 прежние. Byte-only normalize staged после
ошибочного CRLF commit; историю не переписывать. Живая weather probe пока не
сработала из-за dead actor; не заявлять полный native PASS. Детали в doc82.

## Свежий приоритет: игровые баги, 2026-10-08 вечер

Новее нижних строк: doc81 продолжение23:45.904 скачан/квалифицирован, установлен
только в retained private lab, server6532/client25468 работают. RP Stop снова PASS;
серверный hit power10 после normal g_god on оставил HP1->1. OFF/control ещё pending.
28a Foundation37838717278 обе SUCCESS; fullDX1137838717247 FAILED: FDemoRecord
не включил IGame_Persistent.h. Исправляется вместе с native nil обеих see overloads
(реальный empty-server wounded evaluator failure) и Actor-scoped God для атак
бюрера/контролёра; actual fixtures расширены. Полной clean-session/hover/mutant
квалификации ещё нет. Состояние owner4/main сохранено. Счётчики188 не повышать.

Сначала doc81:9043440b8 обе Foundation/DX11 fullSUCCESS, пакет скачивается;
предыдущий8a провалил только Windows fixture до engine. В private328 lab реальный
server AV GetRelationType(nil)22:49:49: dump fault0x8/RBP0/PDB+инструкция доказаны.
Сервер19644 завершился, private15352 после sealing остановлен; сейчас нет процессов.
Миры/учётки сохранены. Native relation-null guard + серверные условия nil actor,
ADMIN demo teleport через сервер и очистку старой prediction history без reset
sequence готовятся следующей GHA. Lua regressions PASS, native/full tests pending.
Есть отдельная поздняя UI hspairs(nil) ошибка, не назвать scoped RP/pickup proof
чистой полной сессией. Mutant freeze/smoothness и weapon hover/wall acceptance
ещё открыты; не применять догадки о split-animation или отсутствии UpdateTracks.

Более свежий результат: actual RP native mouse Stop exactly1 + pose exit PASS;
qualified-gameplay-scope.json в отдельном lab. Pickup original42753 при корректном
прицеле блокировался DotMarks/FDDA; точечный fallback only-netcoop при killswitch
прошёл native F/FDDA pickup и authority journal world->test_admin v2. Потом
персонаж умер/respawn, item обратно world v3; wrong ID_Parent и поздняя parent
assertion сохранены FAIL, это не опровергает более ранний journal, но не считать
полной hover/drop/restart квалификацией. Source добавляет пропущенный класс
CPhysicsSkeletonObject в server physics replication; actual filter fixture.
God source новый per-connection native state/role validation + per-actor damage/
condition/emission check + g_god server request/confirmation; GHA/native pending.
a39 обе GHA SUCCESS. Первыми закончить GHA/native эти правки, затем demo teleport,
mutant smoothness/freezes, hover/wall, восстановление private maps; потом188.

Сначала прочитай doc80 и последние записи doc45. Снимки процессов ниже устарели:
все4 сервера владельца позже отсутствовали, миры/accounts сохранены. Новая328
сборка/обе Foundation/полный DX11 SUCCESS; qualified package только в отдельном
owner-gameplay-repro-3289dfd96. Исправлены RP input gate и dynamics копии реплик;
полная проверка игровых багов ещё НЕ закрыта. Native RP trial получил выход
из hands_pockets, но счётчик теста был ошибочно module-local; повтор с _G
наблюдателем начат. Длинные пути lab client вызвали ранний AV; short aliases
устранили его без смены archive/root pair. Не продвигать в PRIMARY на этом основании.
Pickup cfg commands до аутентификации блокировались (есть реальный журнал);
точечный allowlist+actual classifier differential fixture готовятся в GHA.
Далее floor pickup/hover, barrels/fragments/wall contacts, mutant smoothness/freezes,
server ADMIN god и demo teleport; затем188. Без урезания NPC/частоты/видимости.
Владелец ушёл спать, работать автономно; раньше просил также Тёмную Лощину
(k01_darkscape) для переходов, сохранить/add private maps после квалификации.

## Более свежий приоритет 2026-10-08: четыре карты для владельца

Прочитай doc79 и последние записи doc45 раньше устаревшего снимка ниже.
Engine21351fe49aceaee8624f16515af6a47a24031b80 собран/проверен ТОЛЬКО GHA:
Foundation37811183846 и DX1137811183642 SUCCESS, artifact11565414387,
обаEXE91FDA3F357C3694BDCF68C01A9DE69D9C854A47524EFD6781A792E8849CA4CAA.
Exact local g_always_active/keypress_on_start разрешены PLAYER; bounded startup
watchdog сохраняет normal60s protection и не считает stale dedicated precache
загрузкой. Actual768 hook cases GCC/MSVC PASS. Silent do_exit сохраняет причины,
FlushLog/exit1; только existing-silent option отключает modal message.

Предыдущий bcc native клиент завершил precache: ОБА реальных PNG просмотрены,
inventory15groups над Кордоном и мир/HUD/NPC. Qualified-render-scope.json + sealed
after-failure logs в background-render-bcc28d4ae. FULLprobe FAIL отдельно из-за
старого z_gavrilenko_tasks_fix GUI_on_show nil speaker. Новый client/server
override отключает old story autocompletion в netcoop, SP сохранён, nil safe;
actual Lua51 regression+sandbox PASS. Primary scripts/EXEs не продвигались.
Не повторяй scoped pixel/startup proof без новой причины; это не64 acceptance.

Владелец просит запустить Кордон/Болота/Свалка/Бар и интерактивный test_admin.
Отдельная LostZone-4Maps-Test, native GHA213 package+новые Lua guards, fresh
private namespaces, shared account/cluster, DPAPI auto-login, NO automatic
cluster_selftest transfers. Native console sv_account_role должен подтвердить
ADMIN, затем actual login/Actor/precache/world PNG. Clean original actor binder,
только read-only once screenshot observer. На успехе ОСТАВИТЬ ВСЕ4SERVERS И
ЧЕЛОВЕЧЕСКИЙ КЛИЕНТ РАБОТАТЬ: прежнее правило ниже «stop all probes» к этой
явно запрошенной игровой сессии не относится. Проверь running-servers.json/
running-client.json и собственные PID перед любым запуском/очисткой.
Девять B06 checkpoint cases уже подготовлены, НЕ ЗАПУСКАЛИСЬ; отложены,
пока владелец играет. Counts27/33/69/59,161unclosed без новых закрытых188.

Первая попытка четыре сервера не имела user.ltx; settings добавлены и preflight
защищает повтор. Вторая выявила Empty lightning_model: short fs_root и long
game_data рассогласовали виртуальные archive keys. В server fsgame
восстановлена исходная LONG пара fs_root/game_data. Client использует СВОЮ
qualified SHORT пару; ошибочное применение LONG server root к SHORT client
привело к первому interactive crash (owner сообщил), журнал сохранён отдельно.
Оба launcher теперь проверяют буквальное согласование пары; UTF8noBOM.
Старые failed-start/logs/dumps сохраняются, owner worlds не удалялись.
Третья server попытка успешна:4durableReady, native ADMIN grant подтверждён,
PIDs7732/20264/21592/14656 по порядку выше. Interactive повтор PID16632 loading;
финал дописать после native auth/Actor/precache/PNG. Не останавливай4живыхсерверов.
Actual88primaryfingerprints MATCH. Source1b01b013d pushed, DX1137816511889
Lua checks SUCCESS, fullengine pending; private EXEs qualified213 (C++unchanged).

Продолжай Lost Zone — мультиплеер GAMMA/S.T.A.L.K.E.R. Anomaly на X-Ray,
репозиторий Gostn1ght/AnomalyMP, ветка menu-3d-hideout, remote gostn1ght.
Локальная папка:
`C:\Users\Mahito\Desktop\NetAnomaly_Engine_Console_2026-09-10\NetAnomaly_Full\engine-steamnet`.
Windows/PowerShell, GitHub CLI настроен. Владелец просит закрыть все188
пунктов автономно, сначала простые, потом средние, потом сложные. Не
заканчивай работу после одного плана или прогона. Сейчас27 принято,
33 код/fixtures,69 частично,59 не сделано;161 не закрыто полностью.
Перепроверь актуальные counters по строкам doc48, а не по этому снимку.

Сначала прочитай docs/audit/45_CODEX_HANDOFF.md,48_DOC43_AUDIT.md,
43_WORLD_REQUIREMENTS_PROGRESS.md,67_DESTRUCTIBLE_STATE_RESTART.md,
68_FAILED_START_INPUT.md,70_NATIVE_WORLD_IDENTITY.md,71_NATIVE_WORLD_EXCLUSIVITY.md,72_NATIVE_WORLD_CLOCK_SCALE.md,73_RAIN_SOUNDS_RESTORE.md,74_NPC_LOADOUT_COMPATIBILITY.md,75_NATIVE_HUD_STOP_GUARD.md,76_NATIVE_FIRST_CHECKPOINT_ADMISSION.md,77_INVENTORY_UNUSED_TEXTURES.md,78_NATIVE_PLAYER_SCREENSHOT.md. Сверь git status/HEAD,
Actions, свои процессы и qualified acceptance. Более свежий журнал важнее
этого промпта. Не ставь native PASS по одному backend unit-test/fixture.
Не добавляй к узкому готовому пункту требования соседних этапов.

Все C++ сборки и native fixtures ТОЛЬКО GitHub Actions. Не подделывай
GITHUB_ACTIONS для локальной компиляции. Локальные Python/Lua5.1/PowerShell
и запуск готового проверенного GHA exe разрешены. Source push отменяет
текущую DX11 сборку: дождись завершения; docs-only push безопасен. Git:
pull --rebase gostn1ght menu-3d-hideout перед push; без reset/stash/add-A.
Не добавляй чужие файлы. Перед foreign-region edit координируйся в doc45.
Трейлер: Co-Authored-By: Codex <noreply@openai.com>.

Сервер авторитетный, отдельный процесс на карту, цель кластера512 игроков.
NPC/мутанты — в количестве и с поведением GAMMA freeplay. Нельзя урезать
население/каденс ИИ/зрения, замедлять игроков или оставлять видимых NPC
застывшими/дёргаными даже на максимальной видимости. Lua меняет состояние:
не кэшируй её результаты наивно и не параллель общий Lua state. Разные глаза
не дают эквивалентных лучей. Без безопасного решения тяжёлая64-проблема
может временно остаться открытой по разрешению владельца. Старые headless64
и разные миры не доказывают визуальную плавность или честный A/B.

Живые NPC/мутанты не респавнятся и полностью сохраняются. Предметы на полу,
тайники/содержимое сохраняются. Трупы с оставшимся лутом удаляются при
рестарте и через40мин без игрока рядом; отдельные предметы не удаляются
этим правилом. Пустая карта спит, ориентир загруженного сервера1.5ГБ.
Переходы карт обязательны. Старый сюжет/предметы/задания вырезаются. Можно
оставить выбранных бывших сюжетных NPC мини-торговцами с НОВЫМИ сложными
контрактами. У Лукаша5–10 задач для вступления в Свободу; лидера-игрока
назначает админ. Роли игрок/лидер/админ. Не возвращай старый сюжет.

Основные EXE пока НЕ обновляли: четыре primary exe gamma-runtime и
LostZone-3D-Hideout всё ещё SHA256
FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88.
88 primary exe/config/account/character/world fingerprints совпадают с
baseline. Проверка: python -B _build/live/fingerprint-primary-health.py after.
НЕ перезаписывай baseline; не удаляй/пересеивай owner миры, аккаунты или
персонажей ради тестов. Только узкие server PDA/item-save guards из doc57
ранее установлены с backup. Также приняты и установлены только14 новых SSFX
OGG (doc73); существующий junction даёт их обеим основным папкам. Новые exe/
full overlays не продвигались, основные world/account/character файлы прежние.
Также doc74:20 loadout LTX files (9rows/5files ×4 active client/server roots)
точечно исправлены, original byte backups retained. Эти LTX вне baseline88;
нельзя писать, что все primary configs неизменны.
Doc77 также устанавливает ONLY2call-site changes per2client UIInventory
scripts + helper each (4script files), exact backups. Server scripts untouched.
Для rollout нужны scoped обычный вход, проверенная версия, backup и
совместимость основного мира. Один bot PASS не основание заменить всё.

Текущая законченная правка — два native падения при повторном входе (doc68).
Не добавляй их произвольно в188 counters:

- CLevel::net_start6 удалял уровень после auth failure, оставляя его в CInput
stack. Реальный4b dump/PDB: CInput::iCapture:655, AV/read0x30; pInput валиден,
старый receiver уничтожен. Код4cea делает IR_Release до failed deletion.
Actual net_start6/iRelease fixture квалифицирует старый control/все ветки.
a428 Foundation37750844941 и DX1137750844864 SUCCESS. На actual exe unknown960
после загрузки карты -> живое меню PASS. Attempt1 не смог обработать mailbox
из скрытого main_menu: свой GUID сохранён/очищен, ограничение инструмента.
- Attempt2 сохраняет original Update menu+login,7живых callbacks после отказа,
native login961 в том же процессе -> новый AV при main_menu off из Update.
a428 exact PDB CDialogHolder::OnFrame UIDialogHolder.cpp256/address14032c89c.
CleanInternals очищал vector во время callback, инвалидируя iterator.
Production asynchronous EnterWorld тоже закрывает меню из Update. e609
использует индекс с повторной size-проверкой без references через callback,
очищает deferred закрытые окна. Actual fixture:256legacy traces + clear/delete/add.

Финальный e609538ddc5f197a959b273bd9375d624d928f06 Foundation37756749563 и
DX1137756749573 SUCCESS. Artifact11541183178,
ZIP93e019ca25765cc8acaf0675d66b95e2844d3f229522748dce7acc284edc3d6d,
both exe96FB0C81503A5B99DCA3559ED951FA241C082993BAA7D8617E2B811A6019012A.
Кэш _build/gha/dialog-e609538dd. Полный native recovery PASS:
_build/live/input-recovery-e609538dd/qualified-acceptance.json. Unknown960
после загрузки карты -> live menu/form -> exact GUID valid961 retry ->
ordinary Actor20123 в ТОМ ЖЕ PID10380 ->30сек игры. SAME retained server
world selftest_destructibles_correlated, не новый мир. Два pre-stop журнала,
package/source/hashes запечатаны; старые FAIL/dumps сохранены.

Исторический e609 recovery НЕ был чистым GAMMA startup:14 engine Lua
File-not-found stacks SSFX rain, inactive HUD255 warning, MCM/loadout.
Теперь отдельно принята и установлена звуковая правка doc73; остальные
диагностики требуют своей приёмки. Strict fatal/SCRIPT ERROR/handler-failed evaluator0
не считает все engine diagnostic stacks. Doc67 поправлен: его ранняя фраза
zero Lua была слишком широкой. Native recovery и L30 остаются принятыми;
human Firebase, menu art, max-view64 и все gameplay callbacks не приняты.

B03 закрыт doc70 на real GHA4b server:
_build/live/identity-native-4b74ba7f2/acceptance.json. Fresh private appdata,
первые actual40bytes сохранены в aborted.authority ДО остановки первого
старта. Два следующих ready-start SAME world, WorldID13564581398834934011,
seed14696362713997730183, epochs1→2→3. Независимый parser проверяет exact
bytes/magic/FNV/пять журналов. Первую identity не восстановили догадкой из
последней. B04 этим НЕ проверен.

Первая комбинированная _build/live/authority-native-4b74ba7f2 НЕ принята:
contender жив, в журнале нет acquired/ready или причины отказа. Таймаут/
hashes в unqualified-attempt.json. Не диагностируй по низкому CPU.
do_exit вообще не логировал reason перед FlushLog/MessageBox/TerminateProcess.
Source171473a9940abbfe3e15564bbb2dbb7e63ee5c6c добавляет постоянный Msg-префикс
! [X-Ray][exit] до прежнего flush/dialog/terminate. Actual fixture импортирует
оба метода, проверяет sequence/message. Shared PS gate ловит anchored prefix,
не обычные debug-упоминания;593c ранее добавил actual UnhandledFilter footer.
PS/native fixtures PASS. Поведение завершения/игры не менялось.

171 Foundation37759512127 и DX1137759512199 SUCCESS. Artifact11541814586,
ZIPd20186624d34399c6337fc23f88aba9b965981c61a7121c06422bf842122363c,
both exe2136C663EE24352B9A232AB1D6A5E70ADDE377A85B369BE9305DB7EBECA356AA.
Кэш _build/gha/exit-171473a99. Native B04 PASS (doc71):
_build/live/authority-native-171473a99/acceptance.json. Fresh local directory,
interrupted first durable record sealed -> ready owner epoch2 -> actual
contender explicitly rejected ! [X-Ray][exit] world is locked or lock file
is inaccessible -> authority SHA unchanged, no acquired/ready -> original
owner remains ready -> owner stop -> new server ready epoch3+30seconds.
WorldID15883345463564265689/seed8924220031495453929 unchanged,1→2→3.
Independent parser verifies actual records/magic/FNV and six sealed journals.
Expected contender exit separate from zero unexpected owner fatal/Lua/handler
failures. Old quiet attempt stays UNQUALIFIED. No distributed fencing proof.
B04 accepted. Затем B01 native PASS (doc72): ALife-backed WorldClock положительные scales6/12/3/1/6, все immediate deltas0, пять mono/game samples совпадают с ожидаемым rate (max discrepancy36ms), даты далеко за32-bit, factor6 восстановлен. Core portable/overflow/monotonic fixtures GCC/MSVC PASS. clock-acceptance.json и sealed pre-stop log в authority-native-171473a99. Это local core, не distributed sync/location adoption/global scale barrier. Counters26/34/69/59. ALL own processes stopped, debug empty,
all88 primary fingerprints unchanged, NO pending CI, no primary rollout.

Текущая звуковая правка ЗАКРЫТА (doc73), не новый пункт188:
sourceb18254429effffb23c653f09a517ac5358da2e82 содержит installer/hash manifest.
Локальный исходный archive SHA1465d07b...;14OGG декодированы существующим
codec с CRC/size/OggS/SHA. Original GAMMA/profile/archive не менялись.
_build/live/rain-sound-e609/qualified-acceptance.json: обычный GHAe609
Actor после реального входа961,14sound_object длительностей512–838ms,
ещё15сек игры,0target-rain-Lua/fatal/SCRIPT ERROR/handler/caught на обеих ролях.
SAME selftest_destructibles_correlated private world; no owner credentials.
Stand-alone timeout/first server alias failure retained, не PASS.
Primary-assets-installation.json: добавлены ONLY14 OGG под
gamma-runtime/gamedata/sounds/material/human/step. Hideout использует existing
junction; обе папки SHA verified. Повтор installer добавляет0/keeps14.
Все88 защищённых fingerprints прежние; новые sound assets вне baseline88.

HUD255 диагностическая правка ПРИНЯТА doc75, PRIMARY EXE НЕ обновлён:
StopScriptAnim excludes only inactive255, callbacks/reset/3..254 diagnostics
unchanged. Actual2048 differential cases GCC ASan/UBSan + MSVC PASS.
b182 Foundation37768760407/DX1137768760410 failed fixture before engine:
control rename changed Msg literal; Windows default decoder incompatible.
Fixture-only be30 declaration-only rename+latin1 preserves assertions.
Foundation37773463706/DX1137773463776 SUCCESS fullengine/package/upload.
Sourcebe30a8bb2bef31452eed26d2e945b6fad2f41778, artifact11549278414,
ZIP6f02b5cd8bd3a0f798f4d1d6195b4e161655d167d742b4524e1886b14677605b,
bothEXE4BA7566067A0B457AA5C40AAC3C0EDDEDE08DDEE8D37597A7FCB780C51968711.
_build/live/hud-be30a8bb2/qualified-acceptance.json: SAME private correlated
world, ordinary known961 Actor20608/PID13152+20s, native first-window-frame
presented,3actual game.stop_hud_motion calls, no invalid-part diagnostic.
NO extra rain archive mounted:14PRIMARY installed sounds actual lengths
512–838ms,9targeted native loadout section/key/caliber checks on both roles.
No fatal/SCRIPT ERROR/handler/caught; all HUD processes stopped/debugempty.
This does NOT fix visible character blinking or prove human Firebase/UI/64.
Other native asset warnings remain:38textures/10sounds + MCM. Earlier
zero missing-sound shorthand meant target14rain Lua exceptions only; current
docs73/74/75 clarify. _build/live/remaining-resource-warnings.json records
exact names. Do not silently suppress diagnostics or replace custom assets.
Source44730a31a adds only config installer/manifest/docs, no nativeC++
change. Its redundant DX11 run37776467719 SUCCESS; no pending CI. Be30
package remains the validated ordinary HUD/native G12 acceptance version.

NPC config compatibility repair ПРИНЯТ/УСТАНОВЛЕН doc74:
scripts/install-netcoop-npc-loadouts.py + fixtures/npc-loadouts/compatibility.json.
9точных section/key pairs/5files: USP_match→USP; Ithaca20x70 index3/6→0;
DVL_m1 index3→0; AK74uM1ISG index6→3 (pristine7.62AP). Attachment/weights/
accessory chances/comments/newlines/unrelated bytes unchanged. Missing USP
restored to intended pool: don't claim identical RNG/item choices. No NPC
population/AI/cadence edit. Installer preview default, all-row preflight,
exclusive original backup, atomic replacement avoids hardlink write-through.
_build/live/loadout-e609/qualified-acceptance.json: GHAe609 ordinary known961
Actor26903 +20s; SAME retained private correlated world. Actual native INI
on BOTH roles verifies9 exact section/key pairs, actual calibers/quality and
all random USP ammo section existence;0loadout/target-rain-Lua/fatal/SCRIPT
ERROR/handler/caught on sealed logs. Two failed private query controls
(non-raw Python path, whole-table count across unrelated factions) retained,
strict assertions rejected before client launch. Final ammo checks not relaxed.
Primary-installation.json: only5files/9rows per4 ACTIVE config roots:
gamma-runtime/client/configs, gamma-runtime/server/configs,
LostZone-3D-Hideout/client/configs, LostZone-3D-Hideout/server/configs.
Relevant primary weapon configs match staged bytes before install. Exact
original backups _build/live/loadout-e609/primary-backups; after SHA verified,
repeat preview0. Fallback gamedata configs/original GAMMA not edited.
All88 protected fingerprints unchanged; these20LTX outside88 baseline.
No proof all generated NPC item packets, human gunfire or immortal/jerky AI.
All loadout/HUD test processes stopped/debugempty after their acceptances.
G12 принят doc76: _build/live/bootstrap-admission-be30-2/
qualified-acceptance.json. ONE private controller/new appdata, no owner
worlds/accounts copied/deleted. Same validated be30 native engine, normal
AI/population/bootstrap30s/retry15s. Scoped Lua fault checker returnsfalse
for THIS server's script_snapshot_matches, seven actual native checkpoint
verifications rejected; no committed pointer, exact native connection IDs
nbot202/203 rejected, no Actor. ORIGINAL checker restored, bootstrap LZW3
commit succeeds; sizes/FNV64 for BOTH.scop/.scoc verified, first files and
pointer sealed. Only AFTERcommit nbot204 Actor42752+20s/final1playing.
First observed refusal follows an initial failed save: pre-COMMIT proof,
not a request before the first attempt. Expected failed negative bots and
incomplete-save messages are controlled faults, separate from unexpected
fatal/SCRIPT ERROR/handler/probe/loadout0. Old bootstrap-admission-be30
retained UNQUALIFIED: server-only reason awaited on bot, competing cleanup
interrupted recovery. Do not delete/reseed or invent PASS for old root.
ALL tests stopped/shared debug empty/all88protected fingerprints unchanged.
Current audit27/33/69/59,161 unclosed. LOCAL first-commit gate only; disk
crash/distributed/other transaction cases remain separate. Don't rerun full
accepted cases without new changes/reason. Next simple cleanup may inspect
38remaining texture/10sound warnings; some UI names are atlas REGION keys,
not missing DDS files, so check XML definitions before copying/creating assets.
Native64/max-view and broader clock/chunk/transaction work remain queued.

Inventory unused texture cleanup accepted/installed doc77:
source64e7a3087 Lua helper/installer/actual ctor fixture; DX1137785253553
fullSUCCESS. Original clientui_inventory SHA16CCF35AE84EA1F014FC1D38BF96617F99DE8BE44B62DE02368ADA8CCC5ABD32,
afterBB1F05ECBE83CF1E8B6333A4AE7C14739CABEB3583B93678F0990C4B4E2C325F.
Actual ctor Lua diff preserves all15rows/widgets/parents/show states and
18valid texture names; skips12unused absent P/N regions for six extra stats.
Native _build/live/inventory-compat-be30/qualified-acceptance.json: be30
engine+currentLua, known961 Actor20020/inventory opened+20s; all15native
stat groups retained/no target12warnings. Other27texture/10sound+MCM persist.
Only2call sites per2active primary client scripts + owned helper each;
backups under primary-backups, installed bytes match tested source/repeat0.
All88protected fingerprints unchanged; these script files OUTSIDE baseline88.
Screenshot NOT accepted: existing GAME console policy rejected screenshot/
r_screenshot_mode for player, no image. Native logged marker=request only.
XR_IOConsole local screenshot fix ПРИНЯТ в новом GHA engine doc78:
source d3323e2fe8999890fa51818d73ec4141ae65fb5c addsONLY screenshot and
r_screenshot_mode; full keyboard-console/role/gameplay/server/debug gates
unchanged. power_loss_bias affects stamina and stays denied. Actual747
classifier differential cases GCC ASan/UBSan + MSVC PASS. Foundation37788240462
and DX1137788240522 SUCCESS. Artifact11556018007,
ZIPa537c48ec04e7ba272805ebfd6272a4c9d0bdb339f9de22f32ea31d2747d13ff,
bothEXE04A764441C50AF214C45913876232D29304AFACA7FB1B86ECFE667FDA80ECD96.
_build/live/console-capture-d332/qualified-acceptance.json: SAME private
world/known961 explicit PLAYER role, Actor20569+20s, actual inventory15row
groups/open flag; registered g_god on rejected, PNG format/capture allowed,
actual944x501 PNG saved/verified and viewed. Image shows GAMMA LOADING screen,
NOT inventory/world. Accept local capture/file output only; first3D/world
pixels/window-focus/Alt-Tab and human UI NOT proven. Hidden/background
rendering may keep the loading backbuffer; don't invent diagnosis from this.
SM_NORMAL names dated file, optionalname ignored; exactlyone PNG under fresh
private root, source/role/log/request nonce sealed. No local C++build and
NOprimaryEXE promotion. ALL own processes stopped/shared debugempty, all88
protected fingerprints unchanged. No pending CI. Counters27/33/69/59 remain.
Current native accepted package d332; older be30/e609/171 proofs remain valid
for their cases. Source/doc HEAD via git; do not rerun accepted cases without
new change/reason. Next priority easy→medium→hard, remaining161 original188
and unresolved resources/foreground first3D/inventory pixels before rollout.

L30 закрыт doc64–67: actual GHA4b glass/wood/metal, exact health0.6/original
INI после restart,0.7 уничтожает, checkpoint/второй restart сохраняют отсутствие.
151untouched объектов,8natural bottle parts с IDs/model/health/pose (max2.3мм).
Ordinary peers Actor20123/20239 видят15505 intact -> damaged после SAME restart
-> absent. Trusted server hits, НЕ human weapon RPC/screenshot/64/velocities/
chunk hydration. Не повторяй всю приёмку без новой причины. Private root
_build/live/destructibles-correlated-4b74ba7f2 сохраняется. Doc59/60 scoped
плохая сеть/две карты/4бота/mixed NCH7→8 переходы тоже уже приняты;
общие ItemLedger/chunks/512 пункты ими не закрыты.

Приватные stage/install helpers отказывают на существующем root. Не удаляй
старые данные ради повторного запуска: новый root/точный backup. Запуск Hidden,
ordinary client BelowNormal; остановка только своих PID с проверенным exe.
Не оставляй тесты после завершения. Shared gamma-runtime/netcoop_debug_l01_escape.lua
не перезаписывай с чужой pending командой; собственный GUID preserve/verify
до очистки. Только GUID correlation — старый log-length delimiter был неверен.

Логи bytes.decode(cp1251,errors=replace), scripts сохраняй исходными байтами,
fsgame UTF8 БЕЗ BOM. PowerShell не раскрывает rg-globs: directory/-g,
для _build --no-ignore. Python -B без pyc. Downloader:
python -B _build/live/quick-transitions/fetch-artifact.py RUN FULL_SHA CACHE API_IP.
API_IP140.82.121.5, temporary curl --resolve со строгим TLS; глобальные hosts/
DNS не менять. Token memory/stdin, не печатай secrets/signed URLs. Source,
built-from, ZIP digest, manifest и exe hashes проверять обязательно.

Продолжай161 оставшийся пункт, обновляй честно doc45/48. Защити основной
вход в игру. Если лимиты заканчиваются, сохрани точный handoff/свои pending
процессы/CI/незакоммиченные файлы. Reset credits автоматически не расходуй.
Последний quota snapshot 2026-10-08:5h used23%, weekly4%; reset автоматически
не расходовали. Snapshot из прошлой сессии99/84 устарел. Основные EXE
прежние;14 новых sound assets,20 scoped NPC loadout LTX и4scoped client
script files установлены. Local screenshot C++permission native accepted doc78, NOprimaryEXE rollout;
image is loading screen, no inventory/world pixel acceptance.
