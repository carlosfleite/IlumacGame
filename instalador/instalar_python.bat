@echo off
rem ===========================================================
rem  Instala o Python do jogo (python-embed\) a partir de
rem  instalador\python-embed.zip. 100% local, sem internet.
rem  Chamado pelo INICIAR_QUIZ.bat e pelo VERIFICAR_TOTEM.bat,
rem  sempre de dentro da pasta do jogo.
rem
rem  Codigo de saida: 0 instalou, 1 falhou, 2 pasta com caminho longo.
rem ===========================================================

rem O Windows nao aceita caminho de arquivo com mais de 260 letras, e o
rem arquivo mais fundo do Python do jogo tem 110 (mais "python-embed\").
rem Com a pasta do jogo num caminho longo (dentro de outras pastas, no
rem OneDrive...), a instalacao quebra no meio. Melhor avisar antes.
set "PASTA_JOGO=%CD%"
set "TAM_PASTA=0"
for /f %%n in ('powershell -NoProfile -Command "$env:PASTA_JOGO.Length"') do set "TAM_PASTA=%%n"
if %TAM_PASTA% GTR 130 (
    echo.
    echo [ERRO] A pasta do jogo esta num caminho longo demais ^(%TAM_PASTA% letras^):
    echo   %PASTA_JOGO%
    echo.
    echo O Windows nao consegue instalar o jogo tao "fundo" nas pastas.
    echo Mova a pasta do jogo para um lugar curto, por exemplo:
    echo   C:\IlumacGame
    echo e de dois cliques de novo neste arquivo.
    echo.
    exit /b 2
)

echo ========================================
echo  Primeira vez do jogo NESTA maquina.
echo  Instalando o Python do totem agora...
echo  ^(100%% local, sem internet - pode levar alguns minutos^)
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Expand-Archive -LiteralPath 'instalador\python-embed.zip' -DestinationPath 'python-embed' -Force -ErrorAction Stop; exit 0 } catch { Write-Host ('   motivo: ' + $_.Exception.Message); exit 1 }"

if errorlevel 1 goto falhou
if not exist "python-embed\python.exe" goto falhou
echo [OK] Python do totem instalado nesta maquina.
echo.
exit /b 0

:falhou
rem Instalacao pela metade atrapalharia a proxima tentativa: apaga.
if exist "python-embed" rmdir /s /q "python-embed"
echo.
echo [ERRO] Nao consegui instalar o Python do jogo.
echo Confira se o arquivo instalador\python-embed.zip veio inteiro
echo ^(baixe o .zip do jogo de novo, se precisar^) e se ha espaco no disco.
echo.
exit /b 1
