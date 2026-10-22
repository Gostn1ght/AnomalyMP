# Single-player `Actor()` in monster code on the dedicated server (2026-10-20)

## Found

The Marsh server (native 486fbbfa9, release 2026.10.19.1) crashed 3 minutes
after start on the viewtest stand:
`CBaseMonster::set_state_sound`, `base_monster.cpp:619`, access violation
reading 0xB0 — `Actor()` was null (a dog in its rest state played the idle
sound and measured the distance to "the" actor). Dump:
`J:\LostZone_Work\_work\srvtest\appdata\server\logs\xray_view36_k00_marsh_20261019_192305_serverauthority_10-19-26_19-26-22.mdmp`,
PDB `J:\LostZone_Work\_work\pdb_486fbbfa9`.

Fixed in b3e3c5339: no Actor means the distant idle sound. Not built or
released yet (next patch 000037).

## The same pattern elsewhere (open)

GAMMA's monster code assumes one local player. On a dedicated server
`Actor()` is either null (crash) or the server's anchor actor (the monster
then acts on a non-player — the AI looks dumb). Each site must take the
nearest player / the current enemy instead, or skip when there is none:

| File | Lines | Use |
| --- | --- | --- |
| ai/Monsters/controller/controller.cpp | 836 | psy aim direction |
| ai/Monsters/controller/controller_psy_hit.cpp | 68, 87, 218, 309 | psy hit distance and heading |
| ai/Monsters/monster_aura.cpp | 56, 171 | aura distance (effect strength) |
| ai/Monsters/poltergeist/poltergeist.cpp | 195, 334 | actor position, 85 m check |
| ai/Monsters/poltergeist/poltergeist_telekinesis.cpp | 56, 232, 238, 240, 249 | object search and throw at the actor |
| ai/Monsters/bloodsucker/bloodsucker_vampire_execute_inline.h | 222 | commented out |
| ai/Monsters/controller/controller.cpp | 818 | commented out |

Also check `Actor()` without `->Position()` in the same folders (state
managers, `CMonsterSquad`, sound managers) before closing this.

Rule (memory "no dumbing AI"): a fix must aim at real players, never just
silence the behaviour.

## Root cause of the null (2026-10-22)

`g_actor` (what `Actor()` returns) is set by every local `ASPLAYER` actor
spawn; on the server `CActor::net_Spawn` forces `LOCAL`. When the actor that
set it is destroyed (a player leaves or dies), `net_Destroy` set it to null
while the ALife anchor (id 0) and other players remained. c99f4778d: on a
dedicated server it goes back to the anchor, as before any player spawned,
and the log names every change (`[Lost Zone] global actor ...`).

A player's local server (release 2fb19d4b5) went silent in a fight with a
mutant on 2026-10-21; the client left after 15 s without data. The server
log is still to get; this null is the likely cause.

Still open: the special attacks above test `enemy == Actor()`, so against
real players they never fire (vampire, burer telekinesis/stamina, controller
psy, poltergeist). Each needs the enemy actor for the gameplay part and an
event to the player's client for the camera/postprocess part.

## Plan for the special attacks against players

Damage is the server's (netcoop_events.inc: a client never sends GE_HIT
except its own fall), so each attack splits in two:

1. Gameplay on the server, against the attacking monster's enemy when it is
   a player's server copy (`netcoop::server_player_copy`), not `Actor()`:
   - burer: stamina hit and weapon drop (burer.cpp 247-283, 544);
   - controller: stamina hit (controller.cpp 752-755), psy aim (836);
   - bloodsucker vampire: hold, damage, release (vampire_execute_inline.h);
   - poltergeist telekinesis: object search and throw at the player
     (poltergeist_telekinesis.cpp);
   - psy dog / aura strength by the player's distance (monster_aura.cpp).
2. The player's screen on that player's client: a new netcoop event
   (monster id, effect kind, parameters) to the target's client, which runs
   the camera/postprocess effector on its local actor (the code that now
   calls `Actor()->Cameras()` on the server).

Stamina is the owner's (sprint is simulated on the client), so the stamina
hit goes in the same event; health damage stays the server's GE_HIT.
Needs a two-player test for each monster.
