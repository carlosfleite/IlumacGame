# -*- coding: utf-8 -*-
"""
Rotas Flask do Quiz SDAI — Ilumac Fire Show 2026.
App local single-user (totem); estado da tentativa fica em memória.
"""

import logging
import random
import re
import threading
import time
from flask import Flask, jsonify, render_template, request

from database import (
    ConfiguracaoInvalida,
    FILTRO_TENTATIVAS_GERAL,
    FILTRO_TENTATIVAS_HOJE,
    buscar_premio_por_pontos,
    get_connection,
    init_db,
    sql_melhor_tentativa,
)
from admin import admin_bp

app = Flask(__name__)
app.register_blueprint(admin_bp)
log = logging.getLogger(__name__)


@app.errorhandler(Exception)
def _erro_json(exc):
    """
    Qualquer exceção não tratada em /api/ vira JSON, nunca a página HTML
    padrão do Flask. O totem roda 3 dias sem supervisão: se o banco travar
    ou o disco encher, o participante precisa ver uma mensagem que o
    frontend consegue interpretar (fetch().then(res => res.json())) em vez
    de um SyntaxError ao tentar parsear HTML como JSON — travando a tela
    sem nenhuma saída.
    """
    codigo = getattr(exc, "code", 500) or 500
    if codigo == 500:
        log.exception("Erro nao tratado em %s", request.path)
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "erro": "Erro interno do servidor."}), codigo
    return exc if codigo != 500 else ("Erro interno do servidor.", 500)

# Estado da sessão atual do totem (uma pessoa por vez).
# Chave: participante_id → dict com perguntas, respostas bufferizadas, etc.
_sessao_lock = threading.Lock()
_sessoes = {}

# Quem começa o quiz e abandona o totem sem finalizar nunca limpa a
# própria sessão. Numa feira de 3 dias isso acumula sem teto. Cada nova
# tentativa varre e descarta sessões mais velhas que isto — tempo generoso
# porque uma pessoa parada lendo as perguntas não pode ser confundida com
# abandono.
_SESSAO_TTL_S = 30 * 60


def _descartar_sessoes_expiradas():
    """Chamado sempre com _sessao_lock já adquirido."""
    limite = time.time() - _SESSAO_TTL_S
    expiradas = [pid for pid, s in _sessoes.items() if s["criada_em"] < limite]
    for pid in expiradas:
        del _sessoes[pid]

# Preenchidos por create_app() a partir do config/questions.json. Os valores
# aqui são só o fallback de quem roda `python app.py` sem passar pelo factory.
PONTOS_POR_ACERTO = 2
QTD_PERGUNTAS = 5

# Mensagem de config fatal (ex.: poucas perguntas ativas). Setado só na
# inicialização; enquanto não-None, todas as rotas ficam bloqueadas com um
# aviso legível em vez de deixar o watchdog reiniciar o processo em loop
# infinito sem nada visível na tela do totem.
_erro_fatal = None


def _aplicar_config(config):
    global PONTOS_POR_ACERTO, QTD_PERGUNTAS
    PONTOS_POR_ACERTO = config["pontos_por_acerto"]
    QTD_PERGUNTAS = config["perguntas_por_partida"]


@app.before_request
def _bloquear_se_config_invalida():
    # /admin não depende de questions.json/premios.json (só lê participantes
    # e tentativas já gravadas) — não faz sentido travar o acesso do
    # marketing aos dados de contato por causa de um erro de conteúdo do
    # quiz que não tem nada a ver com isso.
    if not _erro_fatal or request.path.startswith(("/static/", "/admin")):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "erro": _erro_fatal}), 503
    return (
        "<h1>Quiz indisponível</h1>"
        "<p>Configuração inválida: %s</p>"
        "<p>Corrija config/questions.json ou config/premios.json "
        "e reinicie o totem.</p>" % _erro_fatal,
        503,
    )


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.route("/")
def pagina_abertura():
    # Tela de abertura = estado de repouso do totem. kiosk.js volta pra cá
    # (URL_REPOUSO = "/") depois de qualquer reset por inatividade ou fim
    # de partida — por isso não leva data-kiosk-timeout: ela já é o descanso.
    return render_template("abertura.html")


