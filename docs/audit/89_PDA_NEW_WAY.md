# 89. PDA like New Way (owner 2026-10-10)

Owner sent New Way screenshots and patch notes: "the same PDA". Reference
files (owner: NW authorised reversing): Downloads\Kall\NW_unpacked\configs\ui
pda_16.xml, pda_global_chat.xml, pda_private_chat.xml, pda_extra.xml,
pda_notes.xml. NW does tabs and chat natively in its engine; here they are
Lua tabs (pda_dynamic_tabs, engine tab scrolling already in CUIPdaWnd) over
the netcoop command/channel transport and the cluster shared store.

## Requirements (from the owner's text and screenshots)

1. Tabs strip with scrolling, 4 visible: Карта местности, Общий канал, Чаты,
   Контакты, Галерея, Фото, Диктофон, Заметки. Cut FM radio "и т.д.".
2. PDA name + 6-digit UID per character. No public online list: online
   status only after both added each other's UID. Strangers: UID only
   (general channel, chats); contacts: avatar + name, status, send points/
   tasks without typing a UID.
3. History of general and private channels survives relog/restart; private
   messages to offline players; unread marks in chats and contacts.
4. Group chats from contacts: name + icon, any member can delete.
5. Chat actions: Перевод (money to the contact), Удалить чат, Снимок
   (photo), Точка (map point, "Отметить на карте"), Запись (voice), typing
   indicator; general channel: "Анонимно", keyboard layout hint.
6. Photo mode (RMB zoom, LMB shot, E/ESC exit), gallery with date, place,
   size, delete; send photos to chats and groups.
7. Dictaphone: up to 10 min, records what the player hears (players,
   mutants, anomalies, weapons) and his voice; send records; seek bar.
8. Bug: from the side the PDA *screen image* (not the PDA) is shifted down
   and partly visible; must match the owner's own screen.

## Full checklist (owner's text + all 20 screenshots, re-read 2026-10-10)

Owner, later: "Пока вырезать только фм и добавить новые" - every GAMMA tab
stays except FM radio; the New Way tabs are added. Marks: [x] code written
(not verified in game), [ ] not done.

Tabs and frame
- [x] all GAMMA tabs kept, only FM radio removed; NW tabs added; tab strip
      scrolls, 4 visible
- [x] "Карта местности" caption for the map tab
- [ ] map tab: "Список заданий" button (task list over the map)
- [x] clock (game time) at the right of the tab strip
- [x] footer on every NW tab: "<PDA name> - UID nnnnnn"
- [x] profile card (PDA name, UID, faction, money "RU", avatar) like the
      NW header (top of Contacts)
- [ ] PDA held landscape in both hands, in first and third person
- [ ] other player's PDA: the screen image is shifted down (needs a screenshot)

Contacts
- [x] own name + UID line, UID field, Добавить / Открыть / Удалить
- [x] list: avatar, name, UID, "в сети" only for mutual contacts
- [x] empty-list hint "Список пуст. Спросите у сталкера его UID..."
- [x] unread count on a contact
- [ ] unread mark on the Contacts tab caption
- [x] send a map point to a contact without typing the UID ("Отправить точку")
- [ ] send a task to a contact

General channel
- [x] history kept on the server, anonymous checkbox, Отправить
- [x] sender: name for contacts, "UID nnnnnn" for strangers, avatar
- [x] date like "16:24, Сентябрь 11, 2011" (game date)
- [x] "Раскладка: EN/RU" keyboard layout indicator

Chats
- [x] list: avatar, name, last message, time, unread badge; total unread
- [x] Новая группа dialog: name, member checkboxes, Создать / Отмена
- [x] group icon picker ("Значок")
- [x] header: avatar, name, UID, status; groups "Участников: N - в сети: M"
- [x] group "Состав" (member list)
- [x] Удалить чат (group: for everyone)
- [x] Перевод - money to the contact (server, offline credit)
- [x] typing indicator "<name> печатает сообщение..."
- [x] text messages; own on the right, others left with avatar; sender name
      in groups; date "12.09 15:16"
- [x] point message: "Точка", description, "Отметить на карте"
- [ ] point: send button flow ("Точка" picks a map spot / current position)
- [ ] photo message (image inline) - needs photo capture
- [x] voice message ("Запись 0:13", play/pause, seek bar, time)

Photo mode ("Фото" tab / "Режим съёмки")
- [ ] camera overlay: "ФОТОКАМЕРА", corner brackets, "Снимков: N - 1x"
- [ ] RMB zoom, LMB shot, E / ESC exit
- [ ] frame capture (engine), stored per character

Gallery
- [ ] thumbnails with date/time, selected preview: date, place, size
- [ ] Удалить снимок, Режим съёмки, "Снимков: N"
- [ ] send a photo to a chat or group

Dictaphone
- [x] description, "Записей: N", Начать запись / Остановить
- [x] up to 10 minutes; recording goes on with the PDA put away
- [x] records the player's voice and what he hears: players talking nearby
      (where they stood), walkie-talkie voices and receivers' speakers (radio
      voice), mutants, anomalies, weapons (world sounds replayed around the
      listener)
- [x] list of records, play/pause, seek bar "0:00 / 0:00", Удалить
- [x] send a record to a chat or group

Notes
- [x] notes tab (NW pda_notes.xml): list, create, edit, delete

Voice messages: up to 2 minutes from "Запись" in a chat; the record goes to
the server in 3800-character parts, stored in the cluster store
(pda_audio), fetched by chat members only. Dictaphone records: up to 10
minutes, kept in the PDA (a file per UID in appdata), one can be sent to the
chat open in "Чаты". Engine: netcoop_voice_record.inc (recorder, player,
base64), xrSound ISoundTap (world sounds), ISoundVoice::SetRecord.
Fixtures: check-netcoop-pdanet.py, check-netcoop-pdanet-voice.py.

## Stages

- P1 server core (77e1db10d): UID, contacts (mutual status), general
  channel with anonymous posts, private/group chats with history (cluster
  store, CAS), offline delivery and cross-server polling, unread, group
  delete, typing, points validated. Fixture check-netcoop-pdanet.py.
- P2 client tabs: general channel, chats (list + conversation + new group
  dialog), contacts (UID field, add/open/delete, status); "Карта местности"
  caption; FM radio removed. Points: "Отметить на карте" adds a personal pin
  (netcoop_pda pins).
- P3 money transfer between contacts (server moves money, offline credit
  applied on the recipient's next login), with a confirmation.
- P4 photos: engine capture of the frame (downscaled JPEG/RTC), stored per
  character on the server, gallery tab, photo messages with a size limit.
  Needs engine work (capture + runtime texture from bytes) in GHA.
- P5 dictaphone: there is no microphone path in the engine; recording "what
  the player hears" can be done as a log of the sounds played around the
  listener (sound, position relative to the listener, time) replayed later.
  Voice needs voice chat first. Needs design with the owner.
- P6 remote screen image (point 8): needs one screenshot of the bug. Code
  findings: the observer quad (scripts/generate-pda-screen.py) is mirrored
  along the long side relative to its own atlas comment, and sits 1.5 mm
  under the housing's glass layer (y 0.0187 vs 0.0202); the capture crop
  (cursor box) is within 1 % of the HUD screen's UV area (u 0.111-0.889,
  v 0.047-0.963), so the frame itself is not the shift.

Nothing here is verified in game.
