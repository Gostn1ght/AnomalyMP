# Промпт для Claude: продолжить Lost Zone автономно

Продолжай Lost Zone — мультиплеер GAMMA/S.T.A.L.K.E.R. Anomaly на X-Ray,
репозиторий Gostn1ght/AnomalyMP, ветка menu-3d-hideout, remote gostn1ght.
Локальная папка:
`C:\Users\Mahito\Desktop\NetAnomaly_Engine_Console_2026-09-10\NetAnomaly_Full\engine-steamnet`.
Windows/PowerShell, GitHub CLI настроен. Владелец просит закрыть все188
пунктов автономно, сначала простые, потом средние, потом сложные. Не
заканчивай работу после одного плана или прогона. Сейчас25 принято,
35 код/fixtures,69 частично,59 не сделано;163 не закрыто полностью.
Перепроверь актуальные counters по строкам doc48, а не по этому снимку.

Сначала прочитай docs/audit/45_CODEX_HANDOFF.md,48_DOC43_AUDIT.md,
43_WORLD_REQUIREMENTS_PROGRESS.md,67_DESTRUCTIBLE_STATE_RESTART.md,
68_FAILED_START_INPUT.md,70_NATIVE_WORLD_IDENTITY.md,71_NATIVE_WORLD_EXCLUSIVITY.md. Сверь git status/HEAD,
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

Основную игру пока НЕ обновляли: четыре primary exe gamma-runtime и
LostZone-3D-Hideout всё ещё SHA256
FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88.
88 primary exe/config/account/character/world fingerprints совпадают с
baseline. Проверка: python -B _build/live/fingerprint-primary-health.py after.
НЕ перезаписывай baseline; не удаляй/пересеивай owner миры, аккаунты или
персонажей ради тестов. Только узкие server PDA/item-save guards из doc57
ранее установлены с backup; новые exe/full overlays не продвигались.
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

Это НЕ чистый весь GAMMA startup:14 engine Lua File-not-found stacks для
SSFX rain sounds, inactive HUD sentinel255 warning, MCM20s diagnostics,
две NPC-loadout записи. Strict fatal/SCRIPT ERROR/handler-failed evaluator0
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
B04 accepted, counters25/35/69/59. ALL own processes stopped, debug empty,
all88 primary fingerprints unchanged, NO pending CI, no primary rollout.

Следующие простые задачи диагностированы, но НЕ исправлены:

1. SSFX sounds: архив
`C:\Users\Mahito\Downloads\GAMMA\GAMMA\GAMMA RC3.7\mods\190- Screen Space Shaders 23 - Ascii1457\db\mods\ssfx_rain_footsteps.db0`.
SHA2561465d07b0dfabbda8082f06cc08f9063ed5a6acbed4d714602d249f46ba8a655,
166511bytes. _build/live/ssfx-archive-inspection.json:14ogg rain01..08,
jump01..03,land01..03 и4directory entries — совпадают с missing diagnostics.
Header auto_load=true/entry_point=$fs_root$\gamedata\; runtime не сканирует
modовый db/mods. Сначала private отдельный FS alias только для этого архива,
с сохранением остальных assets/aliases; native getFS exist + sound_object14.
Не активируй весь отключённый мод/не меняй профиль/не копируй4.3ГБ sounds.
Архив нигде не устанавливался; existing bundled codec использован read-only,
нового native helper не компилировали.
2. player_hud::StopScriptAnim: script_anim_part начинаетсяu8(-1)=255,
GAMMA actor_effects.on_game_load вызывает stop_hud_motion без активной анимации.
part>2 ошибочно диагностирует sentinel. Будущая узкая правка должна сохранить
reset/movement/resync callbacks, диагностировать3..254,255 считать штатным.
Нужны actual method/differential fixture/GHA; не отключай все warnings и
не выдавай это за исправление мерцания персонажей.
3. Native INI _build/live/input-recovery-e609538dd/runtime-loadout-observation.json:
USP_match отсутствует, USP существует; DVL_m1 только338_federal, Ithaca20x70
только20x70_buck; AK74uM1ISG имеет6 типов7.62x39. Таблицы NPC ссылаются на
отсутствующий USP и индексы3/6 за границей. Скрипт берёт fallback0 и пишет
printe. Исправляй конкретные config mappings/совместимость, сохраняй attachment,
weight и качество по смыслу; не подавляй diagnostics и не меняй AI/population
ради скорости. Эти таблицы ещё не патчились.

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

Продолжай163 оставшихся пункта, обновляй честно doc45/48. Защити основной
вход в игру. Если лимиты заканчиваются, сохрани точный handoff/свои pending
процессы/CI/незакоммиченные файлы. Reset credits автоматически не расходуй.
Последний quota snapshot:5h used77%, weekly81%; основной runtime не обновлён.
