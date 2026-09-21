function evaluator_contact:evaluate()
	--utils_data.debug_write("eva_contact")
	if not (self.object:alive()) then
		return false
	end

	if self.a.meet_set ~= true then return false end

--	if self.a.meet_only_at_path == true and not db.storage[self.object:id()].move_mgr:arrived_to_first_waypoint() then
--		return false
--	end

	if db.actor then
		if not db.actor:alive() then
			return false
		end

		self.a.meet_manager:update()

		if (db.storage[self.object:id()].victim_surrender == AC_ID) then
			return true
		end

		if xr_wounded.is_wounded(self.object) then
			return false
		end

		if self.object:best_enemy() ~= nil then
			return false
		end

		local state = state_mgr.get_state(self.object)
		if (state == "search_corpse" or state == "pickup_crouch") then
			return false
		end

		if (self.object:has_info("npcx_is_companion") or not get_object_story_id(self.object:id())) and not (self.object:is_talking()) then
			if (self.a.gtfo == true) then
				return true
			end
			if (db.actor:position():distance_to_sqr(self.object:position()) < 1.5) and not (good_acts[utils_obj.get_current_action_id(self.object)]) then
				self.a.dtimer = not self.a.dtimer and time_global() + 4000 or self.a.dtimer
				if (time_global() > self.a.dtimer) then
					self.a.dtimer = nil
					self.a.gtfo = true
					return true
				end
			end
		end

		local squad = self.object and get_object_squad(self.object)
		local commander = squad and squad:commander_id() ~= self.object:id() and level.object_by_id(squad:commander_id())
		if (commander and state_mgr.get_state(commander) == "threat_na" and utils_obj.get_current_action_id(commander) == xr_actions_id.stohe_meet_base + 1) then
			if (self.object:see(db.actor) or db.actor:position():distance_to_sqr(self.object:position()) <= 225) then
				self.a.commander_threat = true
				return true
			end
		else
			self.a.commander_threat = nil
		end

		return self.a.meet_manager.current_distance ~= nil
	end
	return false
end

----------------------------------------------------------------------------------------------------------------------
--Actions
----------------------------------------------------------------------------------------------------------------------
--' Приглашение к тороговле

local default_meet = {} -- no sense to recreate for each npc

