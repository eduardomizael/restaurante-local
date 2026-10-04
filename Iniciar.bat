@echo off
setlocal
set "launcher_update_attempted="
chcp 65001 >nul
title Restaurante Local
pushd "%~dp0"
if errorlevel 1 goto directory_error

where rtk >nul 2>&1
if errorlevel 1 goto tools_error
if not exist ".venv\Scripts\python.exe" goto environment_error

:start_application
rtk proxy ".venv\Scripts\python.exe" manage.py run_local %*
set "launcher_exit_code=%errorlevel%"
if "%launcher_exit_code%"=="3" goto offer_update
if not "%launcher_exit_code%"=="0" (
    echo.
    echo Não foi possível iniciar o Restaurante Local. Confira a mensagem acima.
    pause
)
goto finished

:offer_update
if defined launcher_update_attempted goto update_unresolved
echo.
echo Os dados locais precisam ser preparados ou atualizados antes de iniciar.
choice /C SN /N /M "Executar a atualizacao com backup e depois iniciar? [S/N] "
if errorlevel 2 goto update_declined
if errorlevel 1 goto perform_update
goto update_declined

:perform_update
set "launcher_update_attempted=1"
rtk proxy ".venv\Scripts\python.exe" manage.py initialize_local
set "launcher_exit_code=%errorlevel%"
if not "%launcher_exit_code%"=="0" goto update_failed
echo.
echo Atualizacao concluida. Iniciando o Restaurante Local...
goto start_application

:update_declined
echo Atualizacao cancelada. Nenhum dado foi alterado pelo atualizador.
goto finished

:update_failed
echo.
echo Nao foi possivel atualizar os dados. A aplicacao nao sera iniciada.
echo Confira a mensagem acima.
pause
goto finished

:update_unresolved
echo.
echo O banco continua exigindo atualizacao. Confira a mensagem acima.
pause
goto finished

:finished
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
