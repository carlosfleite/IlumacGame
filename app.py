# -*- coding: utf-8 -*-
"""
Rotas Flask do Quiz SDAI — Ilumac Fire Show 2026.
App local single-user (totem); estado da tentativa fica em memória.
"""

import random
import threading
from flask import Flask, jsonify, render_template, request

from database import buscar_premio_por_pontos, get_connection, init_db

app = Flask(__name__)

# Estado da sessão atual do totem (uma pessoa por vez).
# Chave: participante_id → dict com perguntas, respostas bufferizadas, etc.
_sessao_lock = threading.Lock()
_sessoes = {}

PONTOS_POR_ACERTO = 2
QTD_PERGUNTAS = 5


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
    return render_template("regras.html")


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

@app.route("/api/cadastro", methods=["POST"])
def api_cadastro():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    empresa = (data.get("empresa") or "").strip()
    email = (data.get("email") or "").strip()
    telefone = (data.get("telefone") or "").strip()
    cargo = (data.get("cargo") or "").strip()
    consentimento = 1 if data.get("consentimento_lgpd") else 0

    if not nome:
        return jsonify({"ok": False, "erro": "Nome é obrigatório."}), 400
    if not consentimento:
        return jsonify({"ok": False, "erro": "Consentimento LGPD é obrigatório."}), 400

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO participantes
                (nome, empresa, email, telefone, cargo, consentimento_lgpd)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, empresa, email, telefone, cargo, consentimento),
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
    init_db()
    return app


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
