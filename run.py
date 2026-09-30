# -*- coding: utf-8 -*-
"""
Entrypoint do totem: sobe Flask em thread daemon e abre janela pywebview
em modo kiosk.

Hardware alvo: Dell Inspiron One 2330 (retrato / touch).
Uso: python run.py

Este processo é supervisionado pelo INICIAR_QUIZ.bat, que o reinicia
automaticamente se ele morrer. Por isso, qualquer falha aqui deve
terminar o processo com código != 0 e registrar o motivo no log — não
travar esperando input.
"""

import ctypes
import logging
import logging.handlers
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import flask.cli
import webview

from app import create_app, registrar_fechamento_navegador, registrar_janela
from database import backup_periodico, fazer_backup

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}/"

# Horario local (24h) a partir do qual o backup de fim de dia acontece
# sozinho, sem precisar reiniciar o totem. Ajuste conforme o horario de
# fechamento real da feira.
HORA_BACKUP_FIM_DIA = 21

# A janela do totem abre com ?kiosk=1: e esse parametro que liga o
# travamento de tecla (F5/F11/F12/Ctrl+R) e o reset por inatividade no
# kiosk.js, que grava a marca no localStorage desta instalacao. Quem abre
# o mesmo endereco num navegador comum nao passa por aqui e fica
# destravado, que e o necessario para inspecionar e testar responsividade.
URL_JANELA = URL + "?kiosk=1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PERFIL_NAVEGADOR = os.path.join(LOG_DIR, "perfil-navegador")

# Código de saída que o INICIAR_QUIZ.bat entende como "já tem um totem
# rodando nesta máquina": ele encerra em vez de reabrir em loop.
SAIDA_JA_RODANDO = 3


class _SoOQueImporta(logging.Filter):
    """
    Filtro do CONSOLE. O arquivo de log continua recebendo tudo.

    A janela preta é o que a equipe do estande olha quando desconfia de
    algum problema. Duas fontes de ruído enterravam qualquer coisa útil
    nela:

    1. O log de acesso do Werkzeug é uma linha POR ARQUIVO servido — uma
       única tela do quiz gera ~15 linhas de 200/304. Em três dias de
       feira isso rola a tela sem parar. Aqui passam só 4xx e 5xx, que
       são os que interessam quando algo quebra.
    2. O aviso de "development server". É verdadeiro, mas este servidor
       atende 127.0.0.1 e um único usuário; na janela do estande ele só
       parece defeito e faz alguém ligar achando que quebrou.
    3. "Press CTRL+C to quit", que ensina a coisa errada: quem encerra o
       totem é o PARAR.flag, e um Ctrl+C só faria o watchdog reabrir.
    """

    # '"GET /static/x.png HTTP/1.1" 304 -' — o código vem depois da aspa
    # de fechamento. O 304 chega colorido com ANSI, que fica DENTRO das
    # aspas e por isso não atrapalha. 4xx e 5xx passam de propósito.
    _ACESSO_NORMAL = re.compile(r'" [23]\d\d ')
    _RUIDO = ("This is a development server", "Press CTRL+C to quit")

    def filter(self, record):
        msg = record.getMessage()
        if self._ACESSO_NORMAL.search(msg):
            return False
        return not any(r in msg for r in self._RUIDO)


