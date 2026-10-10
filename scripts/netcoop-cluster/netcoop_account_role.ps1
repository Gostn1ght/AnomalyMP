# Admin rights for a player's account (owner 2026-10-10: how to give admin on
# the server). The location servers run hidden, so their console command
# sv_account_role cannot be typed; this edits the shared accounts file the same
# way the servers do: under their lock (appdata\server\netcoop_locks\
# accounts.lock), written to a temporary file and swapped in. Every running
# server adopts the change (it rereads the file when its time changes); the
# player gets the role on the next login. Admin also approves the account, as
# the console command does. Nothing is started.
#   netcoop_account_role.ps1 -Runtime <server folder> -List
#   netcoop_account_role.ps1 -Runtime <server folder> -Login <name> -Role admin|player
param(
    [string]$Runtime = (Split-Path $PSScriptRoot -Parent),
    [string]$Login = "",
    [ValidateSet("", "admin", "player")][string]$Role = "",
    [switch]$List
)
$ErrorActionPreference = "Stop"
$data = Join-Path ([IO.Path]::GetFullPath($Runtime)) "appdata\server"
$path = Join-Path $data "netcoop_accounts.txt"
$bytes = [Text.Encoding]::GetEncoding(28591) # byte for byte, as the server writes it

function Read-Accounts {
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    return [IO.File]::ReadAllLines($path, $bytes)
}

if ($List -or -not $Login) {
    $rows = @(Read-Accounts | Where-Object { $_ -and -not $_.StartsWith("#") } | ForEach-Object {
        $f = $_ -split "\|"
        if ($f.Count -ge 4) { "  {0,-20} {1,-7} {2}" -f $f[0], $f[1], $(if ($f.Count -ge 7) { $f[6] } else { "approved" }) }
    })
    Write-Host ("{0} account(s) in {1}" -f $rows.Count, $path)
    $rows | ForEach-Object { Write-Host $_ }
    if (-not $Login) { return }
}
if ($Login -notmatch '^[A-Za-z0-9_.-]{3,20}$') { throw "Login: 3-20 letters, digits, _ - ." }
if (-not $Role) { throw "Role: admin or player" }
if (-not (Test-Path -LiteralPath $path)) { throw "No accounts yet: $path (the player has to register on the server first)" }

# The servers' lock: an exclusive file deleted on close (ClusterFileLock).
$locks = Join-Path $data "netcoop_locks"
New-Item -ItemType Directory -Force $locks | Out-Null
$lock = $null
$deadline = (Get-Date).AddSeconds(10)
while (-not $lock) {
    try {
        $lock = New-Object IO.FileStream((Join-Path $locks "accounts.lock"), [IO.FileMode]::OpenOrCreate,
            [IO.FileAccess]::Write, [IO.FileShare]::None, 1, [IO.FileOptions]::DeleteOnClose)
    } catch {
        if ((Get-Date) -gt $deadline) { throw "The accounts file is busy (a server is saving it); try again" }
        Start-Sleep -Milliseconds 20
    }
}
try {
    $found = $false
    $lines = @(Read-Accounts | ForEach-Object {
        $f = $_ -split "\|"
        if ($_ -and -not $_.StartsWith("#") -and $f.Count -ge 4 -and $f[0] -ieq $Login) {
            $found = $true
            $f[1] = $Role
            if ($Role -eq "admin" -and $f.Count -ge 7) { $f[6] = "approved" }
            $f -join "|"
        } else { $_ }
    })
    if (-not $found) { throw "Account '$Login' not found (sv_accounts / -List shows the logins)" }
    $temp = "$path.$PID.tmp"
    [IO.File]::WriteAllText($temp, (($lines -join "`n") + "`n"), $bytes)
    Move-Item -LiteralPath $temp -Destination $path -Force
} finally {
    $lock.Dispose()
}
Write-Host "$Login is now $Role (takes effect on the next login)"
