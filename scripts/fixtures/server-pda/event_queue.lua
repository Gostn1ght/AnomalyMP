local ev_queue = {}
function CreateTimeEvent(ev_id,act_id,timer,f,...)
	if not (ev_queue[ev_id]) then
		ev_queue[ev_id] = {}
		ev_queue[ev_id].__size = 0
	end

	if not (ev_queue[ev_id][act_id]) then
		ev_queue[ev_id][act_id] = {}
		ev_queue[ev_id][act_id].timer = time_global() + timer*1000
		ev_queue[ev_id][act_id].f = f
		ev_queue[ev_id][act_id].p = {...}
		ev_queue[ev_id].__size = ev_queue[ev_id].__size + 1
	end
end
function RemoveTimeEvent(ev_id,act_id)
	if (ev_queue[ev_id] and ev_queue[ev_id][act_id]) then
		ev_queue[ev_id][act_id] = nil
		ev_queue[ev_id].__size = ev_queue[ev_id].__size - 1
	end
end
function ResetTimeEvent(ev_id,act_id,timer)
	if (ev_queue[ev_id] and ev_queue[ev_id][act_id]) then
		ev_queue[ev_id][act_id].timer = time_global() + timer*1000
	end
end
function ProcessEventQueue(force)
	if has_alife_info("sleep_active") then
		return false
	end
	
	for event_id,actions in pairs(ev_queue) do
		for action_id,act in pairs(actions) do
			if (action_id ~= "__size") then
				if (force) or (time_global() >= act.timer) then
					-- utils_data.debug_write(strformat("event_queue: event_id=%s action_id=%s",event_id,action_id))
					if (act.f(unpack(act.p)) == true) then
						ev_queue[event_id][action_id] = nil
						ev_queue[event_id].__size = ev_queue[event_id].__size - 1
					end
				end
			end
		end

		if (ev_queue[event_id].__size == 0) then
			ev_queue[event_id] = nil
		end
	end
	
	return false
end
