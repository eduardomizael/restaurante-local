@echo off
setlocal
chcp 65001 >nul
title Preparar ou atualizar Restaurante Local
pushd "%~dp0"
if errorlevel 1 goto directory_error

if not exist ".venv\Scripts\python.exe" goto environment_error

echo Preparação ou atualização do banco local. O aplicativo deve estar fechado.
".venv\Scripts\python.exe" manage.py initialize_local %*
set "launcher_exit_code=%errorlevel%"
echo.
if "%launcher_exit_code%"=="0" (
    echo Comando concluído. Confira o resultado acima.
) else (
    echo Não foi possível preparar ou atualizar os dados. Confira a mensagem acima.
)
pause
popd
exit /b %launcher_exit_code%

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
