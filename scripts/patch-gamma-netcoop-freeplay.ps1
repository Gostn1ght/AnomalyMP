param(
    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot
)

$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$scriptPath = Join-Path $runtime 'server\scripts\se_actor.script'
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
    throw "GAMMA server Actor script missing: $scriptPath"
}

$encoding = [System.Text.Encoding]::GetEncoding(28591)
$content = $encoding.GetString([System.IO.File]::ReadAllBytes($scriptPath))
$newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
$marker = 'self.m_registred = true' + $newline + $newline + "`tif not self.start_position_filled then"
$replacement = @(
    'self.m_registred = true',
    '',
    "`t-- Netcoop uses the normal freeplay ALife world and secondary contracts,",
    "`t-- while removing the story chain before the starting SIMBOARD callback.",
    "`tlocal sim = alife()",
    "`tif sim then",
    "`t`tlocal freeplay_info = {",
    "`t`t`t'story_mode_disabled',",
    "`t`t`t'yan_labx16_switcher_1_off', 'yan_labx16_switcher_2_off',",
    "`t`t`t'yan_labx16_switcher_3_off', 'yan_labx16_switcher_primary_off',",
    "`t`t`t'bar_deactivate_radar_done', 'warlab_deactivate_generators_done',",
    "`t`t`t'mortal_sin', 'isg_entered_the_zone'",
    "`t`t}",
    "`t`tfor _, info in ipairs(freeplay_info) do",
    "`t`t`tif not sim:has_info(0, info) then sim:give_info(0, info) end",
    "`t`tend",
    "`tend",
    '',
    "`tif not self.start_position_filled then"
) -join $newline

if ($content.Contains("-- Netcoop uses the normal freeplay ALife world")) {
    Write-Host "Already patched: $scriptPath"
    return
}
if (-not $content.Contains($marker)) {
    throw "Expected GAMMA Actor registration block missing: $scriptPath"
}
[System.IO.File]::WriteAllBytes($scriptPath, $encoding.GetBytes($content.Replace($marker, $replacement)))
Write-Host "Patched freeplay story flags in $scriptPath"
