"""Exercise actual server camp retaliation/protection policy in Lua 5.1."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root=Path(__file__).resolve().parents[1]
source=(root/'scripts/netcoop-overlay/server/netcoop_server_compat.script').read_text(encoding='cp1251')
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
now=0;story=false;range=4;section='sim_default_stalker';rule='{=npc_in_zone(esc_camp_safe_restr)} true'
function time_global() return now end
function get_object_story_id(id) return story end
function printf() end
local point={distance_to_sqr=function() return range*range end}
npc={id=function() return 27 end,alive=function() return true end,section=function() return section end,position=function() return point end}
attacker={id=function() return 91 end,alive=function() return true end,position=function() return point end}
level={object_by_id=function(id) return id==27 and npc or id==91 and attacker end}
db={storage={[27]={section_logic='logic',ini={r_string_ex=function() return rule end}}}}
stalker_generic={is_need_invulnerability=function() return true end,
update_invulnerability=function(n) invulnerable=stalker_generic.is_need_invulnerability(n) end}
xr_combat_ignore={is_enemy=function() return false end,ignore_enemy_by_overrides=function() return true end,npc_in_safe_zone=function() return true end}
''')
begin=source.index('local squad_attackers = {}')
end=source.index('\nfunction on_game_start()',begin)
lua.execute(source[begin:end]+r'''
install_squad_witnesses()
assert(stalker_generic.is_need_invulnerability(npc),'initial camp protection')
before_npc_hit(27,91)
assert(not invulnerable and xr_combat_ignore.is_enemy(npc,attacker),'attack interrupts camp safety')
assert(not xr_combat_ignore.ignore_enemy_by_overrides(npc,attacker) and not xr_combat_ignore.npc_in_safe_zone(npc))
story=true;before_npc_hit(27,91);assert(invulnerable,'explicit story protection retained')
story=false;rule='true';before_npc_hit(27,91);assert(invulnerable,'explicit immunity retained')
rule='{=npc_in_zone(esc_camp_safe_restr)} true';section='esc_trader';before_npc_hit(27,91);assert(invulnerable,'special NPC protection retained')
section='sim_default_stalker';range=80
assert(not xr_combat_ignore.is_enemy(npc,attacker),'no unlimited pursuit')
range=4;now=300001
assert(not xr_combat_ignore.is_enemy(npc,attacker),'witness memory expires')
assert(stalker_generic.is_need_invulnerability(npc),'expired combat restores normal camp policy')
''')
print('Actual server AI: immediate retaliation, generated camp protection, preserved story/explicit protection, range and memory expiry PASS')