def _configurar_log():
    """
    Console enxuto, arquivo completo.

    O arquivo rotaciona: com o log de acesso ligado, três dias de feira
    escrevem sem parar, e disco cheio no meio do evento é justamente um
    dos modos de falha que o app trata (ver app.py).
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    arquivo = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "totem.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    console = logging.StreamHandler(sys.stdout)
    console.addFilter(_SoOQueImporta())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[arquivo, console],
    )

    # O banner do Flask fala em "Press CTRL+C to quit", que contradiz a
    # instrução do INICIAR_QUIZ.bat (criar PARAR.flag) — e o watchdog
    # reabriria o totem de qualquer jeito. Melhor não dar a instrução
    # errada para quem está no estande.
    flask.cli.show_server_banner = lambda *a, **kw: None


def _run_flask():
    try:
        flask_app = create_app()
        # use_reloader=False é obrigatório quando Flask roda em thread
        flask_app.run(
            host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False
        )
    except Exception:
        logging.exception("Servidor Flask caiu")
        # Derruba o processo inteiro para o watchdog reiniciar limpo:
        # uma janela aberta contra um servidor morto é pior que reiniciar.
        os._exit(1)


def _esperar_servidor(tentativas=100, intervalo=0.1):
    for _ in range(tentativas):
        try:
            urllib.request.urlopen(URL, timeout=0.3)
            return True
        except Exception:
            time.sleep(intervalo)
    return False


def _vigiar_backups():
    """
    O backup de boot (em database.init_db) cobre reinicios do watchdog,
    mas a feira tem dias inteiros com o totem ligado sem cair. Esta thread
    confere a cada 10 min e:
      - faz o backup da hora, se entrou dado novo (database.backup_periodico);
      - faz o backup de fim de dia assim que passa do horario de
        fechamento, uma vez por dia local.
    Cada backup tambem vai para o pendrive ILUMAC_BACKUP, se conectado.
    """
    while True:
        try:
            backup_periodico()
            if time.localtime().tm_hour >= HORA_BACKUP_FIM_DIA:
                fazer_backup("fim_do_dia")
        except Exception:
            logging.exception("Falha ao tentar o backup automatico")
        time.sleep(600)


def _porta_ocupada():
    """Outro run.py (ou outro programa) ja atende na porta do totem?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, PORT)) == 0


def _manter_tela_ligada():
    """
    Impede o Windows de apagar a tela ou suspender enquanto o jogo roda.
    Vale so enquanto este processo estiver vivo: nao mexe na configuracao
    de energia da maquina (que continua a mesma quando o totem fecha).
    """
    if os.name != "nt":
        return
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
    except Exception:
        logging.exception("Nao consegui impedir a suspensao da tela")


def _tem_webview2():
    """
    Mesmo teste que o pywebview faz para escolher o motor da janela:
    .NET 4.6.2+ e o runtime do WebView2 (Edge) instalado.

    Por que conferir antes: sem o WebView2, o pywebview 5 NAO falha — ele
    cai sozinho para o MSHTML, o motor do Internet Explorer, que nao
    entende o CSS do jogo. A janela abriria com a tela toda quebrada e
    nenhum erro no log.
    """
    if os.name != "nt":
        return True
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full") as k:
            if winreg.QueryValueEx(k, "Release")[0] < 394802:
                return False
    except OSError:
        return False

    chave = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    caminhos = [
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + chave),
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + chave),
        (winreg.HKEY_CURRENT_USER, "SOFTWARE\\" + chave),
    ]
    for raiz, caminho in caminhos:
        try:
            with winreg.OpenKey(raiz, caminho) as k:
                versao = str(winreg.QueryValueEx(k, "pv")[0])
            if int(versao.split(".")[0]) >= 86:
                return True
        except (OSError, ValueError):
            continue
    return False


def _navegador_kiosk():
    """Edge (vem em todo Windows 10/11) ou, na falta dele, o Chrome."""
    candidatos = []
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        candidatos.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
        candidatos.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    for caminho in candidatos:
        if os.path.isfile(caminho):
            return caminho
    return None


def _abrir_no_navegador():
    """
    Plano B da janela: o proprio Edge em modo quiosque (tela cheia, sem
    barra de endereco nem abas). Perfil proprio dentro de logs/ para abrir
    sempre um processo novo — com o perfil padrao, o Edge entregaria a URL
    a uma janela ja aberta e voltaria na hora, e o watchdog reabriria sem
    parar. Espera o navegador fechar para devolver o controle ao watchdog,
    igual a janela do pywebview.
    """
    exe = _navegador_kiosk()
    if not exe:
        logging.error("Sem WebView2 e sem Edge/Chrome nesta maquina: nao ha como abrir o jogo")
        time.sleep(60)  # evita reabrir em loop apertado
        sys.exit(1)

    perfil = PERFIL_NAVEGADOR
    _fechar_navegador_quiosque()
    # A rota do brasão (app.py) fecha esta janela antes de encerrar: sem
    # isso, no modo navegador o Edge ficava aberto em tela cheia com o
    # servidor já morto, e ninguém no estande conseguia sair dele.
    registrar_fechamento_navegador(_fechar_navegador_quiosque)
    logging.warning("Abrindo o jogo em modo quiosque no navegador: %s", exe)
    inicio = time.time()
    processo = subprocess.Popen([
        exe,
        "--kiosk", URL_JANELA,
        "--edge-kiosk-type=fullscreen",
        "--user-data-dir=" + perfil,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
        "--disable-pinch",
        "--overscroll-history-navigation=0",
    ])
    processo.wait()
    if time.time() - inicio < 5:
        # Fechou na hora: o navegador entregou a URL a outra janela e
        # saiu. Espera antes de devolver ao watchdog, para nunca virar um
        # loop de reaberturas a cada 5 s.
        logging.warning("O navegador fechou logo ao abrir; aguardando 30 s antes de tentar de novo")
        time.sleep(30)


