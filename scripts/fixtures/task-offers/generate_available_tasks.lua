function generate_available_tasks(npc,is_sim)
	local id = npc:id()
	if not (available_tasks[id]) then
		available_tasks[id] = {}
	else
		empty_table(available_tasks[id])
	end

    local tm = task_manager.get_task_manager()
    local task_info = tm.task_info

    local sec
    local st = db.storage[npc:id()]

	-- Randomly not offer any quests at all for sim npcs
	if (is_sim and st.dyn_quest_rand == nil) then
		if ( (math.random(1,100)/100) < 0.3) then
			st.dyn_quest_rand = "nil"
			return
		end
	end

    if (st and st.ini and st.section_logic) then
        sec = st.ini:r_string_ex(st.section_logic,"task_section")
        if (sec) then
            sec = sec .. "_task_"
        end
    end

    if not (sec) then
        sec = is_sim and "simulation_task_" or npc:section() ~= "m_trader" and npc:section().."_task_" or npc:name().."_task_"
    end
	
	local t
	local size_t = 0

			
	for task_id in pairs(CFG_CACHE) do
		if starts_with(task_id, sec) then
			if (task_info[task_id] == nil and xr_conditions.has_completed_task_prerequisites(nil,nil,{task_id})) then
				if (is_sim) then
					local p = parse_list(task_manager.task_ini,task_id,"sim_communities",true)
					if (p[character_community(npc)] == true) then
						if not (t) then
							t = {}
						end

						if (st.dyn_quest_rand == task_id) then
							size_t = size_t + 1
							available_tasks[id][size_t] = task_id
							return
						elseif (st.dyn_quest_rand == nil) then
							t[#t+1] = task_id
						end
					end
				else
					size_t = size_t + 1
					available_tasks[id][size_t] = task_id
				end
			end
		end
	end

	-- old code
	--[[
    local task_id = sec.."1"
    local count = 1
    while (task_manager.task_ini:section_exist(task_id)) do
        --printf("task_id=%s skipped=%s",task_id,skipped_tasks[task_id])
        if (task_info[task_id] == nil and xr_conditions.has_completed_task_prerequisites(nil,nil,{task_id})) then
			if (is_sim) then
				local p = parse_list(task_manager.task_ini,task_id,"sim_communities",true)
				if (p[character_community(npc)] == true) then
					if not (t) then
						t = {}
					end

					if (st.dyn_quest_rand == task_id) then
						size_t = size_t + 1
						available_tasks[id][size_t] = task_id
						return
					elseif (st.dyn_quest_rand == nil) then
						t[#t+1] = task_id
					end
				end
			else
				size_t = size_t + 1
				available_tasks[id][size_t] = task_id
			end
        end
        count = count + 1
        task_id = sec..tostring(count)
    end
	--]]

	-- randomize available tasks from sim npcs and only offer 1 job; remembing this job until NPC go offline
	if (t and #t > 0) then
		st.dyn_quest_rand = t[math.random(#t)]
		size_t = size_t + 1
		available_tasks[id][size_t] = st.dyn_quest_rand
	end
end
