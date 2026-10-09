# Checks the two portable Lost Zone folders built by make-portable-release.ps1
# WITHOUT starting the game or a server (owner's rule 2026-10-09):
#   - no junction / symbolic link anywhere (nothing points back to C:);
#   - no absolute path to the builder's disk in launchers, templates, the
#     hoster scripts or the configs (*.ltx, *.cmd, *.ps1, *.json, *.xml);
#   - no PDB, no accounts / characters / worlds / session or secret files, no
#     private debug probes; no server scripts in the players' folder;
#   - every fsgame alias of the template resolves inside the folder;
#   - archives present (players: all categories; server: all but textures);
# then writes MANIFEST-sha256.txt (binaries and archives) into each folder.
param([Parameter(Mandatory = $true)][string]$Out, [string]$Builder = "C:\Users\Mahito")
$ErrorActionPreference = "Stop"
$fail = @()
$game = Join-Path $Out "Lost Zone"
$host_ = Join-Path $Out "Lost Zone Server"
foreach ($root in $game, $host_) {
    if (-not (Test-Path $root)) { $fail += "missing $root"; continue }
    $links = Get-ChildItem $root -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue
    if ($links) { $fail += "links in ${root}: " + (($links | Select-Object -First 5).FullName -join ", ") }
    $pdb = Get-ChildItem $root -Recurse -Force -Filter *.pdb -ErrorAction SilentlyContinue
    if ($pdb) { $fail += "PDB in ${root}: " + (($pdb | Select-Object -First 5).FullName -join ", ") }
    $text = Get-ChildItem $root -Recurse -Force -File -Include *.ltx, *.cmd, *.ps1, *.json, *.xml, *.template, *.txt -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\db\\' }
    foreach ($f in $text) {
        if ((Select-String -LiteralPath $f.FullName -SimpleMatch $Builder -Quiet)) { $fail += "builder path in $($f.FullName)" }
    }
    $private = Get-ChildItem $root -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^(netcoop_debug.*\.lua|accounts.*|.*\.scop|.*\.scoc|.*secret.*|.*session.*|.*lease.*|.*ownership.*)$' -or
        $_.FullName -match '\\appdata\\.*\\(savedgames|netcoop_cluster\\|accounts|characters)'
    }
    if ($private) { $fail += "private files in ${root}: " + (($private | Select-Object -First 5).FullName -join ", ") }
}
if (Test-Path (Join-Path $game "server")) { $fail += "server scripts in the players' folder" }
if (Test-Path (Join-Path $game "dedicated")) { $fail += "dedicated server in the players' folder" }
foreach ($c in "lz_misc", "lz_meshes", "lz_levels", "lz_sounds", "lz_textures") {
    if (-not (Get-ChildItem (Join-Path $game "db\lostzone") -Filter "$c.db*" -ErrorAction SilentlyContinue)) { $fail += "players: no $c archives" }
    $onServer = Get-ChildItem (Join-Path $host_ "db\lostzone") -Filter "$c.db*" -ErrorAction SilentlyContinue
    if ($c -eq "lz_textures" -and $onServer) { $fail += "server: texture archives present" }
    if ($c -ne "lz_textures" -and -not $onServer) { $fail += "server: no $c archives" }
}
foreach ($pair in @(@($game, "fsgame.template", "bin\LostZoneClientDX11.exe"), @($host_, "fsgame_server.template", "dedicated\LostZoneServerDX11.exe"))) {
    $t = Join-Path $pair[0] $pair[1]
    if (-not (Test-Path $t)) { $fail += "missing $t"; continue }
    $lines = Get-Content -LiteralPath $t -Encoding Default
    if (($lines | Where-Object { $_ -match ':\\' })) { $fail += "absolute path in $t" }
    if (-not ($lines | Where-Object { $_ -like '$fs_root$*{ROOT}*' })) { $fail += "no {ROOT} fs_root in $t" }
    if (-not (Test-Path (Join-Path $pair[0] $pair[2]))) { $fail += "missing $($pair[2])" }
}
foreach ($root in $game, $host_) {
    if (-not (Test-Path $root)) { continue }
    $manifest = Get-ChildItem $root -Recurse -File | Where-Object { $_.Extension -in ".exe", ".dll" -or $_.Name -match '\.db[0-9a-f]*$' } |
        Sort-Object FullName | ForEach-Object { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash, $_.FullName.Substring($root.Length + 1) }
    Set-Content -LiteralPath (Join-Path $root "MANIFEST-sha256.txt") -Value $manifest -Encoding ascii
    $size = (Get-ChildItem $root -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Host ("{0}: {1:N1} GB, {2} hashed files" -f $root, ($size / 1GB), $manifest.Count)
}
if ($fail) { $fail | ForEach-Object { "FAIL: $_" }; exit 1 }
"PASS: both folders portable (no links, no builder paths, no PDB/private files), archives complete; game and server were NOT started"
