@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\Build-Windows.ps1" %*
set "BUILD_RESULT=%ERRORLEVEL%"
if "%BUILD_RESULT%"=="0" (
    echo.
    echo Pacotes gerados. Consulte a pasta dist e dist\build-report.json.
) else (
    echo.
    echo Empacotamento interrompido. Confira a mensagem acima e o log em build\logs.
)
pause
exit /b %BUILD_RESULT%
