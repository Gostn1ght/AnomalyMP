-- Actual retained GAMMA UIInventory:UpdateWeight; test adapter, source unchanged.
function UIInventory:UpdateWeight()

-- Player
	local actor = db.actor
	local outfit = actor:item_in_slot(7)
	local backpack = actor:item_in_slot(13)

	-- Current weight
	local tot_weight = actor:get_total_weight()

	-- Additional weight - Actor
	local max_weight = actor:get_actor_max_weight()

	-- Additional weight - Outfit
	max_weight = max_weight + (outfit and outfit:get_additional_max_weight() or 0)

	-- Additional weight - Backpack
	max_weight = max_weight + (backpack and backpack:get_additional_max_weight() or 0)

	-- Additional weight - Artefacts
    local function itr(npc,itm)
        if (npc:is_on_belt(itm)) then
            max_weight = max_weight + (itm and ((ini_sys:r_float_ex(itm:section(),"additional_inventory_weight") or 0) * itm:condition()) or 0)
        end
    end
    db.actor:iterate_inventory(itr,db.actor)

	-- Additional weight - Booster
	actor:cast_Actor():conditions():BoosterForEach( function(booster_type, booster_time, booster_value)
		if (booster_type == 4) then --eBoostMaxWeight
			max_weight = max_weight + booster_value
		end
	end)

	-- Change weight color according to how heavy the actor is
	local clr = clr_weight[1]
	if (tot_weight > max_weight) then
		clr = clr_weight[2]
	elseif (tot_weight + 10 > max_weight) then
		clr = clr_weight[3]
	end

	self.player_weight:SetTextColor( clr )
	self.player_weight:SetText( strformat("%s %s", round_idp(tot_weight,1), weight_unit) )
	self.player_weight_max:SetText( strformat("(max %s %s)", round_idp(max_weight,1), weight_unit) )

-- NPC
	local npc = self:GetPartner()
	if npc and (self.mode ~= "repair") then
		local weight = 0

		if self.npc_is_box then
			npc:iterate_inventory_box( function(owner,itm)
				weight = weight + itm:weight()
			end)

		elseif self:IsInvOwner(npc) then
			weight = npc:get_total_weight()
		end

		self.npc_weight:SetText( round_idp(weight,1) .. " " .. weight_unit )
		self.npc_weight_max:SetText( strformat("(max %s %s)", 30, weight_unit) )
	end
end
