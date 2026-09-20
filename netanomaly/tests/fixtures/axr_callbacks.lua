db = {}
actor_calls = 0
npc_calls = 0
gamma_net_compat = {install = function() end}

local actor_handler = {actor_on_update = function() actor_calls = actor_calls + 1 end}
local npc_handler = {npc_on_update = function() npc_calls = npc_calls + 1 end}
local intercepts = {
	actor_on_update = {[actor_handler] = true},
	npc_on_update = {[npc_handler] = true},
}

function spairs(values)
	return pairs(values)
end

function sort_func_values_ascend()
	return false
end

function make_callback(name,...)
	if (intercepts[name]) then
		for func_or_userdata, v in spairs(intercepts[name], sort_func_values_ascend) do
			if (type(func_or_userdata) == "function") then
				func_or_userdata(...)
			elseif (func_or_userdata[name]) then
				func_or_userdata[name](func_or_userdata,...)
			end
		end
	end
end

function on_game_start()
end
