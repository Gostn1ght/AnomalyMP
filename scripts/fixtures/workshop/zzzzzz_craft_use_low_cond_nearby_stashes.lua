--[[
	Monkey patch: craft_use_low_cond.script
	Extends low-condition priority crafting to search nearby stashes

	Features:
	- Searches both inventory and nearby stashes for degradable items
	- Artefact high-priority option: regular artefacts use highest condition first
	- Perk artefacts (af_signet, af_pas) always use lowest condition first
	- Deletes items from stashes, ensures result items are created
--]]

function on_game_start()
	-- Save reference to the previous Craft wrapper (craft_use_low_cond's version)
	local craft_use_low_cond_Craft = ui_workshop.UIWorkshopCraft.Craft

	-- Override with our version that searches nearby stashes
	function ui_workshop.UIWorkshopCraft:Craft()
		-- Get stash range from MCM
		local stash_range = ui_mcm and ui_mcm.get("craft_from_stashes/range") or 10

		-- Reset stash artefact condition data (read by zz_ui_workshop_keep_crafting_window_open)
		self._stash_arty_total_cond = 0
		self._stash_arty_counter = 0
		self._stash_arty_randomize = 0

		for idx,_ in pairs(self.craft_item) do
			local sec

			-- Save item section if it's degradable
			local first_id = self.craft_item[idx][1]
			local item = first_id and level.object_by_id(first_id)
			local degradable = item and utils_item.is_degradable(item)
			if degradable then
				sec = item:section()
			end

			if sec then
				-- Save # of item needed. Empty craft table
				local craft_cnt = #self.craft_item[idx]
				self.craft_item[idx] = {}
				local cond_sort_list = {}
				local item_parents = {}  -- Track which stash each item is in

				-- Reusable search function for collecting items
				local function search_items(temp, item)
					if item:section() == sec then
						cond_sort_list[item:id()] = item:condition()
						item_parents[item:id()] = temp  -- temp is the parent (nil for inventory, stash obj for stashes)
					end
				end

				-- Collect items from player inventory (parent = nil)
				db.actor:iterate_inventory(search_items, nil)

				-- Collect from workshop stash if it exists
				local stashId = self.stashId or (self.owner and self.owner.stashId)
				if stashId then
					local stash_obj = get_object_by_id(stashId)
					if stash_obj then
						stash_obj:iterate_inventory_box(search_items, stash_obj)
					end
				end

				-- Collect from nearby stashes (parent = stash obj)
				-- Note: clsid check is already done inside IterateStashesInRange
				IterateStashesInRange(search_items, stash_range)

				-- Sort by condition ascending (lowest condition first)
				-- For artefacts, optionally use descending sort (highest condition first) based on MCM setting
				-- Exception: perk artefacts (like af_signet) always use low-condition-first
				local counter = 1
				local mcm_setting = ui_mcm and ui_mcm.get("craft_from_stashes/artefact_high_priority")
				local use_high_priority = (mcm_setting ~= false)
				local sort_func = value_sort_ascending
				local kind = SYS_GetParam(0, sec, "kind")
				local r_kind = SYS_GetParam(0, self.craft_item_r[1], "kind")
				if r_kind == "i_arty" then
					if kind == "i_arty" and use_high_priority then
						sort_func = value_sort_descending
					elseif kind == "i_arty_junk" and use_high_priority then
						sort_func = value_sort_ascending
					end
				end

				for id, cond in spairs(cond_sort_list, sort_func) do
					if counter > craft_cnt then break end

					local parent = item_parents[id]
					if parent then
						-- Item is in stash: save artefact condition data before releasing
						-- (zz_ui_workshop_keep_crafting_window_open reads self._stash_arty_* to set result condition)
						if kind == "i_arty" then
							self._stash_arty_total_cond = self._stash_arty_total_cond + cond
							self._stash_arty_counter = self._stash_arty_counter + 1
						elseif kind == "i_arty_junk" then
							self._stash_arty_total_cond = 1
							self._stash_arty_counter = 1
							self._stash_arty_randomize = 1
						end
						alife_release_id(id)
					else
						-- Inventory item: add to craft_item so base_craft releases it
						self.craft_item[idx][#self.craft_item[idx] + 1] = id
					end

					counter = counter + 1
				end
			end
		end

		-- Call base_craft directly (skips craft_use_low_cond's loop which crashes when craft_item[n] is empty).
		-- base_craft is set by craft_use_low_cond at game start; fall back to saved reference if not installed.
		local final_craft = (type(base_craft) == "function") and base_craft or craft_use_low_cond_Craft
		final_craft(self)
	end
end

function value_sort_ascending(t, a, b)
	return t[a] < t[b]
end

function value_sort_descending(t, a, b)
	return t[a] > t[b]
end
