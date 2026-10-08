# Промпт для продолжения Lost Zone

Продолжай автономную разработку Lost Zone — мультиплеера GAMMA/S.T.A.L.K.E.R.
Anomaly на X-Ray. Репозиторий Gostn1ght/AnomalyMP, ветка menu-3d-hideout.
Локальный репозиторий:
`C:\Users\Mahito\Desktop\NetAnomaly_Engine_Console_2026-09-10\NetAnomaly_Full\engine-steamnet`.
Сначала прочитай docs/audit/45_CODEX_HANDOFF.md, docs/audit/48_DOC43_AUDIT.md,
исходные требования docs/audit/43_WORLD_REQUIREMENTS_PROGRESS.md и последние
docs/audit/66–68. Проверь фактический git status/HEAD и результаты Actions;
не принимай состояние этого промпта за более свежее, чем журнал.

Цель владельца — закрыть все188 пунктов, сначала лёгкие, потом средние,
потом сложные. Сейчас23 полностью проверены,37 реализованы/проверены fixtures,
69 частичны и59 не сделаны.165 пунктов ещё не закрыты полностью. Не считай
backend unit-test доказательством работы адаптера в реальной игре. Не ставь
✅ без достаточного native-доказательства исходного требования; не добавляй
к отдельному пункту требования соседних этапов, чтобы бесконечно откладывать
его закрытие. Исторические и текущие счётчики doc48 различаются намеренно.

Владелец разрешил продолжать самостоятельно и просил сохранить возможность
входить в игру как раньше. Сервер авторитетный, отдельный процесс на карту,
план кластера512 игроков. Все native-сборки и C++ fixtures — ТОЛЬКО GitHub
Actions. Локально разрешены проверки Lua5.1/Python/PowerShell и запуск готовых
GHA exe. Не отменяй текущую полную сборку новым source push. Для native
fixture есть проверка GITHUB_ACTIONS; не подделывай её ради локальной сборки.

NPC и мутанты должны иметь количество и поведение GAMMA freeplay. Нельзя
снижать частоту их ИИ/зрения, убирать население, замедлять игроков или оставлять
видимых персонажей застывшими/дёргаными, включая максимальную видимость.
Lua GAMMA меняет состояние; нельзя наивно кэшировать её результаты или
параллелить общий Lua state. Лучи из разных глаз не эквивалентны.
Тяжёлую64-проблему владелец разрешил временно оставить открытой, если безопасного
решения нет. Не выдавай прошлые headless64/разные миры за контролируемый A/B
или доказательство визуальной плавности.

Живые NPC/мутанты не респавнятся и полностью сохраняются; предметы на полу,
тайники и их содержимое тоже. Трупы с оставшимся лутом удаляются при рестарте
и через40мин без игрока рядом; независимые предметы не удаляются этим правилом.
Пустая карта спит, загруженный сервер ориентировочно1.5ГБ. Учти переходы карт.
Исходный сюжет и его предметы удаляются. Допускаются выбранные бывшие сюжетные
NPC как мини-торговцы с НОВЫМИ сложными контрактами; у Лукаша5–10 заданий для
вступления в Свободу. Лидера-факционного игрока назначает админ; роли игрок,
лидер, админ. Не возвращай исходные сюжетные квесты под видом этих контрактов.

Сейчас приоритет — завершить native-приёмку исправления падения при отказе
во входе. Код `CLevel::net_start6` в src/xrGame/Level_start.cpp теперь освобождает
захват ввода до удаления уровня. Ранее обычный клиент мог загрузить карту,
получить отказ авторизации и удалить уровень, оставив его в CInput stack;
меню на следующем кадре вызывало метод уничтоженного объекта. Это доказано
реальным minidump/PDB/read-only запросом, а не гипотезой о пустом pInput.

