function discover_spots()
	ResetTimeEvent(0,"ScanForSpots",3)
	
	local actor = db.actor
	for k,v in pairs(primary_objects_tbl) do
		if actor:dont_has_info(v.target) then
			local obj_id = get_story_object_id(v.target)
			if obj_id and db.storage[obj_id] and db.storage[obj_id].object then
				local n_dist = distance_tbl[level.name()] or 40
				if (db.storage[obj_id].object:position():distance_to(actor:position()) <= n_dist) then
					give_info(v.target)
					game_statistics.increment_rank(10)
					actor_menu.set_fade_msg( game.translate_string(v.hint), 5, nil, "device\\pda\\spot_discovered" )
					--news_manager.send_tip(actor,game.translate_string(v.hint),0,"tourist",5000,nil,game.translate_string("st_revealled_area"))
					fill_primary_objects()
				end	
			end
		end
	end
end