-- Функция чтения настроек. В нее передается секция, откуда их нужно читать.
function init_meet(npc, ini, section, st, scheme)
	--printf("MEET SECTION [%s][%s][%s]", tostring(st.meet_section), tostring(section), tostring(scheme))

	if (section == st.meet_section and section ~= "nil") then
		return
	end

	st.meet_section = section

	-- TODO: fix the fucked up relations
	local comm_actor = character_community(db.actor):sub(7)
	local comm_npc = character_community(npc)
	local relation_enemy_1 = game_relations.is_factions_enemies( comm_actor , comm_npc )
	local relation_enemy_2 = game_relations.get_npcs_relation(npc, db.actor) == game_object.enemy
	local is_enemy = (relation_enemy_1 or relation_enemy_2) and true or false

	if not (default_meet[is_enemy]) then
		default_meet[is_enemy] = {}
	end
	-------------------------------------
	--local relation = game_relations.get_npcs_relation(npc, db.actor)

	if (is_enemy) then
		default_meet[is_enemy].close_distance 		= "0"
		default_meet[is_enemy].close_anim 			= "nil"
		default_meet[is_enemy].close_snd_distance 	= "0"
		default_meet[is_enemy].close_snd_hello		= "nil"
		default_meet[is_enemy].close_snd_bye		= "nil"
		default_meet[is_enemy].close_victim		    = "nil"
		default_meet[is_enemy].far_distance		    = "0"
		default_meet[is_enemy].far_anim			    = "nil"
		default_meet[is_enemy].far_snd_distance	    = "0"
		default_meet[is_enemy].far_snd				= "nil"
		default_meet[is_enemy].far_victim			= "nil"
		default_meet[is_enemy].snd_on_use			= "nil"
		default_meet[is_enemy].use					= "false"
		default_meet[is_enemy].meet_dialog			= "nil"
		default_meet[is_enemy].abuse				= "false"
		default_meet[is_enemy].trade_enable		    = "false"
		default_meet[is_enemy].allow_break			= "true"
		default_meet[is_enemy].meet_on_talking		= "true"
		default_meet[is_enemy].use_text			    = "nil"
	else
		default_meet[is_enemy].close_distance 		= "{=is_wounded} 0, {!is_squad_commander} 0, {!after_first_meet !actor_friend !actor_is_safemode =actor_has_weapon} 3, 2"
		default_meet[is_enemy].close_anim 			= "{=is_wounded} nil, {!is_squad_commander} nil, {!actor_is_safemode =actor_has_weapon} nil, talk_default"
		default_meet[is_enemy].close_snd_distance 	= "{=is_wounded} 0, {!is_squad_commander} 0, 3"
		default_meet[is_enemy].close_snd_hello		= "{=is_wounded} nil, {!is_squad_commander} nil, {=actor_enemy} nil, {!after_first_meet !actor_friend !actor_is_safemode =actor_has_weapon} meet_stop, meet_hello"
		default_meet[is_enemy].close_snd_bye		= "nil"
		default_meet[is_enemy].close_victim		    = "{=is_wounded} nil, {!is_squad_commander} nil, actor"
		default_meet[is_enemy].far_distance		    = "{=is_wounded} 0, {!is_squad_commander} 0, {!after_first_meet !actor_friend !actor_is_safemode =actor_has_weapon} 5, 3"
		default_meet[is_enemy].far_anim			    = "{=is_wounded} nil, {!is_squad_commander} nil, {!after_first_meet !actor_friend !actor_is_safemode =actor_has_weapon} threat_na, nil"
		default_meet[is_enemy].far_snd_distance	    = "{=is_wounded} 0, {!is_squad_commander} 0, 5"
		default_meet[is_enemy].far_snd				= "{=is_wounded} nil, {!is_squad_commander} nil, {=actor_enemy} nil, {=is_story} nil, {!after_first_meet !actor_friend !actor_is_safemode =actor_has_weapon} meet_hide_weapon, meet_wait"
		default_meet[is_enemy].far_victim			= "{=is_wounded} nil, {!is_squad_commander} nil, actor"
		default_meet[is_enemy].snd_on_use			= "{=is_wounded} nil, {!is_squad_commander} meet_use_no_talk_leader, {=actor_enemy} nil, {=has_enemy} meet_use_no_fight, {!dist_to_actor_le(3)} nil"
		default_meet[is_enemy].use					= "{=is_wounded} false, {!is_squad_commander} false, {=actor_enemy} false, {=has_enemy} false, {=dist_to_actor_le(3)} true, false"
		default_meet[is_enemy].meet_dialog			= "nil"
		default_meet[is_enemy].abuse				= "{=has_enemy} false, true"
		default_meet[is_enemy].trade_enable		    = "true"
		default_meet[is_enemy].allow_break			= "true"
		default_meet[is_enemy].meet_on_talking		= "true"
		default_meet[is_enemy].use_text			    = "nil"
	end

	local def = default_meet[is_enemy]

	if tostring(section) == "no_meet" then
		st.close_distance 	= xr_logic.parse_condlist(npc, section, "close_distance", 		"0")
		st.close_anim 		= xr_logic.parse_condlist(npc, section, "close_anim", 			"nil")
		st.close_snd_distance=xr_logic.parse_condlist(npc, section, "close_distance", 		"0")
		st.close_snd_hello	= xr_logic.parse_condlist(npc, section, "close_snd_hello", 		"nil")
		st.close_snd_bye	= xr_logic.parse_condlist(npc, section, "close_snd_bye", 		"nil")
		st.close_victim		= xr_logic.parse_condlist(npc, section, "close_victim", 		"nil")

		st.far_distance		= xr_logic.parse_condlist(npc, section, "far_distance", 		"0")
		st.far_anim			= xr_logic.parse_condlist(npc, section, "far_anim", 			"nil")
		st.far_snd_distance	= xr_logic.parse_condlist(npc, section, "far_distance", 		"0")
		st.far_snd			= xr_logic.parse_condlist(npc, section, "far_snd", 				"nil")
		st.far_victim		= xr_logic.parse_condlist(npc, section, "far_victim", 			"nil")

		st.snd_on_use		= xr_logic.parse_condlist(npc, section, "snd_on_use", 			"nil")
		st.use				= xr_logic.parse_condlist(npc, section, "use", 					"false")
		st.meet_dialog		= xr_logic.parse_condlist(npc, section, "meet_dialog", 			"nil")
		st.abuse			= xr_logic.parse_condlist(npc, section, "abuse", 				"false")
		st.trade_enable		= xr_logic.parse_condlist(npc, section, "trade_enable", 		"true")
		st.allow_break		= xr_logic.parse_condlist(npc, section, "allow_break", 			"true")
		st.meet_on_talking	= xr_logic.parse_condlist(npc, section, "meet_on_talking",		"false")
		st.use_text			= xr_logic.parse_condlist(npc, section, "use_text", 			"nil")

		st.reset_distance	= 30
		st.meet_only_at_path = true
	else
		st.close_distance 	= ini:r_string_to_condlist(section,"close_distance",def.close_distance)
		st.close_anim 		= ini:r_string_to_condlist(section,"close_anim",def.close_anim)
		st.close_snd_distance=ini:r_string_to_condlist(section,"close_snd_distance",def.close_snd_distance)
		st.close_snd_hello	= ini:r_string_to_condlist(section,"close_snd_hello",def.close_snd_hello)
		st.close_snd_bye	= ini:r_string_to_condlist(section,"close_snd_bye",def.close_snd_bye)
		st.close_victim		= ini:r_string_to_condlist(section,"close_victim",def.close_victim)

		st.far_distance		= ini:r_string_to_condlist(section,"far_distance",def.far_distance)
		st.far_anim			= ini:r_string_to_condlist(section,"far_anim",def.far_anim)
		st.far_snd_distance	= ini:r_string_to_condlist(section,"far_snd_distance",def.far_snd_distance)
		st.far_snd			= ini:r_string_to_condlist(section,"far_snd",def.far_snd)
		st.far_victim		= ini:r_string_to_condlist(section,"far_victim",def.far_victim)

		st.snd_on_use		= ini:r_string_to_condlist(section,"snd_on_use",def.snd_on_use)
		st.use				= ini:r_string_to_condlist(section,"use",def.use)
		st.meet_dialog		= ini:r_string_to_condlist(section,"meet_dialog",def.meet_dialog)
		st.abuse			= ini:r_string_to_condlist(section,"abuse",def.abuse)
		st.trade_enable		= ini:r_string_to_condlist(section,"trade_enable",def.trade_enable)
		st.allow_break		= ini:r_string_to_condlist(section,"allow_break",def.allow_break)
		st.meet_on_talking	= ini:r_string_to_condlist(section,"meet_on_talking",def.meet_on_talking)
		st.use_text			= ini:r_string_to_condlist(section,"use_text",def.use_text)

		st.reset_distance	= 30
		st.meet_only_at_path = true
	end

	st.meet_manager:set_start_distance()

	--print_table(st.far_distance)
	-- флажок, что функция хотя бы раз вызывалась

	st.can_gtfo			= ini:r_string_ex(section,"can_gtfo","true")
	st.meet_set = true
end

--- Находится ли чувак в данный момент в состоянии мита

function Cmeet_manager:update()
 error("unexpected update without actor")
end
