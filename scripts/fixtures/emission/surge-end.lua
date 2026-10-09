function CSurgeManager:end_surge(manual)

	if (self.started == true) then 
		game_statistics.increment_statistic("emissions")
		self:kill_all_unhided()
		SendScriptCallback("actor_on_interaction", "anomalies", nil, "emissions")
		SendScriptCallback("actor_on_interaction", "anomalies", nil, "emission_end")
	end
	
	self.last_surge_time 	= game.get_game_time()
	self.started 			= false
	self.finished 			= true

	self:new_surge_time(false)

	self.surge_message 		= ""
	self.surge_task_sect 	= ""
	self.task_given 		= nil
	
	presurge_played = {0, 0, 0, 0, 0}

	if(self.blowout_sound) then
		xr_sound.stop_sound_looped(AC_ID, "blowout_rumble")
	end
	if(self.wave_sound) then
		xr_sound.stop_sound_looped(AC_ID, "blowout_particle_wave_looped")
	end
	for k,wave in pairs(self.blowout_waves) do
		if wave.effect:playing() then
			self:kill_wave(k)
		end
	end
	for k,snd in pairs(self.blowout_sounds) do
		if snd ~= nil and snd:playing() then
			snd:stop()
		end
	end
	if(self.second_message_given) then
		xr_sound.stop_sound_looped(AC_ID, "surge_earthquake_sound_looped")
	end

	if(manual or (self.time_forwarded and level_weathers.get_weather_manager().weather_fx)) then
		level.stop_weather_fx()
--		level_weathers.get_weather_manager():select_weather(true)
		level_weathers.get_weather_manager():forced_weather_change()
	end

	self.effector_set 			= false
	self.second_message_given 	= false
	self.ui_disabled  			= false
	self.blowout_sound			= false
	self.wave_sound			= false
	prev_sec				= 0
	self.hitFactor=0

	level.remove_pp_effector(surge_shock_pp_eff)
	level.remove_cam_effector(earthquake_cam_eff)
	-- hide indicators
	self:displayIndicators(0)

	level.set_time_factor(self.game_time_factor)

	for k,v in pairs(db.signal_light) do
		v:stop_light()
		v:stop()
	end
end

