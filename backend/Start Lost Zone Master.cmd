@echo off
cd /d "%~dp0"
title Lost Zone - master
color 07
if not exist "runtime\config.json" (
    echo Create the private master configuration first. See README.md.
    pause
    exit /b 1
)
python -m lostzone console --config "runtime\config.json"
if errorlevel 1 pause
