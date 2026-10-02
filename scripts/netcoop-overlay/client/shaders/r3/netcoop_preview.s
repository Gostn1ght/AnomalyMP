function normal(shader, t_base, t_second, t_detail)
    local bumped = t_second ~= "null" and t_second ~= ""
    shader:begin("netcoop_preview", bumped and "netcoop_preview_bump" or "netcoop_preview"):fog(false):zb(true, true):blend(false)
    shader:dx10texture("s_base", t_base)
    if bumped then shader:dx10texture("s_bump", t_second) end
    shader:dx10sampler("smp_base")
    shader:dx10texture("s_menu_shadow", "$user$menu_room_shadow")
    shader:dx10sampler("smp_nofilter")
end
