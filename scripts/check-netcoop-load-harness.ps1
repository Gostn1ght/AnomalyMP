$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'netcoop-selftest-results.ps1')
function Assert($Condition, $Message) { if (-not $Condition) { throw $Message } }
function BotLog($Name, $First, $Count) {
    $lines = @()
    foreach ($n in $First..($First + $Count - 1)) {
        $lines += "[Lost Zone][bots] nbot_$('{0:d3}' -f $n) plays Actor $n at 0 0 0"
        $lines += "[Lost Zone][bots] nbot_$('{0:d3}' -f $n) plays Actor $n at 0 0 0"
    }
    $lines += "[Lost Zone][bots] $Count wanted: $Count playing, 0 joining, 0 connecting, 0 failed; rx 1"
    [pscustomobject]@{ Name = $Name; Lines = $lines }
}
$logs = @(BotLog 'a' 1 2; BotLog 'b' 3 2)
function Evaluate($InputLogs, $ServerLines = @(), $Load = $true) {
    Get-NetcoopSelftestResult -BotLogs $InputLogs -ServerLines $ServerLines -ExpectedBots 4 -ExpectedProcesses 2 -LoadOnly:$Load
}
$ok = Evaluate $logs
Assert $ok.Passed 'Healthy load must pass'
Assert ($ok.Summary.unique_joined_bots -eq 4) 'Repeated Actor records must not double the joined count'
$retry = @(BotLog 'a' 1 2; BotLog 'b' 3 2)
$retry[0].Lines = @('! [Lost Zone][bots] nbot_001: connection timed out', '[Lost Zone][bots] nbot_001 retries (1)') + $retry[0].Lines
$retried = Evaluate $retry
Assert ($retried.Passed -and $retried.Summary.admission_retries -eq 1 -and $retried.Summary.terminal_failed -eq 0) 'Recovered admission errors are not terminal'
Assert (-not (Evaluate @()).Passed) 'Missing processes must fail'
$silent = @([pscustomobject]@{Name='a'; Lines=@('Loading...')}, [pscustomobject]@{Name='b'; Lines=@('Loading...')})
Assert (-not (Evaluate $silent).Passed) 'No report / zero joined must fail'
$zero = @([pscustomobject]@{Name='a'; Lines=@('[bots] 2 wanted: 0 playing, 0 joining, 2 connecting, 0 failed;')},
          [pscustomobject]@{Name='b'; Lines=@('[bots] 2 wanted: 0 playing, 0 joining, 2 connecting, 0 failed;')})
Assert (-not (Evaluate $zero).Passed) 'Zero playing with reports must fail'
foreach ($state in @('1 playing, 1 joining, 0 connecting, 0 failed', '1 playing, 0 joining, 0 connecting, 1 failed', '2 playing, 1 joining, 0 connecting, 0 failed')) {
    $bad = @(BotLog 'a' 1 2; BotLog 'b' 3 2)
    $bad[1].Lines += "[bots] 2 wanted: $state;"
    Assert (-not (Evaluate $bad).Passed) "Reject incomplete/inconsistent load state: $state"
}
$duplicate = @(BotLog 'a' 1 2; BotLog 'b' 1 2)
Assert (-not (Evaluate $duplicate).Passed) 'Duplicate bot process login ranges must fail'
foreach ($errorLine in @('FATAL ERROR', 'combine_1.hlsl(39): error X3017: cannot implicitly convert',
        '[Lost Zone] time event error: nil actor', '[Lost Zone] save_state handler failed: nil actor', 'character save failed')) {
    Assert (-not (Evaluate $logs @($errorLine)).Passed) "Reject error record: $errorLine"
}
$transfer = @(BotLog 'a' 1 2; BotLog 'b' 3 2)
$transfer[1].Lines += '[bots] 2 wanted: 1 playing, 1 joining, 0 connecting, 0 failed;'
Assert (Evaluate $transfer @() $false).Passed 'In-flight cluster transfer is allowed after all bots have joined'

# Execute the actual launch loop with a fake Start-Process: no games or filesystem
# mutations. This reproduces the former case-insensitive $botArgs/$BotArgs bug.
$parseErrors = $null; $tokens = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'run-cluster-selftest.ps1'), [ref]$tokens, [ref]$parseErrors)
Assert (-not $parseErrors) 'Harness must parse'
$launchLoop = $ast.Find({ param($node) $node -is [Management.Automation.Language.ForEachStatementAst] -and $node.Condition.Extent.Text -eq '$botMaps' }, $true)
Assert ($null -ne $launchLoop) 'Actual bot launch loop missing'
$script:commands = @()
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, [switch]$PassThru)
    $script:commands += [pscustomobject]@{ Arguments = $ArgumentList; WindowStyle = $WindowStyle }
    [pscustomobject]@{ PriorityClass = 'Normal' }
}
$botMaps = @('k00_marsh'); $BotProcesses = 4; $Bots = 64
$first = 0; $BotArgs = '-dedicated -netcoop_fake_loss=5'; $BotsBelowNormal = $true
$client = 'not-a-real-game.exe'; $Runtime = 'not-a-real-runtime'; $ports = @{k00_marsh=1367}; $processes = @()
. ([scriptblock]::Create($launchLoop.Extent.Text))
Assert ($script:commands.Count -eq 4) 'Four requested bot processes must launch'
for ($i = 0; $i -lt 4; $i++) {
    $command = $script:commands[$i]
    Assert ($command.Arguments -match "-netcoop_bots 16 -netcoop_bots_first $($i*16) -netcoop_bots_addr 127.0.0.1/port=1367") 'Bot ranges and addresses must remain independent'
    Assert (([regex]::Matches($command.Arguments, '-netcoop_bots 16')).Count -eq 1) 'No recursive command-line duplication'
    Assert (([regex]::Matches($command.Arguments, '-dedicated -netcoop_fake_loss=5')).Count -eq 1) 'Custom BotArgs must appear exactly once per process'
    Assert ($command.WindowStyle -eq 'Hidden') 'Load windows must stay hidden'
}
# Non-divisible splits and multiple maps must retain all requested players.
$script:commands = @(); $botMaps = @('k00_marsh', 'l01_escape'); $ports.l01_escape = 1377
$Bots = 5; $BotProcesses = 2; $first = 0; $processes = @()
. ([scriptblock]::Create($launchLoop.Extent.Text))
foreach ($i in 0..3) {
    $count = @(3,2,3,2)[$i]; $offset = @(0,3,5,8)[$i]
    Assert ($script:commands[$i].Arguments -match "-netcoop_bots $count -netcoop_bots_first $offset ") 'Spread splits must conserve bot count and unique ranges'
}
'PASS actual PowerShell harness: independent launch arguments, split ranges, unique joins, missing/zero/terminal/error rejection, admission retries and transfer states'
