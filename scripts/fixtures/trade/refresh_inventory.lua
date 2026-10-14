-- Actual GAMMA UIInventory method; retained game source, used for late-profile regression.
function UIInventory:TMode_RefreshInventories()

	-- Actor
	local cc_a = self.CC["actor_trade_bag"]
	local cc_at = self.CC["actor_trade"]
	local list_a = cc_a.indx_id
	local list_at = cc_at.indx_id
	local inv_a = self:ParseInventory(db.actor, nil, true)
	for id,obj in pairs(inv_a) do
		if (not list_a[id]) and (not list_at[id]) then
			cc_a:AddItem(obj, obj:section())
		end
	end
	for id,idx in pairs(list_a) do
		if (not inv_a[id]) then
			cc_a:RemoveItem_byID(id)
		end
	end
	for id,idx in pairs(list_at) do
		if (not inv_a[id]) then
			local obj = level.object_by_id(id)
			if obj and (not in_actor_inv(obj)) then -- Important because trade bag is proccessed differently
				cc_at:RemoveItem_byID(id)
			end
		end
	end

	-- NPC
	local npc = self:GetPartner()

	local cc_b = self.CC["npc_trade_bag"]
	local cc_bt = self.CC["npc_trade"]
	local list_b = cc_b.indx_id
	local list_bt = cc_bt.indx_id
	local inv_b = self:ParseInventory(npc, nil, true)
	for id,obj in pairs(inv_b) do
		if (not list_b[id]) and (not list_bt[id]) then
			cc_b:AddItem(obj, obj:section())
		end
	end
	for id,idx in pairs(list_b) do
		if (not inv_b[id]) then
			cc_b:RemoveItem_byID(id)
		end
	end
	--
	for id,idx in pairs(list_bt) do
		if (not inv_b[id]) then
			local obj = level.object_by_id(id)
			if obj and (not in_npc_inv(npc, obj)) then -- Important because trade bag is proccessed differently
				cc_bt:RemoveItem_byID(id)
			end
		end
	end
	--
end
