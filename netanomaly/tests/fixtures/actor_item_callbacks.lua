item_device_on_anomaly_touch = item_device.on_anomaly_touch
item_device.on_anomaly_touch = function(obj, flags)
	if flags.ret_value then
		item_device_on_anomaly_touch(obj, flags)
	end
end

itms_manager_actor_on_item_before_use = itms_manager.actor_on_item_before_use
itms_manager.actor_on_item_before_use = function(obj, flags)
	if flags.ret_value then
		itms_manager_actor_on_item_before_use(obj, flags)
	end
end
