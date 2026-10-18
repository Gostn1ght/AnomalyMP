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

## Delivered 2026-10-18

- Native commit `544aed7409ea26e0ae5be3e3b41ebb10de49f02b`, successful
  [DX11 CI run 39073736637](https://github.com/Gostn1ght/AnomalyMP/actions/runs/39073736637).
  Client/server executable SHA256:
  `c0d6420945d3f0be0db664a888204bf2696500adf11139308b66f6dd7d2c8aa1`.
- Resource patch `000028`, one client script and one server script, from
  `1688c170009051206bb030526367768dc1988782`. The final native commit has
  identical overlays; the subsequent change fixes the CRT comparison name
  and updates hoster instructions.
- Launcher client `2026.10.18.2`: 6874 public files, signed release/manifest
  verified, required updated client files reconstructed from compressed
  chunks and compared byte for byte. Manifest BLAKE3:
  `b193ba78e74b046d091f08c15e4a6f7d38c45b10ad81e708b77230f19f051e5f`.
- Updated overlay folder `J:\LostZone_Work\Lost Zone Server`; ZIP
  `J:\LostZone_Work\Lost Zone Server.zip`, 272220025 bytes, 6897 entries.
  Every source and decompressed ZIP entry matches the public manifest.
  ZIP SHA256: `f13ad36ade2669698067963716ca1d9f5f7bfaa257a65513636bf291b471ce7a`.
- Existing standalone distribution server restarted with its existing
  identity; P2P online confirmed. HTTP mirror remains disabled by its
  existing configuration. No game, location server or master started.
- Publication input is the isolated public staging folder
  `J:\LostZone_Work\_work\launcher_client_000028`. The owner's game binaries
  were retained; update the installed game through the launcher before
  testing this version. Accounts/world/private runtime files were not
  included in the release or changed by installation.
- Install/publication/ZIP receipts and the running distribution logs are in
  `J:\LostZone_Work\_work\patch_000028`. The installation receipt records the
  preserved previous files. The previous server ZIP is retained in the
  corresponding `_work\server_zip_000028_*` staging directory.

The hoster unpacks the ZIP over the updated game while their servers are
stopped. In-game acceptance remains with the owner and hoster, as requested.