Native-код исправления —4cea23d23, последняя коррекция fixture —
a428731720378abf1c01184c3abd17fe6c5fdcdf. Foundation37750844941 PASS Linux
GCC/ASan/UBSan и WindowsMSVC, actual net_start6/iRelease, квалифицированный
pre-fix control и все failure branches. Первые два запуска CI не прошли
из-за самого fixture: пропущенного alias IInputReceiver, затем старого
MSVC-warning преобразования vector::size в u32. Engine/assertions не меняли;
warning подавлен только внутри импортированного старого iRelease.
DX1137750844864 SUCCESS. Artifact11539071054,
ZIPf3330cd418dc8b99f64f298fc0f42d12912de83a0d702e6c6a7b3afba331e413;
both exe28859EF757A0BD2BF0365B4D8B4CC2D0040C777117B2AC924D4E410CB3A281D1.

Подготовлен приватный `_build/live/input-recovery-a42873172/run.ps1`:
неизвестный тестовый nbot_960 получает отказ -> обычное меню продолжает
Update ПОСЛЕ отказа -> через нативный login API входит существующий nbot_961
в ТОМ ЖЕ процессе -> actor ready и30сек живого клиента. Это проверка
восстановления, не Firebase-регистрация владельца. Перед запуском нужны
успешный GHA пакет, проверенные built-from/manifest/ZIP/exe hashes и
installed-from.json. Пакет уже установлен только в этой приватной папке.
Отказ после загрузки карты -> живые menu/form Update прошёл на actual exe.
Attempt1 не смог выполнить mailbox из скрытого main_menu: свой GUID сохранён
и очищен, ограничение инструмента. Attempt2 сохраняет оригинальные Update и
main_menu, и login dialog;7живых callbacks после отказа, valid native login961
в том же процессе -> НОВОЕ реальное падение при main_menu off из Update.
Minidump0xc0000005/address14032c89c; exact a428 PDB:
CDialogHolder::OnFrame UIDialogHolder.cpp256. CleanInternals очищает render
vector, пока OnFrame держит итератор. Production asynchronous EnterWorld
также закрывает меню из Update. attempt2-qualification.json сохраняет
провал полного retry и hashes/logs/dump; ранний menu PASS его не заменяет.

Source e609538ddc5f197a959b273bd9375d624d928f06 исправляет итерацию индексом
с повторной проверкой size, без references через callback. Обычный порядок/
число callbacks сохраняются; CleanInternals очищает и deferred закрытые окна.
Actual OnFrame/CleanInternals/AddDialogToRender fixture:256legacy traces,
clear+delete из callback, deferred/deduplicated add, clear+new add, disabled skip.
Foundation37756749563 SUCCESS Linux ASan/UBSan/MSVC. DX1137756749573 строится:
дождись результата, проверь пакет. Не отменяй source push во время сборки.
Свежий input-recovery-e609538dd/run.ps1 подготовлен без бинарников; appdata
только user.ltx, owner credentials нет. Установи validated e609 пакет с
installed-from/hashes, повтори unknown960 -> live menu -> valid961 -> actor
ready+30сек в ТОМ ЖЕ обычном клиенте, zero actual fatal/Lua.
Сервер использует исходный сохранённый приватный
world selftest_destructibles_correlated; не удаляй/не пересеивай его.
Приватный подготовщик `_build/live/prepare-input-recovery.py` нельзя запускать
повторно поверх созданной папки; он намеренно отказывает. Таймер меню уже
исправлен по реальному binding: device():time_continual(), а не property.

GHA downloader с проверками:
`_build/live/quick-transitions/fetch-artifact.py RUN FULL_SHA CACHE_NAME API_IP`.
Кэш только `_build/gha`. Последний рабочий API IP140.82.121.5, локальный DNS
иногда выдавал нерабочий188.68.214.139; использовали временный curl --resolve
со строгим TLS, не меняли системный DNS/hosts. Не печатай токены или подписанные
artifact URLs; GH токен уже настроен и передаётся только в stdin/памяти.
Git remote gostn1ght, pull --rebase перед push, без reset/stash/add -A.

