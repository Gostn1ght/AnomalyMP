# Two portable Lost Zone folders (owner 2026-10-09): the game for players and
# a complete dedicated server with the location panel for a friend to host.
#
#   powershell -File scripts\dist\make-portable-release.ps1 -Out J:\LostZone -Artifact _build\artifacts\<sha>
#
# Inputs (read only): the GAMMA runtime (client/server configs+scripts), the
# GAMMA base archives (db), the packed GAMMA data in <Out>\_work (xrCompress
# lz_*.db*), a GitHub Actions artifact (binaries, hoster panel). The repo's
# current overlay is installed into a staging copy, never into the owner's
# runtime. Nothing here starts the game or a server.
#
# Output: <Out>\Lost Zone\ (players) and <Out>\Lost Zone Server\ (host).
#   - no junctions/symlinks, no absolute paths: each launcher writes its
#     fsgame from a template with the folder it runs from;
#   - no PDB, no accounts/characters/worlds/session files, no private probes,
#     no server scripts in the players' folder;
#   - GAMMA's merged data in standard compressed .db archives (xrCompress
#     -pack; -strong for meshes/levels/other). This is compression, NOT
#     encryption: community tools can unpack .db archives. Configs and
#     scripts stay loose because GAMMA mods read/write files there directly.
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [Parameter(Mandatory = $true)][string]$Artifact,
    [string]$Runtime = "",
    [string]$GammaDb = "C:\Users\Mahito\Downloads\GAMMA\GAMMA\db",
    [switch]$SkipCopy,
    [switch]$NoPacks
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $Runtime) { $Runtime = Join-Path $repo "..\gamma-runtime" } # PS 5.1: no $PSScriptRoot in param defaults
$Runtime = (Resolve-Path $Runtime).Path
$Artifact = (Resolve-Path $Artifact).Path
$work = Join-Path $Out "_work"
$game = Join-Path $Out "Lost Zone"
$host_ = Join-Path $Out "Lost Zone Server"
$stage = Join-Path $work "stage"

function Mirror($from, $to, [string[]]$extra = @()) {
    # /XJ: never follow or copy junctions; /XF *.pdb: no debug symbols.
    $roboArgs = @($from, $to, "/MIR", "/XJ", "/R:1", "/W:1", "/NFL", "/NDL", "/NP", "/NJH", "/XF", "*.pdb") + $extra
    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $from -> $to failed ($LASTEXITCODE)" }
}

# 1. Staging: GAMMA client/server configs+scripts with the current overlay.
Write-Host "staging the overlay"
New-Item -ItemType Directory -Force $stage | Out-Null
foreach ($role in "client", "server") { Mirror (Join-Path $Runtime $role) (Join-Path $stage $role) }
New-Item -ItemType Directory -Force (Join-Path $stage "gamedata\shaders
3") | Out-Null # the overlay copies preview shaders there
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo "scripts\patch-gamma-netcoop-overlay.ps1") -RuntimeRoot $stage | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw "overlay patch failed" }

# 2. The players' game.
Write-Host "players' folder"
New-Item -ItemType Directory -Force $game | Out-Null
Mirror (Join-Path $stage "client") (Join-Path $game "client")
Mirror (Join-Path $stage "gamedata") (Join-Path $game "gamedata")
Mirror (Join-Path $Artifact "bin") (Join-Path $game "bin")
if (-not $SkipCopy) { Mirror $GammaDb (Join-Path $game "db") @("/XD", "lostzone") }
New-Item -ItemType Directory -Force (Join-Path $game "db\lostzone"), (Join-Path $game "mp"), (Join-Path $game "appdata\player") | Out-Null
Copy-Item (Join-Path $PSScriptRoot "fsgame_client.template") (Join-Path $game "fsgame.template") -Force
Copy-Item (Join-Path $PSScriptRoot "Play Lost Zone.cmd") $game -Force
Copy-Item (Join-Path $PSScriptRoot "README-players.txt") (Join-Path $game "README.txt") -Force
Copy-Item (Join-Path $Artifact "notices") (Join-Path $game "notices") -Recurse -Force

# 3. The dedicated server with the location panel (no textures: a dedicated
#    server never loads texture images, CTexture::Load returns first).
Write-Host "server folder"
New-Item -ItemType Directory -Force $host_ | Out-Null
Mirror (Join-Path $stage "server") (Join-Path $host_ "server")
Mirror (Join-Path $stage "gamedata") (Join-Path $host_ "gamedata")
Mirror (Join-Path $Artifact "dedicated") (Join-Path $host_ "dedicated")
Mirror (Join-Path $Artifact "hoster") (Join-Path $host_ "hoster")
if (-not $SkipCopy) { Mirror $GammaDb (Join-Path $host_ "db") @("/XD", "textures", "lostzone") }
New-Item -ItemType Directory -Force (Join-Path $host_ "db\lostzone"), (Join-Path $host_ "mp"), (Join-Path $host_ "appdata\server") | Out-Null
Copy-Item (Join-Path $PSScriptRoot "fsgame_server.template") (Join-Path $host_ "fsgame_server.template") -Force
Copy-Item (Join-Path $PSScriptRoot "Start Server Panel.cmd") $host_ -Force
Copy-Item (Join-Path $PSScriptRoot "README-server.txt") (Join-Path $host_ "README.txt") -Force
Copy-Item (Join-Path $Artifact "notices") (Join-Path $host_ "notices") -Recurse -Force

# 4. Packed GAMMA data: everything for players, no textures for the server.
if ($NoPacks) { Write-Host "archives skipped (-NoPacks)"; return }
Write-Host "archives"
$packs = Get-ChildItem $work -File | Where-Object { $_.Name -match '^lz_[a-z]+\.db\d+$' }
foreach ($p in $packs) {
    if ($p.Name -notlike "lz_textures.*") { Copy-Item $p.FullName (Join-Path $host_ "db\lostzone") -Force }
    Move-Item $p.FullName (Join-Path $game "db\lostzone") -Force # same volume: no second copy
}

Write-Host "done: run scripts\dist\check-portable-release.ps1 -Out $Out"