def _fechar_navegador_quiosque():
    """
    Fecha os processos do Edge/Chrome que usam o perfil do quiosque (e só
    esse perfil — nunca o navegador pessoal de quem estiver na máquina).

    Por que antes de abrir: se o run.py cair e a janela do navegador ficar
    aberta, um navegador novo com o mesmo perfil só entregaria a URL à
    janela antiga e fecharia na hora; processo.wait() voltaria na mesma
    hora e o watchdog reabriria sem parar, a cada 5 s. Medido no
    cronômetro, que usa o mesmo esquema de perfil.
    """
    if os.name != "nt":
        return
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' or Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($env:QUIZ_PERFIL) } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; 'x' }"
    )
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=20,
            env=dict(os.environ, QUIZ_PERFIL=PERFIL_NAVEGADOR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if resultado.stdout.strip():
            logging.warning("Fechei um navegador do quiosque que tinha ficado aberto")
            time.sleep(1)
    except Exception:
        logging.exception("Nao consegui verificar se ficou navegador do quiosque aberto")


def main():
    _configurar_log()
    logging.info("Iniciando totem — Quiz SDAI")

    # INICIAR_QUIZ.bat aberto duas vezes: o segundo servidor nao subiria
    # (porta em uso), mas a janela dele abriria por cima da do primeiro.
    if _porta_ocupada():
        logging.warning("Ja existe um totem rodando em %s; esta copia vai encerrar", URL)
        sys.exit(SAIDA_JA_RODANDO)

    _manter_tela_ligada()

    server = threading.Thread(target=_run_flask, daemon=True)
    server.start()

    threading.Thread(target=_vigiar_backups, daemon=True).start()

    if not _esperar_servidor():
        logging.error("Servidor Flask nao respondeu a tempo em %s", URL)
        sys.exit(1)

    logging.info("Servidor no ar em %s", URL)

    # "python run.py --navegador" força o plano B, para testar no totem
    # como o jogo fica numa maquina sem WebView2.
    if "--navegador" in sys.argv or not _tem_webview2():
        logging.warning("WebView2 ausente (ou --navegador) - usando o navegador como janela")
        _abrir_no_navegador()
        logging.info("Navegador encerrado — devolvendo o controle ao watchdog")
        return

    # Trava o que o pywebview permite travar no lado da janela.
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

    # frameless=True remove a barra de título: sem botão de fechar e sem
    # arrastar a janela para fora da tela cheia.
    janela = webview.create_window(
        title="Quiz SDAI — Ilumac Fire Show 2026",
        url=URL_JANELA,
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        confirm_close=False,
        text_select=False,
    )
    # A rota /api/totem/encerrar (gesto do brasão, em app.py) usa isso pra
    # fechar a janela direto pelo pywebview em vez de só matar o processo
    # e esperar o Windows perceber — bem mais rápido.
    registrar_janela(janela)
    try:
        webview.start(gui="edgechromium")
    except Exception:
        # WebView2 registrado mas quebrado (atualizacao pela metade, por
        # exemplo): em vez de o watchdog reabrir a mesma falha para sempre,
        # o jogo segue no navegador.
        logging.exception("A janela do pywebview falhou - usando o navegador")
        _abrir_no_navegador()

    logging.info("Janela encerrada — devolvendo o controle ao watchdog")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Falha nao tratada no totem")
        sys.exit(1)
