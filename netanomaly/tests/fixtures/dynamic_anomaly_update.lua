bind_anomaly_field_update = bind_anomaly_field.anomaly_field_binder.update
bind_anomaly_field.anomaly_field_binder.update = function(self, delta)
	bind_anomaly_field_update(self, delta)
	if not self.object then return end

	local section = self.section
	if anomalies_near_actor_functions[section] or (additional_articles_to_category.encyclopedia_anomalies[section] and not opened_articles.encyclopedia_anomalies[additional_articles_to_category.encyclopedia_anomalies[section]]) then

		-- Get behaviour radius and check if actor inside it, then apply effect
		local actor = db.actor
		local radius_sqr = self.radius_sqr
		local distance_to_sqr = self.object:position():distance_to_sqr(actor:position())
		if distance_to_sqr <= radius_sqr then
			-- Open anomaly article
			open_anomaly_article(section)

			-- Beep near anoms if option enabled or have Svarog or Anomaly Detector
			if not anomaly_detector_ignore[section] then
				notify_anomaly(self, actor, distance_to_sqr, radius_sqr, false)
			end

			-- Behaviour near actor
			if anomalies_near_actor_functions[section] then
				anomalies_near_actor_functions[section](self, actor, distance_to_sqr, radius_sqr)
			end

			-- printf("actor near anomaly %s, firing effect, delta %s", section, delta)
		else
			anomalies_vars.remove_factor(anomalies_vars, self, actor, distance_to_sqr, radius_sqr)
		end
	end
	if npc_on_near_anomalies_functions[section] then
		if not self.iterate_nearest_func then
			self.iterate_nearest_func = function(obj)
				if obj
				and (IsStalker(obj) or IsMonster(obj))
				and (obj.alive and obj:alive())
				and obj:id() ~= AC_ID
				and obj:position():distance_to_sqr(self.object:position()) <= self.radius_sqr
				then
					npc_on_near_anomalies_functions[section](self, obj, db.actor)
				end
			end
		end
		level.iterate_nearest(self.object:position(), self.radius, self.iterate_nearest_func)
	end
end

