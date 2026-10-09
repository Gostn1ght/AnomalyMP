function has_parts_fieldstrip(wpn, bag, mode)
	local allowedMode = {
		["inventory"] = true,
		["loot"] = true,
	}
	local allowedBag = {
		["actor_equ"] = true,
		["actor_belt"] = true,
		["actor_bag"] = true,
		["npc_bag"] = true,
	}

	--SERIOUS: Prevents field stripping in trade windows. (Black Market and some gun mods include weapons on traders)
	if not allowedBag[bag] or not allowedMode[mode] then return false end

	if not has_parts(wpn) then return false end
		local parts = item_parts.get_parts_con(wpn, nil, true)
		local has_parts = false
		for k,v in spairs(parts, sort_parts) do
			if v > 0 and is_part(k) and not arti_jamming.is_barrel(k) then has_parts = true end
	end
	return has_parts
end

