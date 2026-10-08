param(
    [Parameter(Mandatory = $true)][string]$SourceSounds,
    [Parameter(Mandatory = $true)][string]$GameData
)
$ErrorActionPreference='Stop'
# Restore only the missing SSFX sounds. Do not enable a mod/profile or replace
# customized audio. Source OGG content must match the qualified archive manifest.
$sourceRoot=(Resolve-Path -LiteralPath $SourceSounds).Path
$gameDataRoot=(Resolve-Path -LiteralPath $GameData).Path
$soundRoot=Join-Path $gameDataRoot 'sounds/material/human/step'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'fixtures/rain-sounds/sha256.json') -Raw | ConvertFrom-Json
$entries=@($manifest.PSObject.Properties)
if($entries.Count -ne 14){throw 'Expected exactly14 qualified rain sounds'}
$plan=@()
foreach($entry in $entries){
    $name=$entry.Name
    if($name -notmatch '^rain_(0[1-8]|jump_0[1-3]|land_0[1-3])\.ogg$'){throw 'Unexpected sound manifest path'}
    $src=Join-Path $sourceRoot $name
    $dst=Join-Path $soundRoot $name
    if(-not(Test-Path -LiteralPath $src -PathType Leaf)){throw "Missing qualified source sound: $name"}
    if((Get-Item -LiteralPath $src).Length -ne $entry.Value.bytes -or
       (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $entry.Value.sha256){throw "Source sound hash/size mismatch: $name"}
    $exists=Test-Path -LiteralPath $dst
    if($exists -and (-not(Test-Path -LiteralPath $dst -PathType Leaf) -or
       (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash -ne $entry.Value.sha256)){
        throw "Existing custom sound preserved; refusing replacement: $dst"
    }
    $plan+=@{Source=$src;Target=$dst;Exists=$exists;Hash=$entry.Value.sha256}
}
# Validate ALL source/target files before the first mutation. Copy refuses races
# with a newly created target; it never follows an existing file for overwrite.
[void][IO.Directory]::CreateDirectory($soundRoot)
$added=0;$kept=0
foreach($item in $plan){
    if($item.Exists){$kept++;continue}
    [IO.File]::Copy($item.Source,$item.Target,$false)
    if((Get-FileHash -LiteralPath $item.Target -Algorithm SHA256).Hash -ne $item.Hash){throw 'Copied sound integrity failure'}
    $added++
}
Write-Host "Qualified SSFX rain sounds: added=$added already_present=$kept"
