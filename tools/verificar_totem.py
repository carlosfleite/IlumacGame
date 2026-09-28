# -*- coding: utf-8 -*-
"""
Checagem pré-feira: roda tudo o que precisa estar certo no computador do
totem e diz, em português, o que está OK e o que falta. Não muda nada na
máquina nem no banco — só lê.

Uso: VERIFICAR_TOTEM.bat (na pasta do jogo), ou
     python-embed\\python.exe tools\\verificar_totem.py
"""
import os
import shutil
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

falhas = []
avisos = []


def ok(msg):
    print("  [OK]    " + msg)


def aviso(msg):
    avisos.append(msg)
    print("  [AVISO] " + msg)


def falha(msg):
    falhas.append(msg)
    print("  [FALHA] " + msg)


print()
print("Checagem do totem - Quiz SDAI")
print("=" * 60)

# 1. Dependências do Python do jogo
try:
    import flask, webview, openpyxl, fpdf  # noqa: F401
    ok("Python do jogo e dependencias instalados (%s)" % sys.version.split()[0])
except ImportError as exc:
    falha("Dependencia faltando: %s - copie a pasta do jogo de novo do pendrive" % exc)

# 2. Janela: WebView2 ou navegador de reserva
try:
    import run
    if run._tem_webview2():
        ok("WebView2 instalado: o jogo abre na janela propria")
    elif run._navegador_kiosk():
        aviso("Sem WebView2: o jogo vai abrir no Edge em modo quiosque (funciona igual)")
    else:
        falha("Sem WebView2 e sem Edge/Chrome: nao ha como abrir o jogo neste computador")
except Exception as exc:
    falha("Nao consegui checar a janela do jogo: %s" % exc)

# 3. Arquivos do jogo
faltando = [
    c for c in (
        "static/css/style.css", "static/fonts/pixellari.woff2",
        "static/fonts/sofiasansextracondensed.woff2", "static/js/deco-mockup.js",
        "static/img/mockup/fundo-abertura.png", "static/img/mockup/mascote.svg",
        "config/questions.json", "config/premios.json",
    ) if not os.path.isfile(os.path.join(BASE, c))
]
if faltando:
    falha("Arquivos do jogo faltando: " + ", ".join(faltando))
else:
    ok("Arquivos de tela, fontes e configuracao presentes")

# 4. Conteúdo: perguntas e prêmios válidos
try:
    import database
    dados = database.carregar_perguntas()
    ativas = sum(1 for p in dados["perguntas"] if p["ativa"])
    if ativas < dados["perguntas_por_partida"]:
        falha("Só %d pergunta(s) ativa(s); a partida precisa de %d" % (ativas, dados["perguntas_por_partida"]))
    else:
        ok("%d perguntas ativas no questions.json" % ativas)
    faixas = database.carregar_premios()
    ok("Premios: " + ", ".join("%d-%d pts %s" % (f["pontos_min"], f["pontos_max"], f["nome"])
                                for f in faixas if f["ativo"]))
except Exception as exc:
    falha("config/*.json com erro: %s" % exc)

# 5. Banco de dados
if os.path.exists(database.DB_PATH):
    if database._integro(database.DB_PATH):
        c = sqlite3.connect(database.DB_PATH)
        n = c.execute("SELECT COUNT(*) FROM participantes").fetchone()[0]
        c.close()
        ok("Banco integro (%d participante(s) cadastrado(s))" % n)
    else:
        aviso("Banco com defeito: ao abrir, o jogo restaura sozinho o ultimo backup")
else:
    ok("Banco ainda nao existe: sera criado na primeira abertura")

# 6. Backups
pasta = database.BACKUP_DIR
backups = sorted(n for n in os.listdir(pasta) if n.startswith("quiz_")) if os.path.isdir(pasta) else []
if backups:
    ok("%d backup(s) em backups\\ - o mais recente: %s" % (len(backups), backups[-1]))
else:
    aviso("Nenhum backup ainda (o primeiro sai quando o jogo abrir)")

pendrives = database._pastas_pendrive()
if pendrives:
    ok("Pendrive de backup conectado: " + ", ".join(pendrives))
else:
    aviso("Nenhum pendrive de backup conectado (pasta %s na raiz do pendrive)" % database.PASTA_PENDRIVE)

# 7. Disco
livre_mb = shutil.disk_usage(BASE).free // (1024 * 1024)
if livre_mb < 200:
    falha("Pouco espaco em disco: %d MB livres" % livre_mb)
else:
    ok("Espaco em disco: %d MB livres" % livre_mb)

# 8. Abertura automática
atalho = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                      "Programs", "Startup", "Quiz SDAI.lnk")
if os.path.exists(atalho):
    ok("O quiz abre sozinho quando o Windows liga")
else:
    aviso("O quiz NAO abre sozinho com o Windows (rode ABRIR_JUNTO_COM_WINDOWS.bat)")

print("=" * 60)
if falhas:
    print("  NAO ESTA PRONTO: %d falha(s) acima precisam ser resolvidas." % len(falhas))
    sys.exit(1)
if avisos:
    print("  PRONTO, com %d aviso(s) - leia acima." % len(avisos))
else:
    print("  TUDO PRONTO para a feira.")
