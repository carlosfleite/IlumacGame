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

import logging
import logging.handlers
import os
import re
import sys
import threading
import time
import urllib.request

import flask.cli
import webview

from app import create_app

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}/"

# A janela do totem abre com ?kiosk=1: e esse parametro que liga o
# travamento de tecla (F5/F11/F12/Ctrl+R) e o reset por inatividade no
# kiosk.js, que grava a marca no localStorage desta instalacao. Quem abre
# o mesmo endereco num navegador comum nao passa por aqui e fica
# destravado, que e o necessario para inspecionar e testar responsividade.
URL_JANELA = URL + "?kiosk=1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")


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


def main():
    _configurar_log()
    logging.info("Iniciando totem — Quiz SDAI")

    server = threading.Thread(target=_run_flask, daemon=True)
    server.start()

    if not _esperar_servidor():
        logging.error("Servidor Flask nao respondeu a tempo em %s", URL)
        sys.exit(1)

    logging.info("Servidor no ar em %s", URL)

    # Trava o que o pywebview permite travar no lado da janela.
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

    # frameless=True remove a barra de título: sem botão de fechar e sem
    # arrastar a janela para fora da tela cheia.
    webview.create_window(
        title="Quiz SDAI — Ilumac Fire Show 2026",
        url=URL_JANELA,
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        confirm_close=False,
        text_select=False,
    )
    webview.start()

    logging.info("Janela encerrada — devolvendo o controle ao watchdog")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Falha nao tratada no totem")
        sys.exit(1)
