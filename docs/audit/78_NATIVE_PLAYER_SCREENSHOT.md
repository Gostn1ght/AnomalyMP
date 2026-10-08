# 78. Native local screenshot permission for ordinary players

2026-10-08, Codex. Scoped command-permission fix accepted in a new GHA engine.
No new188 row; current audit27/33/69/59,161 unclosed. Primary EXEs not promoted.

The player-console restriction also rejected ordinary local `screenshot`
and `r_screenshot_mode`, blocking client-side frame captures and the saved
format setting. Add only those two exact names to player_internal_command.
Full keyboard-console/role gates remain; gameplay, server and debugger
commands remain denied. `power_loss_bias` controls EntityCondition/stamina
and remains denied; it is not a rendering setting.

Actual classifier/current-vs-previous differential fixture passes747 cases
on GCC ASan/UBSan and MSVC. Only those two command results change. Explicit
god/noclip/gravity/time/server/debug/seed-all/screenshot-all negatives,
client-only start parsing and wireframe restriction are retained.
Foundation37788240462 SUCCESS; DX1137788240522 full build/package SUCCESS.

Qualified source `d3323e2fe8999890fa51818d73ec4141ae65fb5c`:

- Artifact11556018007; ZIP SHA256
  `a537c48ec04e7ba272805ebfd6272a4c9d0bdb339f9de22f32ea31d2747d13ff`.
- Both EXEs SHA256
  `04A764441C50AF214C45913876232D29304AFACA7FB1B86ECFE667FDA80ECD96`.

Private native probe restores the SAME correlated world, logs ordinary
account961 with explicit `(player)` role, Actor20569 and opened inventory
with15 retained native stat groups. Actual registered `g_god on` request
receives the unchanged administrator rejection. PNG format selection and
local screenshot request receive no administrator rejection. A real
944x501 PNG is saved in the fresh PRIVATE screenshot directory; signature,
dimensions, SHA and nonconstant pixels verified. The ordinary client stays
admitted another20s. No fatal/exception, SCRIPT ERROR, failed handler,
caught probe or loadout error in sealed pre-stop journals.

`view_image` inspection shows GAMMA loading-screen artwork/progress in the
saved pixels, NOT the inventory or a rendered world scene. This qualifies
player local capture/file output and god-command denial. Inventory pixel
layout, completed first3D frame, window-focus/Alt-Tab symptom, human Firebase
flow and64/max-view smoothness are NOT accepted from this image. The hidden/
background probe may retain the loading backbuffer; do not invent a cause
or report an inventory screenshot merely from IsShown=true.

SM_NORMAL uses the engine's dated screenshot filename and ignores the
optional supplied name. Qualification uses the exactly-one real PNG in the
new private root, explicit source/role/request nonce and sealed logs; no
old file or request marker substitutes for a saved image.

Proof `_build/live/console-capture-d332/qualified-acceptance.json`, sealed
client/server logs, `appdata/screenshots/ss_nbot_961_10-08-26_17-23-03_(l01_escape).png`,
and actual classifier fixture job logs113348466110/113348466369.
Nonce `CONCAP_42f518c531464848acfaba49acaccc81`.

All test processes stopped; shared debug empty; all88 protected primary
EXE/FS-alias/account/character/world fingerprints unchanged. No primary
C++ rollout. Current installed delta remains14 sound assets,20 targeted
loadout LTX and four scoped client-script files from docs73/74/77.
Other native asset/MCM warnings remain unresolved; no full clean-startup claim.
