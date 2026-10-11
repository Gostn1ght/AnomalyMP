function create_item_list(npc, npc_comm, npc_rank, is_private, to_save)
	--printf("-create_item_list | id: %s - comm: %s - rank: %s - is private: %s - to save: %s", npc:id(), npc_comm, npc_rank, is_private, to_save)
	
	if (not enble_trade_items) and to_save then
		return
	end
	
	local spawn_section
	if is_private then
		local sect = npc_comm .. "_private_" .. npc_rank
		if item_by_community[sect] then
			spawn_section = sect
		elseif item_by_community[character_community(npc) .. "_private"] then
			spawn_section = character_community(npc) .. "_private"
		end
	else
		local sect = npc_comm .. "_" .. npc_rank
		if item_by_community[sect] then
			spawn_section = sect
		elseif item_by_community[character_community(npc)] then
			spawn_section = character_community(npc)
		end
	end
	
	-- Spawn items
	flags.upgrade = false
	flags.eatable = false
	if spawn_section then
		for i=1,#item_by_community[spawn_section] do
			local sec = item_by_community[spawn_section][i].sec
			local v = item_by_community[spawn_section][i].cha
			if (v > 0 and item_count[sec] and (not IsItem("ammo",sec)) and (not IsItem("grenade_ammo",sec))) then
				local number = math.random(item_count[sec][1], item_count[sec][2])
				create_item(npc, sec, number, v, to_save)
			end
		end
		
		-- shuffle
		if (not shuffle_cnt[spawn_section]) then
			shuffle_cnt[spawn_section] = 0
		end
		shuffle_cnt[spawn_section] = shuffle_cnt[spawn_section] + 1
		if (shuffle_cnt[spawn_section] > shuffle_max) then
			shuffle_table(item_by_community[spawn_section])
		end
	else
		printdbg("! death_manager | no item spawn list for npc with community (%s) rank (%s)", npc_comm, npc_rank)
	end
end

