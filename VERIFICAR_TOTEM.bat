@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Checagem pre-feira: diz se este computador esta pronto para o totem.
rem So le - nao muda nada na maquina nem no banco.

set "PY=python-embed\python.exe"

rem python.exe sozinho nao garante que o Python funciona: ja aconteceu
rem de um antivirus apagar so a python311.dll depois da instalacao,
rem deixando o .exe la mas incapaz de abrir. Por isso as duas condicoes.
set "PY_OK="
if exist "%PY%" if exist "python-embed\python311.dll" set "PY_OK=1"

if not defined PY_OK if exist "instalador\python-embed.zip" (
    call instalador\instalar_python.bat
    if exist "%PY%" if exist "python-embed\python311.dll" set "PY_OK=1"
)
if not defined PY_OK set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [FALHA] O Python do jogo nao esta instalado - veja o motivo acima.
    pause
    exit /b 1
)

"%PY%" tools\verificar_totem.py
echo.
pause
