param(
    [Parameter(Mandatory=$true)][ValidateSet('server','p1','p2')][string]$Role,
    [Parameter(Mandatory=$true)][string]$GameRoot,
    [string]$Executable = 'AnomalyNetDX11.exe',
    [ValidateRange(1,128)][int]$MaxPlayers = 128
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $GameRoot).Path
if (!(Test-Path -LiteralPath (Join-Path $root 'custom-test-manifest.json'))) { throw 'Expected an isolated Custom test directory' }
if ([IO.Path]::GetFileName($Executable) -ne $Executable) { throw 'Executable must be a filename in the test bin directory' }
$exe = Join-Path $root ('bin\' + $Executable)
if (!(Test-Path -LiteralPath $exe)) { throw "Missing GitHub-built executable: $exe" }
$fs = 'fsgame_' + $Role + '.ltx'
if (!(Test-Path -LiteralPath (Join-Path $root $fs))) { throw 'Per-process fsgame configuration missing' }
$common = "-netcoop -dbg -net_trace -noprefetch -multi_instance -logname $Role -fsltx $fs "
switch ($Role) {
    'server' { $args = $common + "-netport 1237 -start server(all/single/alife/new/portsv=1237/maxplayers=$MaxPlayers) client(localhost/name=Host/port=1237/portcl=1240)" }
    'p1' { $args = $common + '-start client(localhost/name=Player1/port=1237/portcl=1241)' }
    'p2' { $args = $common + '-start client(localhost/name=Player2/port=1237/portcl=1242)' }
}
$proc = Start-Process -FilePath $exe -WorkingDirectory $root -ArgumentList $args -PassThru
[pscustomobject]@{ Role=$Role; ProcessId=$proc.Id; Executable=$exe; Arguments=$args } | ConvertTo-Json
