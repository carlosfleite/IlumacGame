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
import os
import sys
import threading
import time
import urllib.request

import webview

from app import create_app

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")


def _configurar_log():
    """Log em arquivo: no totem não há console para ler o traceback."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(LOG_DIR, "totem.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


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
        url=URL,
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
