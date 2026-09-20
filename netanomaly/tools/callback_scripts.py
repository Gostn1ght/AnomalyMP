"""Adapt GAMMA callbacks to network loading, where a local actor may not exist."""


def patch_ledge(data):
    old = b'RegisterScriptCallback("on_loading_screen_key_prompt", actor_on_first_update)'
    new = b'RegisterScriptCallback("actor_on_first_update", actor_on_first_update)'
    if old not in data and data.count(new) == 1:
        return data
    if data.count(old) != 1:
        raise ValueError('Unexpected ledge grabbing callback registration')
    return data.replace(old, new)


def patch_ubgl(data):
    old = b'local obj = db.actor:active_item()'
    new = b'local obj = db.actor and db.actor:active_item()'
    if old not in data and data.count(new) == 2:
        return data
    if data.count(old) != 2 or data.count(b'if not obj then return end') != 2:
        raise ValueError('Unexpected UBGL deferred presentation callbacks')
    # A menu can close without starting a game. Finish this deferred cosmetic
    # callback if no actor/item exists; weapon animation callbacks refresh it later.
    return data.replace(old, new).replace(b'if not obj then return end', b'if not obj then return true end')


def patch_dynamic_anomalies(data):
    old = (b'if anomalies_near_actor_functions[section] or '
           b'(additional_articles_to_category.encyclopedia_anomalies[section] and not '
           b'opened_articles.encyclopedia_anomalies[additional_articles_to_category.encyclopedia_anomalies[section]]) then')
    new = b'if db.actor and (' + old[3:-5] + b') then'
    if old not in data and data.count(new) == 1:
        return data
    if data.count(old) != 1:
        raise ValueError('Unexpected dynamic anomaly actor proximity callback')
    # Keep the base binder and the following NPC branch running without a local
    # actor. Only the actor proximity effects and encyclopedia need db.actor.
    return data.replace(old, new)


def patch_combat_schemes(data):
    marker = b'-- GAMMA net: combat conditions also run before an enemy exists.'
    if marker in data:
        return data
    for name in (b'scheme_camper', b'scheme_cover'):
        anchor = b'function ' + name + b'(enemy,npc,actor)'
        if data.count(anchor) != 1:
            raise ValueError('Unexpected GAMMA combat scheme signature')
        data = data.replace(anchor, anchor + b'\n\tif not enemy or not npc or not db.storage[npc:id()] then return false end')
    # Classify the actual opponent, not the single-player db.actor singleton.
    replacements = (
        (b'(enemy_id == db.actor:id())', b'IsActor(enemy)', 2),
        (b'(enemy_id ~= nil and enemy_id == db.actor:id())', b'(enemy_id ~= nil and is_actor)', 2),
        (b'npc:see(db.actor)', b'npc:see(enemy)', 1),
        (b'if who:id() == AC_ID then', b'if who and IsActor(who) then', 1),
    )
    for old, new, count in replacements:
        if data.count(old) != count:
            raise ValueError('Unexpected GAMMA combat scheme body: ' + old.decode())
        data = data.replace(old, new)
    start = data.index(b'function pure_enemy_distance(npc, enemy)')
    end = data.index(b'function scheme_camper', start)
    helper = data[start:end].replace(b'local pos1 = npc:position()', b'if not enemy then return false end\n\t\tlocal pos1 = npc:position()')
    return marker + b'\n' + data[:start] + helper + data[end:]


def patch_meet(data):
    marker = b'-- GAMMA net: defer actor-dependent meet setup until an actor exists.'
    if marker in data:
        return data
    edits = (
        (b'function init_meet(npc, ini, section, st, scheme)', b'''function init_meet(npc, ini, section, st, scheme)
    if not db.actor then
        st.gamma_pending_meet = {ini = ini, section = section, scheme = scheme}
        st.meet_set = false
        return
    end
    if st.gamma_pending_meet then
        st.gamma_pending_meet = nil
        st.meet_section = nil
    end'''),
        (b'function evaluator_contact:evaluate()', b'''function evaluator_contact:evaluate()
    if not db.actor then return false end
    local pending = self.a.gamma_pending_meet
    if pending then
        init_meet(self.object, pending.ini, pending.section, self.a, pending.scheme)
    end'''),
        (b'function Cmeet_manager:update()', b'''function Cmeet_manager:update()
    if not db.actor or self.a.gamma_pending_meet then return end'''),
    )
    for old, new in edits:
        if data.count(old) != 1:
            raise ValueError('Unexpected GAMMA meet callback: ' + old.decode())
        data = data.replace(old, new)
    return marker + b'\n' + data


def patch_script_fixes_mp(data):
    marker = b'-- GAMMA net: actor item callbacks require a spawned actor.'
    if marker in data:
        return data
    condition = b'\tif flags.ret_value then'
    replacement = b'\tif flags.ret_value and db.actor then'
    for signature in (b'item_device.on_anomaly_touch = function(obj, flags)',
                      b'itms_manager.actor_on_item_before_use = function(obj, flags)'):
        if data.count(signature) != 1:
            raise ValueError('Unexpected actor item callback wrapper')
        start = data.index(signature)
        position = data.find(condition, start, start + 256)
        if position < 0:
            raise ValueError('Unexpected actor item callback condition')
        data = data[:position] + replacement + data[position + len(condition):]
    return marker + b'\n' + data


ORPHAN_SCRIPT_DEPENDENCIES = {
    'a_faction_prices.script': ('faction_stocks.script',),
    'mags_patches.script': ('magazine_binder.script', 'magazines.script', 'magazines_mcm.script'),
    'zz_ui_inventory_better_stats_bars.script': ('better_stats_bars_mcm.script',),
}


def prune_orphan_scripts(scripts):
    """Remove winning compatibility patches whose required mod was not materialized."""
    removed = []
    for leaf, dependencies in ORPHAN_SCRIPT_DEPENDENCIES.items():
        path = scripts / leaf
        if path.is_file() and any(not (scripts / dependency).is_file() for dependency in dependencies):
            path.unlink()
            removed.append(leaf)
    return removed


def patch_zoomcalc(data):
    marker = b'-- GAMMA net: replace invalid C comment delimiters.'
    if marker in data:
        return data
    if data.count(b'/*') != 1 or data.count(b'*/') != 1:
        raise ValueError('Unexpected zoom calculator comment syntax')
    return marker + b'\n' + data.replace(b'/*', b'--[[', 1).replace(b'*/', b']]', 1)
