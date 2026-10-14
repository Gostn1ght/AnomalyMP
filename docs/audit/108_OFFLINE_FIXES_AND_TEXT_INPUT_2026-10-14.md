# Offline fixes and common text input, 2026-10-14

Owner now requests checks without running the game. No game/client/location-server launches are permitted for the current verification pass. Distribution HTTP service is independent and remains available.

## New report

All text fields sometimes insert multiple characters for one press. Common DirectInput/editor path now discards duplicate down/up states, rejects invalid key indices, binds repeat to the last pressed key, does not arm repeat while idle, imposes a 400 ms minimum initial delay and a 50 ms minimum repeat interval. Standard con_sensitive 0.15 is present in both owner and QA settings; this is not evidence that low sensitivity caused the owner's report. Native regression exercises the real input/editor methods in GitHub Actions, including duplicate events, real separate taps, brief holding at all supported sensitivity extremes, prolonged holding, release, focus changes, Ctrl+A/V and CP1251 clipboard. Owner reproduction/graphical acceptance remains pending.

## Implemented in this batch

- Player map presentation: only self and mutual PDA friends on the same location; NPC/quest markers retained. Permission is bound to a spawned actor, forgotten on destruction and reset on disconnect. No claim of hiding combat replication data.
- Late trader profile: rebuild both actual GAMMA inventories after the asynchronous profile arrives, retaining selected deal items without duplication. Does not certify every trader or restore quest creation.
- Obtainable binocular uses the original two-hand animation family 13 rather than its conflicting one-hand/rifle overrides. The required motions exist in installed merged OMF. Visual alignment remains unverified.
- New Way PDA atlas, descriptor and seven layouts imported from the owner's local source. Shared frame/button/input art and tab positioning adapted; duplicate title hidden, photo opens within gallery/PDA, camera uses the source viewfinder art. Full photo hides background interactive controls. Existing group/payment/task dialogs and note editing are adapted Lost Zone functionality, not a byte-for-byte import of all New Way scripts.

Local Lua trade/PDA/photo/voice/animation checks and atlas/XML/native-binding validation pass. Native map and input checks and engine compilation run only in GitHub Actions. New DLL/EXE and patch distribution must wait for green native CI; next free resource patch is 000017.

## Earlier graphical QA interruption

Malwarebytes explicitly killed the owner client on 2026-10-14 17:21:20 and quarantined/deleted its executable at 17:22:23. This is recorded in the local MBAMService log; it is not evidence of a new native engine crash. No security settings were changed, and no client executable was restored or relocated to bypass quarantine. The QA location server was subsequently stopped cleanly. Temporary client QA bridge was removed. Future game verification requires the owner to resolve the quarantine first.

## Still open

Master M0 separate console/EXE is complete and verified; M1 native player-save contract/import and M2 primary master write/read/fencing remain open. M3 actual GAMMA quests/trader integration and reward-once across locations remain open. Inventory capacity must consistently account for armor, backpack, carry weight and item dimensions in live, offline/storage and trade paths and show used/available beside weight. Friend-host full weapon/pickup behavior, other vehicle classes, actual cross-map transitions, grip alignment and permanent freeze reproduction remain open until appropriate acceptance checks are available.
