# -*- coding: utf-8 -*-
"""
Manutencao pontual: renumera quiz_perguntas.id para 1..N (ordem atual),
atualizando quiz_respostas.pergunta_id em lockstep para nao quebrar o
historico ja gravado. Uso unico — depois de rodar, apague este arquivo
ou deixe, nao faz mal, so nao ha necessidade de rodar de novo.

Rode com o totem FECHADO (nada deve estar escrevendo no banco ao mesmo
tempo). Faca backup do quiz.db antes.
"""
import sqlite3
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = OFF")

rows = conn.execute("SELECT id FROM quiz_perguntas ORDER BY id").fetchall()
mapa = {r["id"]: novo for novo, r in enumerate(rows, start=1)}

OFFSET = 1_000_000
conn.execute("BEGIN")
try:
    for antigo, novo in mapa.items():
        conn.execute(
            "UPDATE quiz_perguntas SET id = ? WHERE id = ?",
            (antigo + OFFSET, antigo),
        )
        conn.execute(
            "UPDATE quiz_respostas SET pergunta_id = ? WHERE pergunta_id = ?",
            (antigo + OFFSET, antigo),
        )
    for antigo, novo in mapa.items():
        conn.execute(
            "UPDATE quiz_perguntas SET id = ? WHERE id = ?",
            (novo, antigo + OFFSET),
        )
        conn.execute(
            "UPDATE quiz_respostas SET pergunta_id = ? WHERE pergunta_id = ?",
            (novo, antigo + OFFSET),
        )

    conn.execute(
        "UPDATE sqlite_sequence SET seq = ? WHERE name = 'quiz_perguntas'",
        (len(mapa),),
    )

    problemas = conn.execute("PRAGMA foreign_key_check").fetchall()
    if problemas:
        raise RuntimeError("foreign_key_check encontrou problemas: %r" % problemas)

    conn.commit()
    print("Renumeracao concluida:", len(mapa), "perguntas agora com id 1..%d" % len(mapa))
except Exception:
    conn.rollback()
    raise
finally:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()
