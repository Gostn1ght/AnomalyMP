function generate_cache()
	function x(section)
		CFG_CACHE[section] = {}
		CFG_CACHE[section].stage_complete = task_manager.task_ini:r_float_ex( section, "stage_complete" )
		CFG_CACHE[section].sim_communities = task_manager.task_ini:r_string_ex( section, "sim_communities" )
		CFG_CACHE[section].job_descr = task_manager.task_ini:r_string_ex( section, "job_descr" )
		CFG_CACHE[section].fetch_descr = task_manager.task_ini:r_string_ex( section, "fetch_descr" )
		CFG_CACHE[section].fetch_func = task_manager.task_ini:r_string_ex( section, "fetch_func" )
		CFG_CACHE[section].task_complete_descr = task_manager.task_ini:r_string_ex( section, "task_complete_descr" )
		CFG_CACHE[section].can_cancel = task_manager.task_ini:r_string_ex( section, "can_cancel" )
		CFG_CACHE[section].on_job_descr = task_manager.task_ini:r_string_ex( section, "on_job_descr" )
		
	end
	task_manager.task_ini:section_for_each(x)
	-- utils_data.print_table(CFG_CACHE,strformat('parsed_task_data', section))
end
