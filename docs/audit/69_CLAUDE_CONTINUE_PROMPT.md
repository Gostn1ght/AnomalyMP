# Промпт для Claude: продолжить Lost Zone автономно

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
68_FAILED_START_INPUT.md,70_NATIVE_WORLD_IDENTITY.md,71_NATIVE_WORLD_EXCLUSIVITY.md,72_NATIVE_WORLD_CLOCK_SCALE.md,73_RAIN_SOUNDS_RESTORE.md,74_NPC_LOADOUT_COMPATIBILITY.md,75_NATIVE_HUD_STOP_GUARD.md,76_NATIVE_FIRST_CHECKPOINT_ADMISSION.md. Сверь git status/HEAD,
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
Последний quota snapshot 2026-10-08:5h used1%, weekly0%; reset автоматически
не расходовали. Snapshot из прошлой сессии99/84 устарел. Основные EXE
прежние;14 новых sound assets и20 scoped NPC loadout LTX установлены.
