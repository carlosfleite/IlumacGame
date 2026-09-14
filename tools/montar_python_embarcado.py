# -*- coding: utf-8 -*-
"""
Gera o instalador local do Python do jogo: python-embed/ (interpretador +
todas as dependencias, pronto pra usar) e instalador/python-embed.zip (a
mesma coisa compactada).

Uso (uma vez, nesta maquina, com internet e a .venv ja criada):

    .venv\\Scripts\\python tools\\montar_python_embarcado.py

Depois disso, o INICIAR_QUIZ.bat cuida do resto sozinho em qualquer
computador: se python-embed\\ ja existe (mesma maquina do dia anterior),
usa direto; se nao existe (maquina nova, ou pasta so com o essencial),
extrai instalador\\python-embed.zip na hora, sem internet, e so depois
disso roda o jogo. So funciona para Windows 64 bits porque o embeddable
oficial e assim.
"""

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENV_SITE_PACKAGES = BASE_DIR / ".venv" / "Lib" / "site-packages"
DEST = BASE_DIR / "python-embed"
ZIP_INSTALADOR = BASE_DIR / "instalador" / "python-embed.zip"

PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
PY_TAG = f"{sys.version_info.major}{sys.version_info.minor}"
URL_EMBED = (
    f"https://www.python.org/ftp/python/{PY_VERSION}/"
    f"python-{PY_VERSION}-embed-amd64.zip"
)


def main():
    if not VENV_SITE_PACKAGES.exists():
        sys.exit(
            "Nao encontrei .venv\\Lib\\site-packages. Crie a .venv e instale "
            "requirements.txt antes de rodar este script (veja o README)."
        )

    if DEST.exists():
        print(f"[LIMPEZA] Removendo {DEST} anterior...")
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    zip_path = DEST / "_embed.zip"
    print(f"[DOWNLOAD] {URL_EMBED}")
    urllib.request.urlretrieve(URL_EMBED, zip_path)

    print("[EXTRAINDO] Python embarcavel...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(DEST)
    zip_path.unlink()

    pth_file = DEST / f"python{PY_TAG}._pth"
    if not pth_file.exists():
        sys.exit(f"[ERRO] {pth_file.name} nao apareceu no zip baixado.")

    # Liga o site-packages e a pasta do jogo (".."), que o embeddable
    # desliga por padrao (modo isolado). Sem isso "import database" e
    # "import flask" falham mesmo com os arquivos no lugar certo.
    pth_file.write_text(
        f"python{PY_TAG}.zip\n.\n..\nLib\\site-packages\n\nimport site\n",
        encoding="utf-8",
    )

    print("[COPIANDO] site-packages da .venv (pode demorar um pouco)...")
    shutil.copytree(
        VENV_SITE_PACKAGES,
        DEST / "Lib" / "site-packages",
        dirs_exist_ok=True,
    )

    print("[TESTE] Importando as dependencias no Python embarcado...")
    import subprocess

    resultado = subprocess.run(
        [str(DEST / "python.exe"), "-c", "import flask, webview, openpyxl, fpdf"],
        cwd=BASE_DIR,
    )
    if resultado.returncode != 0:
        sys.exit("[ERRO] Python embarcado nao conseguiu importar as dependencias.")

    print("[COMPACTANDO] Gerando instalador\\python-embed.zip...")
    ZIP_INSTALADOR.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_INSTALADOR.exists():
        ZIP_INSTALADOR.unlink()
    caminho_gerado = shutil.make_archive(
        str(ZIP_INSTALADOR.with_suffix("")), "zip", root_dir=DEST
    )
    Path(caminho_gerado).replace(ZIP_INSTALADOR)

    print()
    print("[OK] Prontos: python-embed\\ (pronto pra rodar nesta maquina) e")
    print("instalador\\python-embed.zip (o INICIAR_QUIZ.bat extrai ele sozinho,")
    print("sem internet, em qualquer outra maquina onde python-embed\\ nao")
    print("existir ainda). Copie a pasta do jogo inteira, com os dois, para")
    print("o pendrive.")


if __name__ == "__main__":
    main()
