# Account, dialogue trade and live admin fixes — 2026-10-18

Owner authorizes the matching server overlay/ZIP and launcher client update.
Do not start the game, locations or master: the owner and hoster test in game.

- A server-opened technician trade records the player/partner and permits
  bypassing only the meet trade flag. Profile, life, hostility, wounded state,
  distance, item policy, funds and ownership are still checked on purchase.
  Missing/failed Lua preparation cannot reuse an enabled trader flag.
- Online role messages register the debug/spawn callbacks immediately and
  once per session, even with a preexisting DEV_DEBUG flag. Demotion clears
  DEV_DEBUG immediately; the existing native handler also clears god mode.
- Remote dialogue supplies GAMMA's used_npc_id during task offer callbacks,
  restoring the previous speaker afterwards. Exception cleanup copies the
  session NPC before erasing the session and closes the failed conversation.
- Recover the Google UID erased by the 17.5 password migration only after
  verified Firebase identity AND proof of the remembered local password.
  Device identity alone cannot reset a password or link a Google identity.
  Persist the recovered UID only after device and ban checks; preserve the
  existing password hash/salt, role, money and character data. An already
  linked Google UID remains usable after a Google password reset.
  Recovery needs the old local credentials cached on that installation;
  missing proof fails closed and must be handled by the host administrator.

Validation: actual Lua trade/menu/role/speaker fixtures locally, native
admission/link parser and full DX11 compilation in GitHub Actions. Delivery
must pin that successful run and exact commit. Runtime acceptance of the
reported trade/task crash and hoster's login remains with owner testing.
