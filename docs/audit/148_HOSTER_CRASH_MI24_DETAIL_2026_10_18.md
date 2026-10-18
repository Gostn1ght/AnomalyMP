# Hoster Cordon crash, Mi-24 detail, F7 buttons - patch 000034

- Hoster dump `xray_srv_l01_escape_serverauthority_10-18-26_21-08-52.mdmp`:
  PE timestamp matches patch33 native 2fb19d4b5 (resolve with that PDB, not
  an earlier one). Access violation in `CUIGameCustom::AddCustomStatic`
  (UIGameCustom.cpp:121): a server script message for a player read the HUD
  message layouts (`MsgConfig`) a dedicated server never loads. Fix: without
  them one plain, never drawn static per id. The players' client logs show
  only the disconnect at that moment.
- F7: GAMMA's God mode (console g_god) and Start Emission (surge start) are
  routed to the server commands `god` / `emission start`; its client-only
  faction changer is removed (Lost Zone faction/pardon buttons remain).
  Unlimited ammo is still a client console command this build lacks: open.
- Mi-24: body decimation 0.2 -> 0.6 (86k triangles), rotors 0.8; 4096 albedo;
  X-Ray bump pairs from the source normal maps (R gloss, G/B/A = normal z/y/x,
  neutral 1x1 bump#) and .thm descriptors (Anomaly reads bumps only from .thm).
  Bind poses identical to the shipped rig; seats unchanged.

## Delivered 2026.10.18.7 / patch 000034

- Native 190cf6a9a, [DX11 CI 39153392128](https://github.com/Gostn1ght/AnomalyMP/actions/runs/39153392128),
  exe SHA256 b4dd49d0...b253. Resources 9c7f17507 (src identical to native).
- Launcher 2026.10.18.7 published through the running distribution service
  (publish_fixes_000034.py; the offline publisher refuses a running service).
  6879 files, manifests/2026.10.18.7-0895b29c.bin, signature verified.
- Hoster folder and ZIP updated: 445029436 bytes, 6907 entries, SHA256
  50b7234d...fae1 (larger: the Mi-24 assets are in both patch archives).
- Owner client was running: not installed locally (launcher update).
