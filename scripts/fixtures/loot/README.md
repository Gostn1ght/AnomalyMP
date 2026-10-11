# GAMMA initial loot fixture

`create_item_list.lua` is the unmodified function from the installed
`gamma-runtime/gamedata/scripts/death_manager.script`, with LF line endings.
SHA256: `51f3de05b1442b87c720516f05e8f691d69c1616748a4f43551fa367f12e7c1f`.

`check-netcoop-loot-policy.py` executes it with its actual cache upvalue names
and controlled raw INI rows. It checks frozen economy, canonical ordering,
GAMMA exclusions, stale/zero cached chances, shared shuffle counters, and
restoration after a generator exception. This supplements the actual server
build_npc_inventory checks; it does not launch a game or ALife process.
