@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update.ps1" -PackageDirectory "%~dp0."
set "installer_exit_code=%errorlevel%"
pause
exit /b %installer_exit_code%
