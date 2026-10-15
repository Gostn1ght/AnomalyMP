# Death callbacks without a local actor

Evidence: retained actual server log `J:\LostZone_Work\_work\owner_remote_bugs_20261013\server_ui_000016_before_stop.log`, lines7043–7065. This is not a new game launch. It contains agdd_voiced_actor:600 and grok_loot_claim:14 indexing nil db.actor, plus CharacterCommunity available only for InventoryOwner from netcoop_world_events:95/103.

The world event journal now calls the real exported is_inventory_owner binding before character_community. A CScriptGameObject exposes character_community even for monsters; testing the method's presence or wrapping it in pcall does not stop its native error log. NPC/player communities and player-login killer names remain intact, monster victims/killers have no character community.

Minimal generated GAMMA overlays guard the voiced-actor monster-death callback before touching an absent/dead actor. Loot claims ignore deaths without victim/killer and compare the local player's ID only when db.actor exists; actor-less NPC fights still create the original NPC claim. This does not replace multiplayer quest attribution or synchronize claims between locations.

Actual shipped Lua callback code is exercised for client/server overlays, environmental deaths, missing local actor, NPC claims, local-player kills and disabled voice. Mutant killer/victim bindings intentionally throw if the forbidden community method is called. World-event regression and GAMMA syntax/CRLF/console fixtures pass locally. No game or location process was started. These resource changes require a new patch number after000017; they are not yet installed or certified in a running game.
