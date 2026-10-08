-- Actual GAMMA UIInventory:InitControls stats block, full source SHA256
--16CCF35AE84EA1F014FC1D38BF96617F99DE8BE44B62DE02368ADA8CCC5ABD32.
	self.stats_dialog            = xml:InitStatic("equipment:actor_state_info", self.equ_dialog)
	self.stat = {}
	for name,_ in pairs(self.stat_list) do
		self.stat[name]          = {}
		self.stat[name].base     = xml:InitStatic("equipment:actor_state_info:" .. name .. "_sensor", self.stats_dialog)
		self.stat[name].bar      = xml:InitProgressBar("equipment:actor_state_info:" .. name .. "_sensor:state_progress", self.stat[name].base)
		self.stat[name].ico_base = xml:InitStatic("equipment:actor_state_info:icon", self.stat[name].base)
		self.stat[name].text	 = xml:InitTextWnd("equipment:actor_state_info:" .. name .. "_sensor:stats", self.stat[name].base)
		self.stat[name].text_bonus	 = xml:InitTextWnd("equipment:actor_state_info:" .. name .. "_sensor:stats_bonus", self.stat[name].base)
		self.stat[name].text_bonus_regen	 = xml:InitTextWnd("equipment:actor_state_info:" .. name .. "_sensor:stats_bonus_regen", self.stat[name].base)
		
		self.stat[name].ico_p    = xml:InitStatic("equipment:actor_state_info:icon:active", self.stat[name].ico_base)
		self.stat[name].ico_p:InitTexture("ui_inGame2_inv_state_P_" .. name)
		self.stat[name].ico_p:Show(false)
		
		self.stat[name].ico_n    = xml:InitStatic("equipment:actor_state_info:icon:active", self.stat[name].ico_base)
		self.stat[name].ico_n:InitTexture("ui_inGame2_inv_state_N_" .. name)
		self.stat[name].ico_n:Show(false)
	end
