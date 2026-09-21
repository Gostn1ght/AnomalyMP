"""Guard installed GAMMA debug entry points and route UI actions to the server."""
import re


def patch_debug(data, name):
    if b'-- GAMMA_SERVER_ADMIN_GUARD' in data:
        return data
    if name == 'ui_debug_launcher.script':
        # Dispatch before the original local console/functor branches can run.
        entries = {
            b'function UIDebugMain:Execute(tab,index)':
                b'\n\tif not gamma_net_compat.admin_allowed() then return end\n'
                b'\tif not gamma_net_compat.is_server() then\n'
                b'\t\treturn gamma_net_compat.request_admin("debug_action " .. tostring(tab) .. " " .. tostring(index))\n\tend',
            b'function UIDebugMain:OnConsoleInput()':
                b'\n\tif not gamma_net_compat.admin_allowed() then return end\n'
                b'\tif not gamma_net_compat.is_server() then\n'
                b'\t\treturn gamma_net_compat.request_admin("debug " .. self.console_input:GetText())\n\tend',
        }
        for anchor, addition in entries.items():
            if data.count(anchor) != 1:
                raise ValueError('Unexpected GAMMA debug handler: ' + anchor.decode())
            data = data.replace(anchor, anchor + addition)
        # Include direct keybinds and exported mutation functions, not only the F7 opener.
        pattern = rb'(function (?!UIDebugMain:Execute\(|UIDebugMain:OnConsoleInput\()[A-Za-z_][A-Za-z_0-9]*\([^\r\n]*\))'
        def guard(match):
            declaration = match.group(1)
            function = re.search(rb'function ([A-Za-z_][A-Za-z_0-9]*)', declaration).group(1)
            addition = b'\n\tif not gamma_net_compat.admin_allowed() then return end'
            if function not in (b'prepare', b'inject', b'on_game_start', b'start_debug_main'):
                addition += (b'\n\tif not gamma_net_compat.is_server() then return gamma_net_compat.request_admin("debug_named '
                             + function + b'") end')
            return declaration + addition
        data = re.sub(pattern, guard, data)
        # A caller can instantiate a spawner or invoke its methods without the launcher.
        class_pattern = rb'(function (UIDebug_[A-Za-z_0-9]+):([A-Za-z_][A-Za-z_0-9]*)\([^\r\n]*\))'
        def guard_class(match):
            method = match.group(3)
            if method in (b'__init', b'__finalize', b'Close'):
                return match.group(1)
            return (match.group(1) + b'\n\tif not gamma_net_compat.admin_allowed() or not gamma_net_compat.is_server() then return end')
        data = re.sub(class_pattern, guard_class, data)
    elif name == 'z_serious_monkey_ui_debug_launcher.script':
        anchor = b'ui_debug_launcher.start_workshop = function(...)'
        if data.count(anchor) != 1:
            raise ValueError('Unexpected GAMMA workshop override')
        data = data.replace(anchor, anchor + b'\n    if not gamma_net_compat.admin_allowed() then return end\n'
                            b'    if not gamma_net_compat.is_server() then return gamma_net_compat.request_admin("debug_named start_workshop") end')
    elif name == 'imgui_lua_debug.script':
        anchor = b'ImGui.Groups.Widget("Debug", function()'
        if data.count(anchor) != 1:
            raise ValueError('Unexpected GAMMA Lua debugger widget')
        data = data.replace(anchor, anchor + b'\n    if not gamma_net_compat.admin_allowed() or not gamma_net_compat.is_server() then return end')
    else:
        raise ValueError('Unsupported debug script')
    return b'-- GAMMA_SERVER_ADMIN_GUARD\n' + data


DEBUG_SCRIPTS = ('ui_debug_launcher.script', 'z_serious_monkey_ui_debug_launcher.script', 'imgui_lua_debug.script')
