@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\windows\Update.ps1" -Source %*
set "installer_exit_code=%errorlevel%"
pause
exit /b %installer_exit_code%
