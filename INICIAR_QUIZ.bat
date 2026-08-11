@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Quiz SDAI — Ilumac Fire Show 2026
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3 e marque "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o venv.
        pause
        exit /b 1
    )
)

echo Atualizando dependencias ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERRO] Falha no pip install.
    pause
    exit /b 1
)

echo.
echo Iniciando o quiz em tela cheia...
echo (Feche a janela do jogo para encerrar)
echo.

".venv\Scripts\python.exe" run.py
set EXITCODE=%ERRORLEVEL%

if not %EXITCODE%==0 (
    echo.
    echo [ERRO] O app encerrou com codigo %EXITCODE%.
    pause
)

exit /b %EXITCODE%
