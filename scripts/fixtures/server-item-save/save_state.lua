function save_state(m_data) --// NOTE: bolts aren't saved in alife, so this is a temp solution
	local bolts = {}
	local function itr(obj)
		local sec = obj:section()
		if (sec == "bolt") or (sec == "bolt_bullet") then
			if (not bolts[sec]) then
				bolts[sec] = 0
			end
			bolts[sec] = bolts[sec] + 1
		end
		return false
	end
	db.actor:inventory_for_each(itr)
	
	m_data.bolts = bolts
	m_data.bolt_slot = db.actor:item_in_slot(6) and db.actor:item_in_slot(6):section() or nil
end
