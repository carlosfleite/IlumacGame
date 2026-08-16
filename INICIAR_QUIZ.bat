@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

rem ===========================================================
rem  Quiz SDAI - Ilumac Fire Show 2026
rem  Inicializador + watchdog do totem.
rem
rem  O totem roda 3 dias sem supervisao tecnica. Este script:
rem   1. so instala dependencias quando faltam (nao exige internet
rem      para ligar o totem no dia do evento);
rem   2. reinicia o quiz sozinho se ele fechar ou travar.
rem ===========================================================

set "PY=.venv\Scripts\python.exe"
set "LOGDIR=logs"
set "LOG=%LOGDIR%\watchdog.log"
set "PARAR=PARAR.flag"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if exist "%PARAR%" del /q "%PARAR%"

echo ========================================
echo  Quiz SDAI - Ilumac Fire Show 2026
echo ========================================
echo.
echo Para encerrar o totem, crie um arquivo chamado PARAR.flag
echo nesta pasta (ou feche esta janela preta).
echo.

rem -----------------------------------------------------------
rem Setup: executado apenas quando falta alguma coisa.
rem A versao anterior rodava "pip install" a cada boot e abortava
rem em caso de erro - sem wifi confiavel na feira, o totem
rem simplesmente nao ligaria.
rem -----------------------------------------------------------

if not exist "%PY%" (
    echo [SETUP] Ambiente virtual ausente. Criando .venv ...
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python 3 nao encontrado no PATH.
        echo Instale o Python e marque "Add Python to PATH".
        pause
        exit /b 1
    )
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

"%PY%" -c "import flask, webview" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Dependencias ausentes. Instalando ... ^(requer internet^)
    "%PY%" -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel instalar as dependencias.
        echo Conecte a internet e rode este arquivo novamente.
        echo IMPORTANTE: faca isso ANTES do evento.
        pause
        exit /b 1
    )
    echo [SETUP] Dependencias instaladas.
)

echo [OK] Ambiente pronto. Iniciando o quiz em tela cheia...
echo.

set /a TENTATIVAS=0

:loop
if exist "%PARAR%" goto fim

echo [%DATE% %TIME%] Iniciando run.py>> "%LOG%"
"%PY%" run.py
set "CODIGO=!ERRORLEVEL!"

if exist "%PARAR%" goto fim

set /a TENTATIVAS+=1
echo [%DATE% %TIME%] run.py encerrou com codigo !CODIGO! - reinicio #!TENTATIVAS!>> "%LOG%"
echo [WATCHDOG] O quiz encerrou (codigo !CODIGO!). Reiniciando... (#!TENTATIVAS!)

set /a RESTO=TENTATIVAS %% 10
if !RESTO!==0 (
    echo [WATCHDOG] Muitos reinicios seguidos. Aguardando 60s.
    echo [%DATE% %TIME%] Backoff de 60s apos !TENTATIVAS! reinicios>> "%LOG%"
    call :esperar 60
) else (
    call :esperar 5
)

goto loop

:fim
echo [%DATE% %TIME%] Watchdog encerrado via PARAR.flag>> "%LOG%"
if exist "%PARAR%" del /q "%PARAR%"
echo.
echo Totem encerrado.
call :esperar 3
exit /b 0

rem -----------------------------------------------------------
rem :esperar <segundos>
rem Caminho absoluto de proposito: se houver outro "timeout" no
rem PATH (o do Git Bash, por exemplo), o comando falha e os
rem reinicios passam a acontecer sem intervalo nenhum, virando
rem um crash loop que consome a CPU do totem.
rem -----------------------------------------------------------
:esperar
"%SystemRoot%\System32\timeout.exe" /t %~1 /nobreak >nul 2>&1
if not errorlevel 1 exit /b 0
rem timeout.exe tambem falha quando a entrada esta redirecionada;
rem ping -n N+1 espera N segundos e nao depende de console.
set /a _PINGS=%~1+1
"%SystemRoot%\System32\ping.exe" -n !_PINGS! 127.0.0.1 >nul 2>&1
exit /b 0
