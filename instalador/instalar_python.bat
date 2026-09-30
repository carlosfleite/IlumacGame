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
rem
rem ATENCAO: nunca escreva %PASTA_JOGO% (ou outro caminho) SEM ASPAS dentro
rem de um bloco "if (...)". Pasta com parenteses no nome, como
rem "IlumacGame(versaoFinal)", fecha o bloco antes da hora: o cmd da erro
rem de sintaxe e a janela some sem mostrar nada (caso real no cronometro).
set "PASTA_JOGO=%CD%"
set "TAM_PASTA=0"
for /f %%n in ('powershell -NoProfile -Command "$env:PASTA_JOGO.Length"') do set "TAM_PASTA=%%n"
if %TAM_PASTA% GTR 130 goto caminho_longo
goto extrair

:caminho_longo
echo.
echo [ERRO] A pasta do jogo esta num caminho longo demais (%TAM_PASTA% letras):
echo   "%PASTA_JOGO%"
echo.
echo O Windows nao consegue instalar o jogo tao "fundo" nas pastas.
echo Mova a pasta do jogo para um lugar curto, por exemplo:
echo   C:\IlumacGame
echo e de dois cliques de novo neste arquivo.
echo.
exit /b 2

:extrair

echo ========================================
echo  Primeira vez do jogo NESTA maquina.
echo  Instalando o Python do totem agora...
echo  ^(100%% local, sem internet^)
echo ========================================
echo.

rem O zip tem quase 4 mil arquivos pequenos (o Python inteiro, DLLs e
rem tudo). Expand-Archive do PowerShell processa arquivo por arquivo e
rem levava mais de um minuto nisso sozinho - e essa espera "sem dar
rem sinal de vida" e o que mais parece que o instalador travou. tar.exe
rem (nativo desde o Windows 10 de 2018) extrai o mesmo zip em segundos.
rem So cai pro Expand-Archive se por algum motivo o tar nao existir
rem nesta maquina (Windows bem antigo ou instalacao customizada).
set "TAR_EXE=%WINDIR%\System32\tar.exe"
if not exist "python-embed" mkdir "python-embed"

if exist "%TAR_EXE%" (
    "%TAR_EXE%" -xf "instalador\python-embed.zip" -C "python-embed"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { Expand-Archive -LiteralPath 'instalador\python-embed.zip' -DestinationPath 'python-embed' -Force -ErrorAction Stop; exit 0 } catch { Write-Host ('   motivo: ' + $_.Exception.Message); exit 1 }"
)

if errorlevel 1 goto falhou

rem O Expand-Archive pode "dar certo" e mesmo assim faltar arquivo: um
rem antivirus que apaga so a DLL depois de extrair (caso real ja visto
rem numa maquina nova) nao faz o PowerShell retornar erro nenhum. Sem
rem conferir python311.dll tambem, o jogo ficava marcado como instalado
rem com um Python que nao roda - so quebrava na hora de abrir de verdade.
if not exist "python-embed\python.exe" goto falhou
if not exist "python-embed\python311.dll" goto falhou
echo [OK] Python do totem instalado nesta maquina.
echo.
exit /b 0

:falhou
rem Instalacao pela metade atrapalharia a proxima tentativa: apaga.
if exist "python-embed" rmdir /s /q "python-embed"
echo.
echo [ERRO] Nao consegui instalar o Python do jogo.
echo Confira se o arquivo instalador\python-embed.zip veio inteiro
echo ^(baixe o .zip do jogo de novo, se precisar^), se ha espaco no disco
echo e se o antivirus desta maquina nao apagou algum arquivo da pasta
echo "python-embed" logo depois da instalacao ^(confira o historico de
echo protecao/itens em quarentena dele^).
echo.
exit /b 1