@app.route("/cadastro")
def pagina_cadastro():
    return render_template("cadastro.html")


@app.route("/regras")
def pagina_regras():
    # O pid vai para o template para o botão "Começar" ser um <a href> real.
    # Antes ele dependia de um listener de clique em JS; num totem, navegação
    # essencial não pode depender disso — se o script falhar ou o evento não
    # chegar, o participante fica preso na tela sem saída.
    return render_template("regras.html", pid=request.args.get("pid", type=int))


@app.route("/quiz")
def pagina_quiz():
    return render_template("quiz.html")


@app.route("/resultado")
def pagina_resultado():
    return render_template("resultado.html")


@app.route("/ranking")
def pagina_ranking():
    return render_template("ranking.html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

_RE_NOME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .-]+$")
_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


def _validar_cadastro(nome, telefone, email):
    """
    Espelha a validação do cadastro.js. Roda no servidor porque o
    navegador é do participante: com o teclado wireless do estande dá para
    abrir o devtools e postar direto na API. Dado sujo aqui contamina a
    base de captação que o marketing vai usar depois da feira.

    Devolve (mensagem_de_erro, telefone_normalizado) — erro None se ok.
    """
    if not nome:
        return "Nome é obrigatório.", None
    if len(nome) > 80:
        return "Nome muito longo.", None
    partes = [p for p in nome.split(" ") if p]
    if len(partes) < 2:
        return "Informe nome e sobrenome.", None
    curtas = [p for p in partes if len(p) < 2]
    if len(curtas) == len(partes):
        return "Informe nome e sobrenome.", None
    if not _RE_NOME.match(nome):
        return "Use apenas letras no nome.", None

    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) < 10 or len(digitos) > 11:
        return "Telefone inválido — use DDD + número.", None
    if not 11 <= int(digitos[:2]) <= 99:
        return "DDD inválido.", None
    if len(digitos) == 11 and digitos[2] != "9":
        return "Celular deve começar com 9 após o DDD.", None

    if not email:
        return "E-mail é obrigatório.", None
    if len(email) > 120 or not _RE_EMAIL.match(email):
        return "E-mail inválido.", None

    # grava sempre no mesmo formato, independente do que o cliente mandou
    if len(digitos) == 11:
        formatado = "(%s) %s-%s" % (digitos[:2], digitos[2:7], digitos[7:])
    else:
        formatado = "(%s) %s-%s" % (digitos[:2], digitos[2:6], digitos[6:])
    return None, formatado


