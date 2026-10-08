# Evaluate snapshots taken BEFORE stopping the game processes. Admission retry
# messages are diagnostic events; only the last report's failed count is terminal.
function Assert-NetcoopSelftestProcesses {
    param([object[]]$Processes)
    foreach ($process in $Processes) {
        if ($null -eq $process) { throw 'Missing selftest process handle' }
        $process.Refresh()
        if ($process.HasExited) { throw "Selftest process $($process.Id) exited before the end of the run" }
    }
}

function Get-NetcoopSelftestResult {
    param([object[]]$BotLogs, [string[]]$ServerLines, [int]$ExpectedBots,
          [int]$ExpectedProcesses, [switch]$LoadOnly)
    $errors = [Collections.Generic.List[string]]::new()
    $logins = [Collections.Generic.HashSet[string]]::new()
    $allBotLines = @($BotLogs | ForEach-Object { $_.Lines })
    $totals = @{ wanted = 0; playing = 0; joining = 0; connecting = 0; failed = 0 }
    if ($BotLogs.Count -ne $ExpectedProcesses) {
        $errors.Add("Expected $ExpectedProcesses bot logs, found $($BotLogs.Count)")
    }
    foreach ($log in $BotLogs) {
        $last = $null
        foreach ($line in $log.Lines) {
            if ($line -match '\[bots\] (nbot_\d+) plays Actor ') { [void]$logins.Add($Matches[1]) }
            if ($line -match '\[bots\] (\d+) wanted: (\d+) playing, (\d+) joining, (\d+) connecting, (\d+) failed;') {
                $last = @([int]$Matches[1], [int]$Matches[2], [int]$Matches[3], [int]$Matches[4], [int]$Matches[5])
            }
        }
        if ($null -eq $last) { $errors.Add("No bot state report: $($log.Name)"); continue }
        if ($last[0] -ne ($last[1] + $last[2] + $last[3] + $last[4])) {
            $errors.Add("Inconsistent final bot state: $($log.Name)")
        }
        $totals.wanted += $last[0]; $totals.playing += $last[1]
        $totals.joining += $last[2]; $totals.connecting += $last[3]; $totals.failed += $last[4]
    }
    if ($totals.wanted -ne $ExpectedBots) { $errors.Add("Expected $ExpectedBots wanted bots, found $($totals.wanted)") }
    if ($logins.Count -ne $ExpectedBots) { $errors.Add("Expected $ExpectedBots distinct joined bots, found $($logins.Count)") }
    if ($totals.failed) { $errors.Add("Terminal failed bots: $($totals.failed)") }
    if ($LoadOnly -and ($totals.playing -ne $ExpectedBots -or $totals.joining -or $totals.connecting)) {
        $errors.Add("Load test ended with $($totals.playing)/$ExpectedBots playing")
    }
    $allLines = @($ServerLines) + $allBotLines
    $summary = [ordered]@{
        unique_joined_bots = $logins.Count
        final_playing = $totals.playing
        final_joining = $totals.joining
        final_connecting = $totals.connecting
        terminal_failed = $totals.failed
        leaves = @($ServerLines | Select-String '\[cluster\] .* leaves for').Count
        arrivals = @($ServerLines | Select-String '\[cluster\] .* arrived from').Count
        redirects = @($ServerLines | Select-String '\[cluster\] .* is sent to').Count
        refused = @($ServerLines | Select-String '\[cluster\] .*: (not inside|this passage|no server|the character|the server of that map)').Count
        lease_rejects = @($ServerLines | Select-String 'still on another location server').Count
        save_failures = @($ServerLines | Select-String 'character (save failed|commit failed|save refused)|inventory restore incomplete|\[world\] (refusing save|cannot capture (physics prop|breakable object)|cannot clear inactive script snapshot|saving .* failed|incomplete script snapshot|saved .* could not point)').Count
        bot_moves = @($allBotLines | Select-String '\[bots\] .* goes to').Count
        admission_error_events = @($allBotLines | Select-String '! \[Lost Zone\]\[bots\]').Count
        admission_retries = @($allBotLines | Select-String '\[bots\] nbot_\d+ retries').Count
        fatal = @($allLines | Select-String 'FATAL ERROR|Expression\s*:').Count
        shader_errors = @($allLines | Select-String 'error X\d{4}').Count
        script_errors = @($allLines | Select-String 'SCRIPT ERROR|time event error|handler failed').Count
    }
    foreach ($field in @('fatal', 'shader_errors', 'script_errors', 'save_failures')) {
        if ($summary[$field]) { $errors.Add("$field log records: $($summary[$field]) (caught errors may be capped)") }
    }
    [pscustomobject]@{ Summary = $summary; Errors = @($errors); Passed = ($errors.Count -eq 0) }
}
