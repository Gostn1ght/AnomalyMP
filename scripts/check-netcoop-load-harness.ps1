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
foreach ($errorLine in @('FATAL ERROR', 'at address 0x000000014009DAC3', '  at address 0x14009dac3  ',
        '! [X-Ray][exit] world is locked or lock file is inaccessible', '  ! [X-Ray][exit] missing archive',
        'combine_1.hlsl(39): error X3017: cannot implicitly convert',
        '[Lost Zone] time event error: nil actor', '[Lost Zone] save_state handler failed: nil actor', 'character save failed',
        '! [Lost Zone] character commit failed: file.bin', '[Lost Zone] character save refused: inventory tree is incomplete',
        '! [Lost Zone] inventory restore incomplete for actor 123; preserving saved character',
        '! [NetAnomaly][world] incomplete script snapshot test_a; keeping the previous commit',
        '! [NetAnomaly][world] saving test_a failed (periodic) at alife snapshot',
        '! [NetAnomaly][world] cannot capture physics prop 15921',
        '! [NetAnomaly][world] cannot capture physics fragment 32001',
        '! [NetAnomaly][world] cannot capture breakable object 15508',
        '! [NetAnomaly][world] cannot capture destroyable health 15778',
        '! [NetAnomaly][world] refusing save: committed pointer is corrupt/inaccessible',
        '! [NetAnomaly][world] saved test_b but could not point test.current to it')) {
    Assert (-not (Evaluate $logs @($errorLine)).Passed) "Reject error record: $errorLine"
}
Assert (Evaluate $logs @('[Lost Zone][hitch] frame 37 at 109 ms: < 14009dac3',
    '[Lost Zone][sample-profile] self 3.0% LostZoneClientDX11.exe+9dac3',
    '[debug] explanation: at address 0x14009dac3',
    '[debug] describing ! [X-Ray][exit] as an example')).Passed 'Ordinary sampled/debug addresses are not unhandled exceptions'
$transfer = @(BotLog 'a' 1 2; BotLog 'b' 3 2)
$transfer[1].Lines += '[bots] 2 wanted: 1 playing, 1 joining, 0 connecting, 0 failed;'
Assert (Evaluate $transfer @() $false).Passed 'In-flight cluster transfer is allowed after all bots have joined'

function FakeProcess([int]$Id, [bool]$Exited) {
    $p = [pscustomobject]@{Id=$Id; HasExited=$Exited; Refreshed=$false}
    $p | Add-Member -MemberType ScriptMethod -Name Refresh -Value { $this.Refreshed=$true }
    $p
}
$running = @(FakeProcess 1 $false; FakeProcess 2 $false)
Assert-NetcoopSelftestProcesses $running
Assert ($running[0].Refreshed -and $running[1].Refreshed) 'Refresh process state before accepting old reports'
$rejectedExit = $false
try { Assert-NetcoopSelftestProcesses @($running[0], (FakeProcess 2 $true)) } catch { $rejectedExit = $_.Exception.Message -match 'exited before' }
Assert $rejectedExit 'An exited process must fail even with a prior healthy report'

