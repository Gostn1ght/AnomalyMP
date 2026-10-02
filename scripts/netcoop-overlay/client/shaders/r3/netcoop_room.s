function normal(shader, t_base, t_second, t_detail)
    shader:begin("netcoop_room", "netcoop_room"):fog(false):zb(true, true):blend(false)
    shader:dx10texture("s_base", t_base)
    shader:dx10sampler("smp_base")
    shader:dx10texture("s_menu_shadow", "$user$menu_room_shadow")
    shader:dx10sampler("smp_nofilter")
end
