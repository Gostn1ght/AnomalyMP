$ErrorActionPreference='Stop'
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installation=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
$buildDir=Join-Path (Split-Path $PSScriptRoot -Parent) '_build\policy-check'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$source=Join-Path $PSScriptRoot 'check-hideout-storage.cpp'
$exe=Join-Path $buildDir 'check-hideout-storage.exe'
$obj=Join-Path $buildDir 'check-hideout-storage.obj'
$batch=Join-Path $buildDir 'compile-storage.cmd'
Set-Content -LiteralPath $batch -Encoding ascii -Value @('@echo off',"call `"$vcvars`" >nul",'if errorlevel 1 exit /b 1',"cl /nologo /EHsc /std:c++17 `"$source`" /Fe:`"$exe`" /Fo:`"$obj`"",'exit /b %errorlevel%')
& cmd /d /c $batch
if ($LASTEXITCODE -ne 0) { throw 'Storage policy compilation failed' }
& $exe
if ($LASTEXITCODE -ne 0) { throw 'Storage policy regression failed' }
$source=Join-Path $PSScriptRoot 'check-hideout-transaction.cpp'
$exe=Join-Path $buildDir 'check-hideout-transaction.exe'
$obj=Join-Path $buildDir 'check-hideout-transaction.obj'
Set-Content -LiteralPath $batch -Encoding ascii -Value @('@echo off',"call `"$vcvars`" >nul",'if errorlevel 1 exit /b 1',"cl /nologo /EHsc /std:c++17 `"$source`" /Fe:`"$exe`" /Fo:`"$obj`"",'exit /b %errorlevel%')
& cmd /d /c $batch
if ($LASTEXITCODE -ne 0) { throw 'Storage transaction compilation failed' }
& $exe
if ($LASTEXITCODE -ne 0) { throw 'Storage transaction regression failed' }
