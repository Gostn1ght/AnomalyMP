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

## Delivered

Hoster script source: `4d439aa1ce29f4dc7173d8254d8e5f19de6044a2`.
The actual Windows CMD error-path fixture and Windows PowerShell 5.1 ADS
fixture both passed. Existing CMD fixtures now copy the new preparation
dependency into their incomplete test kit; no native process is executed.

The updated public folder is `J:\LostZone_Work\Lost Zone Server` (6879
listed files; manifest additionally records hoster_scripts_commit).
Full replacement archive: `J:\LostZone_Work\Lost Zone Server.zip`,
236,022,404 bytes, 6880 entries, SHA256
`85126aaabdef2ec9404174ed819c044e1fd13f62211b0b04ca52ba98e559cc7a`.
Every entry was decompressed and checked against the manifest.

Small overlay for an existing download:
`J:\LostZone_Work\Lost Zone Server - launch fix.zip`, 341,880 bytes,
six entries (three CMDs, preparation PS1, readme and updated public manifest),
SHA256 `8ac2cf4b8c46eadf0d9ebb1d3ca8a0a6c092ead0ec0c43c88e397d0ea4d5585a`.
Its entries are byte-identical to the updated public folder. The friend
should close the old startup/dialogs, extract this overlay over the game
with replacement and start Start Locations.cmd again. No runtime files are
included. Owner process count for client/location/master remained zero.
