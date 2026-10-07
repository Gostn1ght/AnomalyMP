param([Parameter(Mandatory = $true)][string]$ServerScripts)
$ErrorActionPreference = 'Stop'
$scriptsRoot = (Resolve-Path -LiteralPath $ServerScripts).Path
$file = Join-Path $scriptsRoot 'pda.script'
# Byte-preserving decoding: GAMMA script files may contain CP1251 text.
$encoding = [Text.Encoding]::GetEncoding(28591)
$text = $encoding.GetString([IO.File]::ReadAllBytes($file))
$pattern = '(?ms)^function[ \t]+discover_spots[ \t]*\([ \t]*\)[ \t]*\r?\n(?:(?!^function).)*?^[ \t]*local[ \t]+actor[ \t]*=[ \t]*db\.actor[ \t]*(?<newline>\r?\n)'
$match = [regex]::Match($text, $pattern)
if (-not $match.Success) { throw "Expected PDA discovery function missing: $file" }
if ($match.Value -notmatch 'ResetTimeEvent\(0,\s*"ScanForSpots",\s*3\)') {
    throw "Expected PDA timer reset before actor access missing: $file"
}
$guard = 'if not actor then return end -- Lost Zone: no local Actor on dedicated'
$tail = $text.Substring($match.Index + $match.Length)
if ($tail.TrimStart().StartsWith($guard)) { return }
$text = $text.Insert($match.Index + $match.Length, "`t" + $guard + $match.Groups['newline'].Value)
[IO.File]::WriteAllBytes($file, $encoding.GetBytes($text))
Write-Host "Patched dedicated PDA actor guard: $file"
