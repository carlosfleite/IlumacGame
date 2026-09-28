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
rem  O que faz: cria um atalho para o INICIAR_QUIZ.bat na pasta
rem  "Inicializar" do usuario. Para desfazer, rode de novo e escolha
rem  remover (ou apague o atalho "Quiz SDAI" nessa pasta).
rem ===========================================================

set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Quiz SDAI.lnk"

if exist "%ATALHO%" (
    echo O quiz ja abre junto com o Windows neste computador.
    choice /c SN /m "Quer REMOVER a abertura automatica"
    if errorlevel 2 goto fim
    del /q "%ATALHO%"
    echo [OK] Abertura automatica removida.
    goto fim
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%ATALHO%');" ^
    "$s.TargetPath = '%~dp0INICIAR_QUIZ.bat';" ^
    "$s.WorkingDirectory = '%~dp0';" ^
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
