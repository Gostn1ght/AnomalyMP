# Repeated Windows Run/Cancel prompts on hoster startup

Owner confirmed the friend's repeated dialog is Windows "Open File - Security
Warning", Run/Cancel, after launching Start Locations.cmd from the downloaded
server overlay. Initialize-Master invokes the packaged master repeatedly
(init, bridge-config, writer-config for every map). With an Internet Zone.Identifier
mark on that EXE, each Start-Process may ask again; this looks like a loop.

All three distributed startup entry points now run
hoster/netcoop_unblock_launch.ps1 before launching master/maps/panel. It removes
the downloaded-file mark only from six fixed launch paths inside the chosen
kit: the dedicated EXE, packaged master EXE, optional portable Python EXE and
the three CMD entry points. Missing optional files are skipped. Reparse points
along a launch-file path are refused. Game client files, arbitrary executables,
accounts, worlds and machine security settings are untouched. This uses
[Microsoft's Unblock-File](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/unblock-file),
not a registry or system-policy change.

The real preparation function passed an inert NTFS alternate-stream fixture
under Windows PowerShell 5.1: six known files lost only their download mark;
three unrelated/client/account paths retained theirs; main file SHA256 values
did not change; repeat preparation was harmless. All three CMD entry points
prepare before invoking the master/panel. No executable, game or master was
started by the test. Fixture added to the Windows DX11 checks for future CI.

Only hoster launch scripts/readme and the public kit manifest are updated.
Native eca858c03, master e3fcbf1f1, resource patch000021 and client launcher
2026.10.16.2 remain pinned. A small overlay ZIP lets the friend fix an already
downloaded installation; the full server ZIP is refreshed too. Runtime
verification on the friend's Windows remains theirs; no server is started
on the owner's PC.
