# -*- coding: utf-8 -*-
"""
Rotas Flask do Quiz SDAI — Ilumac Fire Show 2026.
App local single-user (totem); estado da tentativa fica em memória.
"""

import random
import re
import threading
from flask import Flask, jsonify, render_template, request

from database import buscar_premio_por_pontos, get_connection, init_db

app = Flask(__name__)

# Estado da sessão atual do totem (uma pessoa por vez).
# Chave: participante_id → dict com perguntas, respostas bufferizadas, etc.
_sessao_lock = threading.Lock()
_sessoes = {}

# Preenchidos por create_app() a partir do config/questions.json. Os valores
# aqui são só o fallback de quem roda `python app.py` sem passar pelo factory.
PONTOS_POR_ACERTO = 2
QTD_PERGUNTAS = 5


def _aplicar_config(config):
    global PONTOS_POR_ACERTO, QTD_PERGUNTAS
    PONTOS_POR_ACERTO = config["pontos_por_acerto"]
    QTD_PERGUNTAS = config["perguntas_por_partida"]


def _limpar_sessao(participante_id):
    with _sessao_lock:
        _sessoes.pop(participante_id, None)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.route("/")
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
    partes = [p for p in nome.split(" ") if p]
    if len(partes) < 2:
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
    email = (data.get("email") or "").strip()
    telefone = (data.get("telefone") or "").strip()
    consentimento = 1 if data.get("consentimento_lgpd") else 0

    erro, telefone_fmt = _validar_cadastro(nome, telefone, email)
    if erro:
        return jsonify({"ok": False, "erro": erro}), 400
    if not consentimento:
        return jsonify({"ok": False, "erro": "Consentimento LGPD é obrigatório."}), 400

    conn = get_connection()
    try:
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
            SELECT id, texto, alt_a, alt_b, alt_c, alt_d, correta
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

    selecionadas = random.sample(list(rows), QTD_PERGUNTAS)

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
        _sessoes[participante_id] = {
            "gabarito": gabarito,
            "ordem_ids": [p["id"] for p in perguntas_cliente],
            "respostas": [],  # buffer até finalizar
            "respondidas": set(),
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
    participante_id = data.get("participante_id")
    pergunta_id = data.get("pergunta_id")
    resposta_dada = (data.get("resposta_dada") or "").strip().lower()
    tempo_resposta_ms = data.get("tempo_resposta_ms")

    if not participante_id or not pergunta_id:
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
    participante_id = data.get("participante_id")
    pontuacao = data.get("pontuacao")
    tempo_total_ms = data.get("tempo_total_ms")

    if not participante_id:
        return jsonify({"ok": False, "erro": "participante_id obrigatório."}), 400
    try:
        pontuacao = int(pontuacao)
        tempo_total_ms = int(tempo_total_ms)
        if pontuacao < 0 or tempo_total_ms < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "pontuacao/tempo inválidos."}), 400

    with _sessao_lock:
        sessao = _sessoes.get(participante_id)
        if not sessao:
            return jsonify({"ok": False, "erro": "Sessão de quiz não iniciada."}), 400
        respostas = list(sessao["respostas"])

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

    _limpar_sessao(participante_id)

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
    """
    limite = request.args.get("limite", default=20, type=int)
    if limite < 1:
        limite = 20
    if limite > 100:
        limite = 100

    conn = get_connection()
    try:
        # Melhor tentativa por participante:
        # 1) maior pontuação; 2) se empatar nos pontos, menor tempo.
        # Entre participantes: ORDER BY pontuacao DESC, tempo ASC
        # (tempo só desempata quem tem a MESMA pontuação).
        rows = conn.execute(
            """
            SELECT
                p.nome,
                p.empresa,
                best.pontuacao,
                best.tempo_total_ms,
                best.data_hora,
                pr.nome AS premio_nome
            FROM (
                SELECT t.*
                FROM quiz_tentativas t
                INNER JOIN (
                    SELECT participante_id,
                           MAX(pontuacao) AS max_pts
                    FROM quiz_tentativas
                    GROUP BY participante_id
                ) mp ON mp.participante_id = t.participante_id
                    AND mp.max_pts = t.pontuacao
                INNER JOIN (
                    SELECT participante_id,
                           pontuacao,
                           MIN(tempo_total_ms) AS min_tempo
                    FROM quiz_tentativas
                    GROUP BY participante_id, pontuacao
                ) mt ON mt.participante_id = t.participante_id
                    AND mt.pontuacao = t.pontuacao
                    AND mt.min_tempo = t.tempo_total_ms
                GROUP BY t.participante_id
            ) best
            JOIN participantes p ON p.id = best.participante_id
            LEFT JOIN quiz_premios pr ON pr.id = best.premio_id
            ORDER BY best.pontuacao DESC, best.tempo_total_ms ASC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()

        ranking = []
        for i, row in enumerate(rows, start=1):
            ranking.append({
                "posicao": i,
                "nome": row["nome"],
                "empresa": row["empresa"] or "",
                "pontuacao": row["pontuacao"],
                "tempo_total_ms": row["tempo_total_ms"],
                "premio_nome": row["premio_nome"] or "",
                "data_hora": row["data_hora"],
            })
    finally:
        conn.close()

    return jsonify({"ok": True, "ranking": ranking})


def create_app():
    """Factory usada pelo run.py."""
    _aplicar_config(init_db())
    return app


if __name__ == "__main__":
    _aplicar_config(init_db())
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
