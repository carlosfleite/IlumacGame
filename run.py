# -*- coding: utf-8 -*-
"""
Entrypoint do totem: sobe Flask em thread daemon e abre janela pywebview fullscreen.

Hardware alvo: Dell Inspiron One 2330 (retrato / touch).
Uso: python run.py
"""

import sys
import threading
import time

import webview

from app import create_app

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}/"


def _run_flask():
    flask_app = create_app()
    # use_reloader=False é obrigatório quando Flask roda em thread
    flask_app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)


def main():
    server = threading.Thread(target=_run_flask, daemon=True)
    server.start()

    # Espera o servidor responder antes de abrir a janela
    import urllib.request

    for _ in range(50):
        try:
            urllib.request.urlopen(URL, timeout=0.3)
            break
        except Exception:
            time.sleep(0.1)
    else:
        print("Falha ao iniciar o servidor Flask.", file=sys.stderr)
        sys.exit(1)

    # Janela nativa Edge WebView2 — fullscreen, sem chrome do navegador
    webview.create_window(
        title="Quiz SDAI — Ilumac Fire Show 2026",
        url=URL,
        fullscreen=True,
        frameless=False,
        easy_drag=False,
        confirm_close=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
