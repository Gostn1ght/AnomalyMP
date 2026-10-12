# Exercise the real Master-Run argv construction, never the master or game.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'netcoop-cluster\netcoop_master_control.ps1')
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testDirectory = Join-Path $temporaryRoot "lz master args $([Guid]::NewGuid().ToString('N'))"
try {
    [IO.Directory]::CreateDirectory($testDirectory) | Out-Null
    $masterDir = $testDirectory
    $masterPython = (Get-Command python -ErrorAction Stop).Source
    $scriptPath = Join-Path $testDirectory 'record argv.py'
    $outPath = Join-Path $testDirectory 'received argv.json'
    [IO.File]::WriteAllText($scriptPath, "import json, sys`nfrom pathlib import Path`nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]), encoding='utf-8')`n")
    $expected = @('space value', 'quote"value', 'trailing\', '', 'C:\Lost Zone\folder\', 'path\"quoted', 'кириллица')
    $code = Master-Run (@($scriptPath, $outPath) + $expected)
    if ($code -ne 0) { throw "Argument fixture exited with $code" }
    $received = @([IO.File]::ReadAllText($outPath) | ConvertFrom-Json)
    if ($received.Count -ne $expected.Count) { throw 'Argument count changed.' }
    for ($index=0; $index -lt $expected.Count; $index++) {
        if ($received[$index] -cne $expected[$index]) { throw "Argument $index changed." }
    }
    Write-Output 'PASS actual Master-Run: folder/argument spaces, quotes, trailing backslashes, empty and Unicode arguments preserved; no game or master launched'
} finally {
    $resolved = [IO.Path]::GetFullPath($testDirectory)
    if (-not $resolved.StartsWith($temporaryRoot,[StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path $resolved -Leaf) -notmatch '^lz master args [a-f0-9]{32}$') { throw 'Unsafe fixture cleanup target.' }
    if ([IO.Directory]::Exists($resolved)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
