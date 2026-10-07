param([Parameter(Mandatory = $true)][string]$ServerScripts)
$ErrorActionPreference = 'Stop'
$file = Join-Path (Resolve-Path -LiteralPath $ServerScripts).Path 'itms_manager.script'
$encoding = [Text.Encoding]::GetEncoding(28591)
$text = $encoding.GetString([IO.File]::ReadAllBytes($file))
$pattern = '(?m)^function[ \t]+save_state[ \t]*\([ \t]*m_data[ \t]*\)[^\r\n]*(?<newline>\r?\n)'
$functionMatches = [regex]::Matches($text, $pattern)
if ($functionMatches.Count -ne 1) { throw "Expected one item save function: $file" }
$match = $functionMatches[0]
$tail = $text.Substring($match.Index + $match.Length)
$body = [regex]::Split($tail, '(?m)^function\b')[0]
if (-not $body.Contains('db.actor:inventory_for_each(itr)') -or -not $body.Contains('m_data.bolt_slot = db.actor:item_in_slot(6)')) {
    throw "Unsupported item inventory save function: $file"
}
# This hook stores ONE local player's bolts. A dedicated world save has no
# such actor; leave existing state untouched. Preserve every actor-present path.
$guard = 'if not db.actor then return end -- Lost Zone: no local player inventory in world save'
if ($tail.TrimStart().StartsWith($guard)) { return }
$text = $text.Insert($match.Index + $match.Length, "`t" + $guard + $match.Groups['newline'].Value)
[IO.File]::WriteAllBytes($file, $encoding.GetBytes($text))
Write-Host "Patched dedicated personal item save guard: $file"
