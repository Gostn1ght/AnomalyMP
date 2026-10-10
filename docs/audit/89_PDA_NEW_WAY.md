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
