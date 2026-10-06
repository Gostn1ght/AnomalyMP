# Location cluster watchdog: runs this machine's location servers and starts
# again any that exits. The plan is appdata\server\netcoop_cluster.ltx
# ([locations] map = host:port, [launch] map = start section, [cluster]
# per_server); a map belongs to this machine when its host is one of its
# addresses (or 127.0.0.1/localhost). Servers start one after another: a
# loading server briefly needs ~6 GB.
#
# It fits the servers to this machine: free memory is measured all the time;
# the system keeps -SystemReserveGB and a game client on the same PC keeps
# -ClientReserveGB (while it runs, or always with -WithClient). When a player
# heads to a map whose server is not running and memory is short, the server
# that has stood empty the longest is stopped first (its world was saved when
# its last player left). Servers run at below-normal priority so the game
# client stays smooth; the video card is the client's alone (servers draw nothing).
#   powershell -ExecutionPolicy Bypass -File netcoop_cluster_watchdog.ps1 [-Maps k00_marsh,l01_escape] [-WithClient]
param(
    [string]$Runtime = $PSScriptRoot,
    [string[]]$Maps = @(),
    [int]$LoadTimeoutSeconds = 600,
    [double]$SystemReserveGB = 3,
    [double]$ClientReserveGB = 8,
    [switch]$WithClient
)
$ErrorActionPreference = "Stop"
$exe = Join-Path $Runtime "dedicated\LostZoneServerDX11.exe"
$planPath = Join-Path $Runtime "appdata\server\netcoop_cluster.ltx"
if (-not (Test-Path $exe)) { throw "missing $exe" }
if (-not (Test-Path $planPath)) { throw "missing $planPath (copy scripts\netcoop-cluster\netcoop_cluster.ltx.full there)" }

# Minimal ltx reader: section -> ordered key/value pairs.
$plan = @{}; $section = $null
foreach ($line in Get-Content $planPath -Encoding Default) {
    $text = ($line -split ";", 2)[0].Trim()
    if ($text -match "^\[(.+)\]$") { $section = $Matches[1]; $plan[$section] = [ordered]@{}; continue }
    if ($section -and $text -match "^([^=]+?)\s*=\s*(.+)$") { $plan[$section][$Matches[1]] = $Matches[2] }
}
$perServer = if ($plan["cluster"] -and $plan["cluster"]["per_server"]) { [int]$plan["cluster"]["per_server"] } else { 128 }
$local = @("127.0.0.1", "localhost", $env:COMPUTERNAME.ToLower())
try { $local += (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | ForEach-Object { $_.IPAddress }) } catch {}

$servers = @()
foreach ($map in $plan["locations"].Keys) {
    if ($Maps.Count -and $Maps -notcontains $map) { continue }
    $address = $plan["locations"][$map]
    $hostName, $port = $address -split ":"
    if ($local -notcontains $hostName.ToLower()) { continue }
    $start = $plan["launch"][$map]
    if (-not $start) { Write-Host "skip $map`: no [launch] start section"; continue }
    # The first two servers keep the worlds they had before the full plan.
    $world = switch ($map) { "k00_marsh" { "zone" } "l01_escape" { "zone_escape" } default { "zone_$map" } }
    $onDemand = $plan["on_demand"] -and $plan["on_demand"][$map] -eq "1"
    $servers += @{ Name = $map; Port = [int]$port; Start = $start; World = $world; OnDemand = $onDemand }
}
if (-not $servers.Count) { throw "no maps of this machine in $planPath" }

function Find-Log($s) {
    $log = if ($s.Name -eq "k00_marsh") { "srv" } else { "srv_$($s.Name)" }
    Get-ChildItem (Join-Path $Runtime "appdata\server\logs") -Filter "xray_$log`_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^xray_$([regex]::Escape($log))_[^_]+\.log$" } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Start-Location($s) {
    $log = if ($s.Name -eq "k00_marsh") { "srv" } else { "srv_$($s.Name)" }
    $arguments = "-nosplashwindow -netcoop -dbg -multi_instance -logname $log -fsltx fsgame_server.ltx " +
        "-netport $($s.Port) -netcoop_start_location=$($s.Start) -netcoop_world=$($s.World) " +
        $(if ($s.OnDemand) { "-netcoop_idle_exit=600 " } else { "" }) +
        "-start `"server(all/single/alife/new/portsv=$($s.Port)/maxplayers=$perServer)`" " +
        "`"client(localhost/name=serverauthority/port=$($s.Port)/portcl=$($s.Port + 1))`""
    $p = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $Runtime -WindowStyle Hidden -PassThru
    try { $p.PriorityClass = "BelowNormal" } catch {}
    Write-Host ("{0:HH:mm:ss} started {1} (port {2}, pid {3})" -f (Get-Date), $s.Name, $s.Port, $p.Id)
    # Wait until it runs (its clock line) before loading the next one.
    $since = Get-Date
    while (((Get-Date) - $since).TotalSeconds -lt $LoadTimeoutSeconds -and -not $p.HasExited) {
        $file = Find-Log $s
        if ($file -and $file.LastWriteTime -gt $since -and (Select-String -Path $file.FullName -Pattern "\[world\] saved \S+ \(bootstrap\)|loading saved world" -Quiet)) { break }
        Start-Sleep -Seconds 5
    }
    return $p
}

