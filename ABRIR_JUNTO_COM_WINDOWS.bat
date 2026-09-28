@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ===========================================================
rem  Faz o quiz abrir sozinho quando o Windows liga.
rem
rem  Para queda de energia ou reinicio do Windows (atualizacao) no meio
rem  da feira: sem isto, o totem volta na area de trabalho e fica assim
rem  ate alguem da equipe perceber. Rode UMA vez em cada computador do
rem  totem. Nao precisa de internet nem de administrador.
rem
rem  O que faz: cria um atalho para o INICIAR_QUIZ.bat DESTA pasta na
rem  pasta "Inicializar" do usuario. Se ja existir um atalho apontando
rem  para outra copia do jogo (outro .zip baixado em outra pasta), ele
rem  passa a apontar para esta. Rodar de novo nesta mesma pasta oferece
rem  remover a abertura automatica.
rem ===========================================================

set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Quiz SDAI.lnk"
set "ALVO=%~dp0INICIAR_QUIZ.bat"

if exist "%ATALHO%" (
    for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO).TargetPath"`) do set "ALVO_ATUAL=%%a"
)

if exist "%ATALHO%" if /i "%ALVO_ATUAL%"=="%ALVO%" (
    echo O quiz ja abre junto com o Windows, a partir desta pasta.
    choice /c SN /m "Quer REMOVER a abertura automatica"
    if errorlevel 2 goto fim
    del /q "%ATALHO%"
    echo [OK] Abertura automatica removida.
    goto fim
)

if exist "%ATALHO%" (
    echo O Windows abria o quiz de outra pasta:
    echo   %ALVO_ATUAL%
    echo Passando a abrir desta pasta...
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO);" ^
    "$s.TargetPath = $env:ALVO;" ^
    "$s.WorkingDirectory = (Split-Path $env:ALVO);" ^
    "$s.WindowStyle = 7;" ^
    "$s.Save()"

if exist "%ATALHO%" (
    echo [OK] Pronto: o quiz vai abrir sozinho sempre que este computador ligar.
) else (
    echo [ERRO] Nao consegui criar o atalho em:
    echo   %ATALHO%
)

:fim
echo.
pause
