@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Checagem pre-feira: diz se este computador esta pronto para o totem.
rem So le - nao muda nada na maquina nem no banco.

set "PY=python-embed\python.exe"
if not exist "%PY%" if exist "instalador\python-embed.zip" (
    echo Instalando o Python do jogo nesta maquina ^(sem internet^)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -LiteralPath 'instalador\python-embed.zip' -DestinationPath 'python-embed' -Force"
)
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [FALHA] Python do jogo nao encontrado. Falta instalador\python-embed.zip.
    pause
    exit /b 1
)

"%PY%" tools\verificar_totem.py
echo.
pause