# ---- machine budget ----------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$cores = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
Write-Host ("machine: {0} GB memory, {1} logical cores; reserve {2} GB system + {3} GB game client" -f $totalGB, $cores, $SystemReserveGB, $ClientReserveGB)

function Server-MemoryGB {
    # Measured from running servers; 1.5 GB until one has started.
    $ws = Get-Process LostZoneServerDX11 -ErrorAction SilentlyContinue | ForEach-Object { $_.WorkingSet64 }
    if ($ws) { return [math]::Max(0.5, (($ws | Measure-Object -Average).Average / 1GB)) }
    return 1.5
}
function Free-BudgetGB {
    $free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    $clientRunning = [bool](Get-Process LostZoneClientDX11 -ErrorAction SilentlyContinue)
    # A running client already holds its memory; without one, keep room for it.
    $reserve = $SystemReserveGB + $(if ($WithClient -and -not $clientRunning) { $ClientReserveGB } else { 0 })
    return $free - $reserve
}
function Players-On($s) {
    $file = Join-Path $Runtime "appdata\server\netcoop_cluster\status_$($s.Port).txt"
    $line = Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line -match "^\d+ (\d+) ") { return [int]$Matches[1] }
    return 0
}
$idleSince = @{}
# Make room for one more server: stop the on-demand server empty for longest.
function Make-Room($need) {
    while ((Free-BudgetGB) -lt $need) {
        $victim = $null
        foreach ($s in $servers) {
            $p = $running[$s.Name]
            if (-not $s.OnDemand -or -not $p -or $p.HasExited -or (Players-On $s) -gt 0 -or -not $idleSince[$s.Name]) { continue }
            if (-not $victim -or $idleSince[$s.Name] -lt $idleSince[$victim.Name]) { $victim = $s }
        }
        if (-not $victim) { return $false }
        Write-Host ("{0:HH:mm:ss} memory short: stopping empty {1}" -f (Get-Date), $victim.Name)
        Stop-Process -Id $running[$victim.Name].Id -Force -ErrorAction SilentlyContinue
        $running.Remove($victim.Name); $idleSince.Remove($victim.Name)
        Start-Sleep -Seconds 5
    }
    return $true
}

Write-Host ("{0} map(s) on this machine: {1}" -f $servers.Count, (($servers | ForEach-Object { $_.Name + $(if ($_.OnDemand) { " (on demand)" } else { "" }) }) -join ", "))
$wakeDir = Join-Path $Runtime "appdata\server\netcoop_cluster"
$running = @{}
# Always-on maps start now; on-demand maps when a server asks for them
# (wake_<map>.txt: a player is heading there) and exit by themselves when idle.
foreach ($s in $servers) { if (-not $s.OnDemand) { $running[$s.Name] = Start-Location $s } }
while ($true) {
    Start-Sleep -Seconds 5
    foreach ($s in $servers) {
        $p = $running[$s.Name]
        $wake = Join-Path $wakeDir "wake_$($s.Name).txt"
        if ($p -and -not $p.HasExited) {
            if ((Players-On $s) -gt 0) { $idleSince.Remove($s.Name) } elseif (-not $idleSince[$s.Name]) { $idleSince[$s.Name] = Get-Date }
        }
        if ($s.OnDemand) {
            if ((-not $p -or $p.HasExited) -and (Test-Path $wake)) {
                # A loading server briefly needs about twice its running size.
                if (-not (Make-Room (2 * (Server-MemoryGB)))) {
                    if (-not $s.Waiting) { Write-Host ("{0:HH:mm:ss} {1} requested, but memory is short and no map is empty" -f (Get-Date), $s.Name) }
                    $s.Waiting = $true
                    continue
                }
                $s.Waiting = $false
                Remove-Item $wake -Force -ErrorAction SilentlyContinue
                Write-Host ("{0:HH:mm:ss} {1} requested" -f (Get-Date), $s.Name)
                $running[$s.Name] = Start-Location $s
            } elseif ($p -and $p.HasExited) {
                Write-Host ("{0:HH:mm:ss} {1} stopped (code {2}); starts again on demand" -f (Get-Date), $s.Name, $p.ExitCode)
                $running.Remove($s.Name)
            } elseif (Test-Path $wake) { Remove-Item $wake -Force -ErrorAction SilentlyContinue }
        } elseif ($p.HasExited) {
            Write-Host ("{0:HH:mm:ss} {1} exited with code {2}; restarting" -f (Get-Date), $s.Name, $p.ExitCode)
            $running[$s.Name] = Start-Location $s
        }
    }
}
