@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update.ps1"
set "updater_exit_code=%errorlevel%"
pause
exit /b %updater_exit_code%