@app.route("/api/cadastro", methods=["POST"])
def api_cadastro():
    data = request.get_json(silent=True) or {}
    nome = " ".join((data.get("nome") or "").split())
    email = (data.get("email") or "").strip().lower()
    telefone = (data.get("telefone") or "").strip()
    consentimento = 1 if data.get("consentimento_lgpd") else 0

    erro, telefone_fmt = _validar_cadastro(nome, telefone, email)
    if erro:
        return jsonify({"ok": False, "erro": erro}), 400
    if not consentimento:
        return jsonify({"ok": False, "erro": "Consentimento LGPD é obrigatório."}), 400

    conn = get_connection()
    try:
        # Mesma pessoa jogando de novo (fila deu volta, celular emprestado
        # etc.) não pode virar um segundo lead na lista de marketing. O
        # e-mail já é normalizado para minúsculo acima, então "T@T.COM" e
        # "t@t.com" caem aqui.
        existente = conn.execute(
            "SELECT id FROM participantes WHERE lower(email) = ?", (email,)
        ).fetchone()
        if existente:
            participante_id = existente["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO participantes
                    (nome, email, telefone, consentimento_lgpd)
                VALUES (?, ?, ?, ?)
                """,
                (nome, email, telefone_fmt, consentimento),
            )
            conn.commit()
            participante_id = cur.lastrowid
    finally:
        conn.close()

    return jsonify({"ok": True, "participante_id": participante_id})


def _sortear_perguntas(rows, quantidade):
    """
    Sorteio estratificado por dificuldade: revezar entre os grupos
    (iniciante/intermediaria/dificil/geral) embaralhados, em vez de um
    random.sample() puro sobre o total.

    Um sorteio uniforme, por puro azar, pode devolver 5 perguntas fáceis
    de vez em quando — aí a fila inteira começa a comparar respostas
    daquela combinação específica. Revezar os grupos espalha a exposição
    de forma mais pareja entre o banco inteiro, dificultando decoreba
    coletiva no estande. A ordem dos grupos também é embaralhada a cada
    partida, para nenhum grupo ser sistematicamente "o primeiro".
    """
    grupos = {}
    for row in rows:
        grupos.setdefault(row["dificuldade"] or "geral", []).append(row)
    for lista in grupos.values():
        random.shuffle(lista)

    ordem_grupos = list(grupos.keys())
    random.shuffle(ordem_grupos)

    selecionadas = []
    indices = {g: 0 for g in ordem_grupos}
    avancou = True
    while len(selecionadas) < quantidade and avancou:
        avancou = False
        for g in ordem_grupos:
            if len(selecionadas) >= quantidade:
                break
            i = indices[g]
            if i < len(grupos[g]):
                selecionadas.append(grupos[g][i])
                indices[g] = i + 1
                avancou = True
    return selecionadas


@app.route("/api/quiz/iniciar", methods=["GET"])
def api_quiz_iniciar():
    """Sorteia 5 perguntas ativas e devolve sem revelar a correta."""
    participante_id = request.args.get("participante_id", type=int)
    if not participante_id:
        return jsonify({"ok": False, "erro": "participante_id obrigatório."}), 400

    conn = get_connection()
    try:
        part = conn.execute(
            "SELECT id FROM participantes WHERE id = ?", (participante_id,)
        ).fetchone()
        if not part:
            return jsonify({"ok": False, "erro": "Participante não encontrado."}), 404

        rows = conn.execute(
            """
            SELECT id, texto, alt_a, alt_b, alt_c, alt_d, correta, dificuldade
            FROM quiz_perguntas
            WHERE ativa = 1
            """
        ).fetchall()
    finally:
        conn.close()

    if len(rows) < QTD_PERGUNTAS:
        return jsonify({
            "ok": False,
            "erro": f"É necessário ter ao menos {QTD_PERGUNTAS} perguntas ativas.",
        }), 500

    selecionadas = _sortear_perguntas(rows, QTD_PERGUNTAS)

    # Guarda gabarito só no servidor
    gabarito = {}
    perguntas_cliente = []
    for row in selecionadas:
        gabarito[row["id"]] = row["correta"]
        perguntas_cliente.append({
            "id": row["id"],
            "texto": row["texto"],
            "alt_a": row["alt_a"],
            "alt_b": row["alt_b"],
            "alt_c": row["alt_c"],
            "alt_d": row["alt_d"],
        })

    with _sessao_lock:
        _descartar_sessoes_expiradas()
        _sessoes[participante_id] = {
            "gabarito": gabarito,
            "ordem_ids": [p["id"] for p in perguntas_cliente],
            "respostas": [],  # buffer até finalizar
            "respondidas": set(),
            "criada_em": time.time(),
        }

    return jsonify({
        "ok": True,
        "pontos_por_acerto": PONTOS_POR_ACERTO,
        "perguntas": perguntas_cliente,
    })


@app.route("/api/quiz/responder", methods=["POST"])
def api_quiz_responder():
    """
    Valida resposta, registra tempo individual e devolve feedback do Ilumaquinho.
    Mensagens:
      acerto → "Ih, deu bom!"
      erro   → "Ih, deu ruim!"
    """
    data = request.get_json(silent=True) or {}
    resposta_dada = (data.get("resposta_dada") or "").strip().lower()
    tempo_resposta_ms = data.get("tempo_resposta_ms")

    try:
        participante_id = int(data.get("participante_id"))
        pergunta_id = int(data.get("pergunta_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados incompletos."}), 400
    if resposta_dada not in ("a", "b", "c", "d"):
        return jsonify({"ok": False, "erro": "Resposta inválida."}), 400
    try:
        tempo_resposta_ms = int(tempo_resposta_ms)
        if tempo_resposta_ms < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "tempo_resposta_ms inválido."}), 400

    with _sessao_lock:
        sessao = _sessoes.get(participante_id)
        if not sessao:
            return jsonify({"ok": False, "erro": "Sessão de quiz não iniciada."}), 400
        if pergunta_id not in sessao["gabarito"]:
            return jsonify({"ok": False, "erro": "Pergunta fora desta tentativa."}), 400
        if pergunta_id in sessao["respondidas"]:
            return jsonify({"ok": False, "erro": "Pergunta já respondida."}), 400

        correta = sessao["gabarito"][pergunta_id]
        acertou = 1 if resposta_dada == correta else 0
        sessao["respondidas"].add(pergunta_id)
        sessao["respostas"].append({
            "pergunta_id": pergunta_id,
            "resposta_dada": resposta_dada,
            "acertou": acertou,
            "tempo_resposta_ms": tempo_resposta_ms,
        })

    if acertou:
        mensagem = "Ih, deu bom!"
        feedback = "bom"
    else:
        mensagem = "Ih, deu ruim!"
        feedback = "ruim"

    return jsonify({
        "ok": True,
        "acertou": bool(acertou),
        "mensagem": mensagem,
        "feedback": feedback,
        "pontos": PONTOS_POR_ACERTO if acertou else 0,
    })


@app.route("/api/quiz/finalizar", methods=["POST"])
def api_quiz_finalizar():
    """Grava tentativa + respostas, calcula prêmio e limpa sessão."""
    data = request.get_json(silent=True) or {}
    pontuacao = data.get("pontuacao")
    tempo_total_ms = data.get("tempo_total_ms")

    try:
        participante_id = int(data.get("participante_id"))
        pontuacao = int(pontuacao)
        tempo_total_ms = int(tempo_total_ms)
        if pontuacao < 0 or tempo_total_ms < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados inválidos."}), 400

    # A sessão é consumida (deletada) aqui dentro do MESMO lock que confirma
    # que ela existe e está completa — não em dois passos separados. Um
    # segundo POST concorrente para o mesmo participante (retry de rede,
    # duplo toque na tela) precisa encontrar a sessão já vazia e cair no
    # "não iniciada" abaixo, em vez de gravar a mesma tentativa duas vezes
    # no ranking.
    with _sessao_lock:
        sessao = _sessoes.get(participante_id)
        if not sessao:
            return jsonify({"ok": False, "erro": "Sessão de quiz não iniciada."}), 400
        respostas = list(sessao["respostas"])
        total_perguntas = len(sessao["ordem_ids"])
        if len(respostas) < total_perguntas:
            return jsonify({
                "ok": False,
                "erro": "Quiz incompleto — responda todas as perguntas antes de finalizar.",
            }), 400
        del _sessoes[participante_id]

    # Recalcula pontuação no servidor (fonte da verdade)
    pontuacao_srv = sum(r["acertou"] for r in respostas) * PONTOS_POR_ACERTO
    tempo_srv = sum(r["tempo_resposta_ms"] for r in respostas)

    conn = get_connection()
    try:
        premio = buscar_premio_por_pontos(conn, pontuacao_srv)
        premio_id = premio["id"] if premio else None

        cur = conn.execute(
            """
            INSERT INTO quiz_tentativas
                (participante_id, pontuacao, tempo_total_ms, premio_id)
            VALUES (?, ?, ?, ?)
            """,
            (participante_id, pontuacao_srv, tempo_srv, premio_id),
        )
        tentativa_id = cur.lastrowid

        for r in respostas:
            conn.execute(
                """
                INSERT INTO quiz_respostas
                    (tentativa_id, pergunta_id, resposta_dada, acertou, tempo_resposta_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tentativa_id,
                    r["pergunta_id"],
                    r["resposta_dada"],
                    r["acertou"],
                    r["tempo_resposta_ms"],
                ),
            )
        conn.commit()

        part = conn.execute(
            "SELECT nome FROM participantes WHERE id = ?", (participante_id,)
        ).fetchone()
    finally:
        conn.close()

    return jsonify({
        "ok": True,
        "tentativa_id": tentativa_id,
        "participante_id": participante_id,
        "nome": part["nome"] if part else "",
        "pontuacao": pontuacao_srv,
        "tempo_total_ms": tempo_srv,
        # cliente pode ter enviado valores; servidor manda o oficial
        "cliente_pontuacao": pontuacao,
        "cliente_tempo_total_ms": tempo_total_ms,
        "premio": {
            "id": premio["id"] if premio else None,
            "nome": premio["nome"] if premio else "Sem prêmio",
            "descricao": premio["descricao"] if premio else "",
        },
    })


