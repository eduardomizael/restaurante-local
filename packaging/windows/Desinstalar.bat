@echo off
setlocal
cd /d "%TEMP%"
rem The whole block is parsed before PowerShell removes this BAT itself.
(
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall.ps1" %*
    if errorlevel 1 (
        echo.
        echo A remocao nao foi concluida. Confira os arquivos informados acima.
        pause
        exit 1
    ) else (
        echo.
        pause
        exit 0
    )
)
