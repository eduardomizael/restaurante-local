@echo off
setlocal
chcp 65001 >nul
title Restaurante Local
pushd "%~dp0"
if errorlevel 1 goto directory_error

where rtk >nul 2>&1
if errorlevel 1 goto tools_error
if not exist ".venv\Scripts\python.exe" goto environment_error

rtk proxy ".venv\Scripts\python.exe" manage.py run_local %*
set "launcher_exit_code=%errorlevel%"
if not "%launcher_exit_code%"=="0" (
    echo.
    echo Não foi possível iniciar o Restaurante Local. Confira a mensagem acima.
    pause
)
popd
exit /b %launcher_exit_code%

:tools_error
echo Este inicializador de desenvolvimento requer rtk disponível no PATH.
goto failed

:environment_error
echo Ambiente local ausente. Prepare as dependências conforme o README.md.
goto failed

:failed
pause
popd
exit /b 1

:directory_error
echo Não foi possível acessar a pasta do aplicativo.
pause
exit /b 1