@app.route("/api/ranking", methods=["GET"])
def api_ranking():
    """
    Ranking: pontuação DESC; empate (mesma pontuação) → menor tempo ASC.
    Quem tem pontuações diferentes não compete por tempo.

    ?escopo=dia devolve só as melhores tentativas de hoje; qualquer outro
    valor (ou ausência do parâmetro) devolve o acumulado dos 3 dias.
    """
    limite = request.args.get("limite", default=20, type=int)
    if limite < 1:
        limite = 20
    if limite > 100:
        limite = 100

    escopo = "dia" if request.args.get("escopo") == "dia" else "geral"
    filtro = FILTRO_TENTATIVAS_HOJE if escopo == "dia" else FILTRO_TENTATIVAS_GERAL
    sql_melhor = sql_melhor_tentativa(filtro)

    conn = get_connection()
    try:
        # Entre participantes: ORDER BY pontuacao DESC, tempo ASC (tempo só
        # desempata quem tem a MESMA pontuação).
        rows = conn.execute(
            """
            SELECT
                p.nome,
                best.pontuacao,
                best.tempo_total_ms,
                best.data_hora,
                pr.nome AS premio_nome
            FROM (%s) best
            JOIN participantes p ON p.id = best.participante_id
            LEFT JOIN quiz_premios pr ON pr.id = best.premio_id
            ORDER BY best.pontuacao DESC, best.tempo_total_ms ASC
            LIMIT ?
            """ % sql_melhor,
            (limite,),
        ).fetchall()

        ranking = []
        for i, row in enumerate(rows, start=1):
            ranking.append({
                "posicao": i,
                "nome": row["nome"],
                "pontuacao": row["pontuacao"],
                "tempo_total_ms": row["tempo_total_ms"],
                "premio_nome": row["premio_nome"] or "",
                "data_hora": row["data_hora"],
            })
    finally:
        conn.close()

    return jsonify({"ok": True, "ranking": ranking, "escopo": escopo})


# Exportação de dados para o marketing mora em admin.py, atrás de login
# (blueprint registrado lá em cima) — não fica mais aqui sem autenticação.


def create_app():
    """
    Factory usada pelo run.py.

    Config inválida (ex.: menos perguntas ativas do que a partida precisa)
    não pode derrubar o processo: run.py mataria o processo inteiro e o
    watchdog reiniciaria sem parar, sem nada legível chegar à tela do
    totem. Em vez disso, sobe o Flask normalmente e bloqueia toda rota com
    um aviso — dá pra equipe do estande ver o motivo e corrigir o JSON.
    """
    global _erro_fatal
    try:
        _aplicar_config(init_db())
    except ConfiguracaoInvalida as exc:
        log.error("Configuração inválida na inicialização: %s", exc)
        _erro_fatal = str(exc)
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
