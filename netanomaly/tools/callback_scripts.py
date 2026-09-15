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
