@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Checagem pre-feira: diz se este computador esta pronto para o totem.
rem So le - nao muda nada na maquina nem no banco.

set "PY=python-embed\python.exe"
if not exist "%PY%" if exist "instalador\python-embed.zip" (
    call instalador\instalar_python.bat
)
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [FALHA] O Python do jogo nao esta instalado - veja o motivo acima.
    pause
    exit /b 1
)

"%PY%" tools\verificar_totem.py
echo.
pause
