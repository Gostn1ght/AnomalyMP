# GAMMA trade fixture

`get_item_trade_status.lua` is the function from the installed
`gamma-runtime/gamedata/scripts/utils_item.script`, with LF line endings and
trailing whitespace removed; its code and behavior are unchanged.
`check-netcoop-trade.py` executes it with the actual server entry point:
condition threshold, quest/nontrade items, buy/sell profile lists, ammo and
multiuse exceptions, hidden partial stock, and absent/malformed profiles.