Основная установленная игра НЕ обновлялась. Все88 primary exe/config/account/
character/world fingerprints совпадают с прежним baseline. Четыре основных
exe gamma-runtime и LostZone-3D-Hideout всё ещё имеют SHA256
FE829FF44D4A0D4CF2C122A0EB6EDF243B8FCB7D3ABC3872A4C949D553B8AC88.
Не трогай основные миры/аккаунты, не стирай данные ради тестов. Не перезаписывай
baseline fingerprints. Локальные источники и acceptance находятся в _build/live;
их журналы/миры сохраняются, включая неудачные попытки. Проверку fingerprints
можно повторить `_build/live/fingerprint-primary-health.py after`.
Для promotion нужны принятый обычный вход/возврат, backup и точная версия;
не продвигай новый пакет только из-за bot PASS.

L30 уже ЗАКРЫТ для исходного INTACT/DAMAGED/DESTROYED (doc67): GHA4b74 native
проверка154 физических объектов,3 штатных повреждаемых модели glass/wood/metal,
151 нетронутый объект,2 рестарта с явными checkpoint. Health0.6 сохраняется
точным binary32, следующий0.7 уничтожает, удалённые не возвращаются.8 реально
отделившихся частей бутылки сохраняют ID/модели/состояния/позы (max2.3мм).
До этого CBreakable и actual PHS тоже проверены. Обычные графические клиенты
Actor20123/20239 дополнительно подтвердили15505 intact -> повреждение+save ->
тот же мир после restart,3f19999a -> следующий удар -> объект отсутствует
у клиента. graphic-peer-acceptance.json и4pre-stop journals запечатаны.
Это trusted server hits, НЕ human weapon RPC, не screenshot, не max-view64,
не velocities или chunk hydration. В GUI есть MCM20s hang diagnostics и
старые NPC loadout warnings; не называй полный GAMMA startup чистым.

Приватные ранние GUI ошибки не замалчивать: длинный путь дал graphics invalid
parameter; причинная связь с длиной не доказана. Quoted CLI start отклоняется
guard; unquoted client-only start разрешён. nbot_960 был ошибочным тестовым
аккаунтом (боты начинают с requested index+1); сервер имеет nbot_961. Затем
тестовый OBS Lua не скомпилировался из-за backslashes; исправленный повтор
syntax-check перед запуском прошёл. Не используй старые результаты как PASS.
Player console отвергает screenshot; запрос команды не означает снимок.

Строгий PS result gate уже закоммичен и pushed593c1e3ef:
scripts/netcoop-selftest-results.ps1 ловит настоящую строку UnhandledFilter
`at address 0x...`, даже если процесс остаётся с crash dialog. Actual PS fixture
scripts/check-netcoop-load-harness.ps1 PASS локально и отличает обычные hitch/
profile/debug addresses от исключения. Foundation37753870928 и
DX1137753870992 SUCCESS. Все свои процессы остановлены. Проверь git status перед commit:
не добавляй чужие/untracked файлы. Эта правка не меняет gameplay/native source.

После приёмки input recovery обнови doc45/68 и этот промпт, останови только
свои процессы по проверенному exe path, убедись, что shared server debug
channel пуст. Не перезаписывай чужую debug-команду. Новые native команды
должны иметь GUID correlation; старый метод delimiter по длине журнала давал
ложный ответ на больших каталогах. Обычные player/GUI acceptance не заменяй
headless fixtures. Продолжай другие пункты188, не ограничивайся отчётом о
готовности. Следующие более простые кандидаты — существующие GAMMA loadout
ошибки и реальная интеграция уже написанных adapters; точно проверь первопричину,
не подавляй diagnostics и не режь ИИ/население. Сложные chunks/64/512 остаются
самостоятельными задачами. В конце дай владельцу короткий честный итог с
доказанными результатами и оставшейся работой.