# Execute the actual launch loop with a fake Start-Process: no games or filesystem
# mutations. This reproduces the former case-insensitive $botArgs/$BotArgs bug.
$parseErrors = $null; $tokens = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'run-cluster-selftest.ps1'), [ref]$tokens, [ref]$parseErrors)
Assert (-not $parseErrors) 'Harness must parse'
Assert ($ast.Extent.Text.Contains('Assert-NetcoopSelftestProcesses $processes')) 'Production harness must invoke the process check'
$launchLoop = $ast.Find({ param($node) $node -is [Management.Automation.Language.ForEachStatementAst] -and $node.Condition.Extent.Text -eq '$botMaps' }, $true)
Assert ($null -ne $launchLoop) 'Actual bot launch loop missing'
$script:commands = @()
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, [switch]$PassThru)
    $script:commands += [pscustomobject]@{ Arguments = $ArgumentList; WindowStyle = $WindowStyle; WorkingDirectory = $WorkingDirectory }
    [pscustomobject]@{ PriorityClass = 'Normal' }
}
$botMaps = @('k00_marsh'); $BotProcesses = 4; $Bots = 64
$first = 0; $BotArgs = '-dedicated -netcoop_fake_loss=5'; $BotsBelowNormal = $true
$client = 'not-a-real-game.exe'; $Runtime = 'not-a-real-runtime'; $ports = @{k00_marsh=1367}; $processes = @()
$GameWorkingDirectory = 'gamma-working-directory'; $botFs = 'private/bots.ltx'
. ([scriptblock]::Create($launchLoop.Extent.Text))
Assert ($script:commands.Count -eq 4) 'Four requested bot processes must launch'
for ($i = 0; $i -lt 4; $i++) {
    $command = $script:commands[$i]
    Assert ($command.Arguments -match "-netcoop_bots 16 -netcoop_bots_first $($i*16) -netcoop_bots_addr 127.0.0.1/port=1367") 'Bot ranges and addresses must remain independent'
    Assert (([regex]::Matches($command.Arguments, '-netcoop_bots 16')).Count -eq 1) 'No recursive command-line duplication'
    Assert (([regex]::Matches($command.Arguments, '-dedicated -netcoop_fake_loss=5')).Count -eq 1) 'Custom BotArgs must appear exactly once per process'
    Assert ($command.WindowStyle -eq 'Hidden') 'Load windows must stay hidden'
    Assert ($command.WorkingDirectory -eq $GameWorkingDirectory -and $command.Arguments.Contains('-fsltx private/bots.ltx ')) 'Keep private bot fs config and GAMMA working directory'
}
# Non-divisible splits and multiple maps must retain all requested players.
$script:commands = @(); $botMaps = @('k00_marsh', 'l01_escape'); $ports.l01_escape = 1377
$Bots = 5; $BotProcesses = 2; $first = 0; $processes = @()
. ([scriptblock]::Create($launchLoop.Extent.Text))
foreach ($i in 0..3) {
    $count = @(3,2,3,2)[$i]; $offset = @(0,3,5,8)[$i]
    Assert ($script:commands[$i].Arguments -match "-netcoop_bots $count -netcoop_bots_first $offset ") 'Spread splits must conserve bot count and unique ranges'
}
$serverFunction = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Start-LocationServer'}, $true)
. ([scriptblock]::Create($serverFunction.Extent.Text))
$script:commands = @(); $server = 'not-a-real-server.exe'; $serverFs = 'private/server.ltx'; $maxPlayers = 32; $ServerArgs = ''
$unused = Start-LocationServer 'k00_marsh' 1367 'hidden_base'
Assert ($script:commands[0].WorkingDirectory -eq $GameWorkingDirectory -and $script:commands[0].Arguments.Contains('-fsltx private/server.ltx ')) 'Keep private server fs config and GAMMA working directory'

# Test the production cleanup guard against traversal, ancestor and subtree
# junctions. The junction target itself is private fixture data, never user data.
$cleanupFunction = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-SelftestCleanupPath'}, $true)
. ([scriptblock]::Create($cleanupFunction.Extent.Text))
$fixtureName = 'lostzone-cleanup-' + [Guid]::NewGuid().ToString('N')
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) $fixtureName
$Runtime = Join-Path $fixtureRoot 'runtime'
$private = Join-Path $Runtime 'appdata\selftest'
$sentinel = Join-Path $fixtureRoot 'sentinel'
$junction = Join-Path $private 'outside'
try {
    New-Item -ItemType Directory -Path $private,$sentinel | Out-Null
    Assert-SelftestCleanupPath $private
    $rejected = $false
    try { Assert-SelftestCleanupPath (Join-Path $private '..\..\..\sentinel') } catch { $rejected=$true }
    Assert $rejected 'Reject traversal outside private appdata'
    New-Item -ItemType Junction -Path $junction -Target $sentinel | Out-Null
    foreach ($path in @($private, (Join-Path $junction 'child'))) {
        $rejected=$false
        try { Assert-SelftestCleanupPath $path } catch { $rejected=$true }
        Assert $rejected 'Reject both subtree and ancestor junctions'
    }
}
finally {
    if (Test-Path -LiteralPath $junction) { Remove-Item -LiteralPath $junction -Force }
    $resolvedFixture = [IO.Path]::GetFullPath($fixtureRoot)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolvedFixture.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolvedFixture -Leaf) -ne $fixtureName) { throw 'Unsafe fixture cleanup target' }
    Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
}
'PASS actual PowerShell harness: independent launch arguments, split ranges, unique joins, missing/zero/terminal/error rejection, admission retries and transfer states'
