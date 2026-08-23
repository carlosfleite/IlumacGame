# -*- coding: utf-8 -*-
"""
Conexão SQLite, schema, migrações e sincronização do conteúdo editável.

O conteúdo do quiz (perguntas e premiação) mora em arquivos JSON na pasta
config/, não no código. A cada boot esses arquivos são sincronizados com o
banco. O banco continua sendo a fonte de verdade em runtime — assim as
respostas gravadas (quiz_respostas) mantêm integridade referencial com a
pergunta que foi de fato exibida.

Regra de ouro: sincronizar NUNCA pode apagar dados de participante. Uma
pergunta removida do JSON é desativada, jamais deletada.
"""

import json
import logging
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quiz.db")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
PERGUNTAS_JSON = os.path.join(CONFIG_DIR, "questions.json")
PREMIOS_JSON = os.path.join(CONFIG_DIR, "premios.json")

LETRAS = ("a", "b", "c", "d")

# Usados quando o questions.json não traz os valores (ou está inválido).
PONTOS_POR_ACERTO_PADRAO = 2
PERGUNTAS_POR_PARTIDA_PADRAO = 5

log = logging.getLogger(__name__)


class ConfiguracaoInvalida(Exception):
    """JSON de conteúdo malformado. Não derruba o totem: ver init_db()."""


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def get_connection():
    """
    Retorna conexão sqlite3 com Row factory (acesso por nome de coluna).

    PRAGMAs escolhidos para um totem que roda 3 dias sem supervisão:
    - journal_mode=WAL: leitura (ranking) não bloqueia escrita (finalizar
      partida). Sem isso, consultar o ranking enquanto alguém termina o quiz
      pode devolver "database is locked".
    - busy_timeout: em vez de falhar na hora, espera o lock por até 5 s.
    - synchronous=NORMAL: seguro sob WAL e bem mais leve no disco que FULL.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS participantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    empresa TEXT,
    email TEXT,
    telefone TEXT,
    cargo TEXT,
    consentimento_lgpd INTEGER NOT NULL DEFAULT 0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_perguntas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT,
    texto TEXT NOT NULL,
    alt_a TEXT NOT NULL,
    alt_b TEXT NOT NULL,
    alt_c TEXT NOT NULL,
    alt_d TEXT NOT NULL,
    correta TEXT NOT NULL CHECK (correta IN ('a','b','c','d')),
    dificuldade TEXT NOT NULL DEFAULT 'geral',
    ativa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS quiz_premios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT,
    pontos_min INTEGER NOT NULL,
    pontos_max INTEGER NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS quiz_tentativas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participante_id INTEGER NOT NULL REFERENCES participantes(id),
    pontuacao INTEGER NOT NULL,
    tempo_total_ms INTEGER NOT NULL,
    premio_id INTEGER REFERENCES quiz_premios(id),
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_respostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tentativa_id INTEGER NOT NULL REFERENCES quiz_tentativas(id),
    pergunta_id INTEGER NOT NULL REFERENCES quiz_perguntas(id),
    resposta_dada TEXT,
    acertou INTEGER NOT NULL,
    tempo_resposta_ms INTEGER NOT NULL
);

-- O ranking ordena por pontuação desc e tempo asc sobre todas as partidas.
CREATE INDEX IF NOT EXISTS idx_tentativas_ranking
    ON quiz_tentativas (pontuacao DESC, tempo_total_ms ASC);

-- Ranking e CSV agrupam tentativas por participante (melhor pontuação) e
-- respostas por tentativa; sem estes índices as duas consultas fazem
-- table scan completo a cada carregamento.
CREATE INDEX IF NOT EXISTS idx_tentativas_participante
    ON quiz_tentativas (participante_id);

CREATE INDEX IF NOT EXISTS idx_respostas_tentativa
    ON quiz_respostas (tentativa_id);
"""


def _colunas(conn, tabela):
    return {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % tabela)}


def _migrar(conn):
    """
    Migrações idempotentes para bancos criados antes da config externa.

    A coluna 'chave' liga a linha do banco ao item do JSON. Bancos antigos
    não a possuem: adicionamos, marcamos o conteúdo legado como inativo
    (eram placeholders) e deixamos o sync do JSON assumir. Nada é apagado,
    para não quebrar as respostas já gravadas.
    """
    if "chave" not in _colunas(conn, "quiz_perguntas"):
        log.info("Migrando quiz_perguntas: adicionando coluna 'chave'")
        conn.execute("ALTER TABLE quiz_perguntas ADD COLUMN chave TEXT")
        conn.execute(
            "UPDATE quiz_perguntas SET chave = 'legado-' || id, ativa = 0 "
            "WHERE chave IS NULL"
        )

    if "dificuldade" not in _colunas(conn, "quiz_perguntas"):
        log.info("Migrando quiz_perguntas: adicionando coluna 'dificuldade'")
        conn.execute(
            "ALTER TABLE quiz_perguntas ADD COLUMN dificuldade TEXT NOT NULL DEFAULT 'geral'"
        )

    if "chave" not in _colunas(conn, "quiz_premios"):
        log.info("Migrando quiz_premios: adicionando coluna 'chave'")
        conn.execute("ALTER TABLE quiz_premios ADD COLUMN chave TEXT")
        conn.execute(
            "UPDATE quiz_premios SET chave = 'legado-' || id, ativo = 0 "
            "WHERE chave IS NULL"
        )

    # UNIQUE só depois do backfill, senão os NULLs antigos atrapalham o upsert.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_perguntas_chave "
        "ON quiz_perguntas (chave)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_premios_chave "
        "ON quiz_premios (chave)"
    )


# ---------------------------------------------------------------------------
# Leitura e validação dos JSON
# ---------------------------------------------------------------------------

def _ler_json(caminho):
    if not os.path.exists(caminho):
        raise ConfiguracaoInvalida("arquivo nao encontrado: %s" % caminho)
    try:
        with open(caminho, encoding="utf-8") as fp:
            return json.load(fp)
    except ValueError as exc:
        raise ConfiguracaoInvalida("JSON invalido em %s: %s" % (caminho, exc))


def _texto(valor, campo, contexto):
    if not isinstance(valor, str) or not valor.strip():
        raise ConfiguracaoInvalida(
            "%s: '%s' deve ser um texto nao vazio" % (contexto, campo)
        )
    return valor.strip()


def carregar_perguntas():
    """Lê e valida o questions.json. Levanta ConfiguracaoInvalida se ruim."""
    dados = _ler_json(PERGUNTAS_JSON)

    pontos = dados.get("pontos_por_acerto", PONTOS_POR_ACERTO_PADRAO)
    por_partida = dados.get("perguntas_por_partida", PERGUNTAS_POR_PARTIDA_PADRAO)
    if not isinstance(pontos, int) or pontos <= 0:
        raise ConfiguracaoInvalida("'pontos_por_acerto' deve ser inteiro positivo")
    if not isinstance(por_partida, int) or por_partida <= 0:
        raise ConfiguracaoInvalida("'perguntas_por_partida' deve ser inteiro positivo")

    brutas = dados.get("perguntas")
    if not isinstance(brutas, list) or not brutas:
        raise ConfiguracaoInvalida("'perguntas' deve ser uma lista nao vazia")

    perguntas = []
    vistas = set()
    for i, item in enumerate(brutas, start=1):
        ctx = "pergunta #%d" % i
        if not isinstance(item, dict):
            raise ConfiguracaoInvalida("%s: deveria ser um objeto" % ctx)

        chave = _texto(item.get("chave"), "chave", ctx)
        if chave in vistas:
            raise ConfiguracaoInvalida("chave duplicada: '%s'" % chave)
        vistas.add(chave)

        ctx = "pergunta '%s'" % chave
        alts = item.get("alternativas")
        if not isinstance(alts, dict):
            raise ConfiguracaoInvalida("%s: 'alternativas' deve ser um objeto" % ctx)
        for letra in LETRAS:
            _texto(alts.get(letra), "alternativas.%s" % letra, ctx)

        correta = _texto(item.get("correta"), "correta", ctx).lower()
        if correta not in LETRAS:
            raise ConfiguracaoInvalida(
                "%s: 'correta' deve ser a, b, c ou d (recebido: %r)" % (ctx, correta)
            )

        perguntas.append({
            "chave": chave,
            "texto": _texto(item.get("texto"), "texto", ctx),
            "alt_a": alts["a"].strip(),
            "alt_b": alts["b"].strip(),
            "alt_c": alts["c"].strip(),
            "alt_d": alts["d"].strip(),
            "correta": correta,
            "dificuldade": (item.get("dificuldade") or "geral").strip().lower(),
            "ativa": 1 if item.get("ativa", True) else 0,
        })

    ativas = sum(p["ativa"] for p in perguntas)
    if ativas < por_partida:
        raise ConfiguracaoInvalida(
            "so ha %d pergunta(s) ativa(s); a partida precisa de %d"
            % (ativas, por_partida)
        )

    return {
        "pontos_por_acerto": pontos,
        "perguntas_por_partida": por_partida,
        "perguntas": perguntas,
    }


def carregar_premios():
    """Lê e valida o premios.json. Levanta ConfiguracaoInvalida se ruim."""
    dados = _ler_json(PREMIOS_JSON)

    brutas = dados.get("faixas")
    if not isinstance(brutas, list) or not brutas:
        raise ConfiguracaoInvalida("'faixas' deve ser uma lista nao vazia")

    faixas = []
    vistas = set()
    for i, item in enumerate(brutas, start=1):
        ctx = "faixa #%d" % i
        if not isinstance(item, dict):
            raise ConfiguracaoInvalida("%s: deveria ser um objeto" % ctx)

        chave = _texto(item.get("chave"), "chave", ctx)
        if chave in vistas:
            raise ConfiguracaoInvalida("chave de faixa duplicada: '%s'" % chave)
        vistas.add(chave)

        ctx = "faixa '%s'" % chave
        pmin = item.get("pontos_min")
        pmax = item.get("pontos_max")
        if not isinstance(pmin, int) or not isinstance(pmax, int):
            raise ConfiguracaoInvalida(
                "%s: pontos_min/pontos_max devem ser inteiros" % ctx
            )
        if pmin > pmax:
            raise ConfiguracaoInvalida("%s: pontos_min maior que pontos_max" % ctx)

        faixas.append({
            "chave": chave,
            "pontos_min": pmin,
            "pontos_max": pmax,
            "nome": _texto(item.get("nome"), "nome", ctx),
            "descricao": (item.get("descricao") or "").strip(),
            "ativo": 1 if item.get("ativo", True) else 0,
        })

    return faixas


# ---------------------------------------------------------------------------
# Sincronização JSON -> banco
# ---------------------------------------------------------------------------

def sincronizar_perguntas(conn, perguntas):
    """Insere/atualiza por chave e desativa o que sumiu do JSON."""
    for p in perguntas:
        conn.execute(
            """
            INSERT INTO quiz_perguntas
                (chave, texto, alt_a, alt_b, alt_c, alt_d, correta, dificuldade, ativa)
            VALUES (:chave, :texto, :alt_a, :alt_b, :alt_c, :alt_d, :correta, :dificuldade, :ativa)
            ON CONFLICT(chave) DO UPDATE SET
                texto = excluded.texto,
                alt_a = excluded.alt_a,
                alt_b = excluded.alt_b,
                alt_c = excluded.alt_c,
                alt_d = excluded.alt_d,
                correta = excluded.correta,
                dificuldade = excluded.dificuldade,
                ativa = excluded.ativa
            """,
            p,
        )

    # Desativa (nunca apaga) o que saiu do JSON: as respostas já gravadas
    # continuam apontando para a pergunta que foi exibida na hora.
    chaves = [p["chave"] for p in perguntas]
    marcadores = ",".join("?" * len(chaves))
    conn.execute(
        "UPDATE quiz_perguntas SET ativa = 0 WHERE chave NOT IN (%s)" % marcadores,
        chaves,
    )


def sincronizar_premios(conn, faixas):
    for f in faixas:
        conn.execute(
            """
            INSERT INTO quiz_premios
                (chave, pontos_min, pontos_max, nome, descricao, ativo)
            VALUES (:chave, :pontos_min, :pontos_max, :nome, :descricao, :ativo)
            ON CONFLICT(chave) DO UPDATE SET
                pontos_min = excluded.pontos_min,
                pontos_max = excluded.pontos_max,
                nome = excluded.nome,
                descricao = excluded.descricao,
                ativo = excluded.ativo
            """,
            f,
        )

    chaves = [f["chave"] for f in faixas]
    marcadores = ",".join("?" * len(chaves))
    conn.execute(
        "UPDATE quiz_premios SET ativo = 0 WHERE chave NOT IN (%s)" % marcadores,
        chaves,
    )


def _validar_cobertura_premios(faixas, pontuacao_maxima, incremento):
    """
    Não-fatal de propósito: uma lacuna na premiação é erro de conteúdo
    (alguém mexeu no premios.json e esqueceu uma faixa), não motivo para
    derrubar o totem. Só avisa no log pra equipe corrigir — quem cair na
    lacuna simplesmente fica sem prêmio, sem crash.
    """
    ativas = [f for f in faixas if f["ativo"]]
    faltando = [
        p for p in range(0, pontuacao_maxima + 1, incremento)
        if not any(f["pontos_min"] <= p <= f["pontos_max"] for f in ativas)
    ]
    if faltando:
        log.error(
            "premios.json tem lacuna(s) de cobertura: pontuacao(oes) %s nao "
            "caem em nenhuma faixa ativa. Corrija config/premios.json.",
            faltando,
        )


def init_db():
    """
    Cria o schema, migra e sincroniza o conteúdo dos JSON.

    Devolve os parâmetros do quiz (pontos por acerto, perguntas por partida).

    Erro de JSON aqui é tolerado de propósito: no meio da feira, um arquivo
    salvo com erro de digitação não pode derrubar o totem. Registra em log e
    segue com o conteúdo que já está no banco.
    """
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        _migrar(conn)
        conn.commit()

        config = {
            "pontos_por_acerto": PONTOS_POR_ACERTO_PADRAO,
            "perguntas_por_partida": PERGUNTAS_POR_PARTIDA_PADRAO,
        }

        try:
            dados = carregar_perguntas()
            sincronizar_perguntas(conn, dados["perguntas"])
            config["pontos_por_acerto"] = dados["pontos_por_acerto"]
            config["perguntas_por_partida"] = dados["perguntas_por_partida"]
            log.info(
                "questions.json sincronizado: %d pergunta(s), %d ativa(s)",
                len(dados["perguntas"]),
                sum(p["ativa"] for p in dados["perguntas"]),
            )
        except ConfiguracaoInvalida as exc:
            log.error(
                "questions.json NAO foi aplicado (%s). "
                "Seguindo com as perguntas ja gravadas no banco.", exc
            )

        try:
            faixas = carregar_premios()
            sincronizar_premios(conn, faixas)
            log.info("premios.json sincronizado: %d faixa(s)", len(faixas))
            pontuacao_maxima = config["perguntas_por_partida"] * config["pontos_por_acerto"]
            _validar_cobertura_premios(faixas, pontuacao_maxima, config["pontos_por_acerto"])
        except ConfiguracaoInvalida as exc:
            log.error(
                "premios.json NAO foi aplicado (%s). "
                "Seguindo com a premiacao ja gravada no banco.", exc
            )

        conn.commit()

        # Sem perguntas ativas não existe jogo: aqui vale falhar alto.
        ativas = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_perguntas WHERE ativa = 1"
        ).fetchone()["n"]
        if ativas < config["perguntas_por_partida"]:
            raise ConfiguracaoInvalida(
                "banco tem %d pergunta(s) ativa(s); a partida precisa de %d. "
                "Corrija o config/questions.json."
                % (ativas, config["perguntas_por_partida"])
            )

        return config
    finally:
        conn.close()


def buscar_premio_por_pontos(conn, pontuacao):
    """Retorna o prêmio ativo cuja faixa contém a pontuação, ou None."""
    row = conn.execute(
        """
        SELECT * FROM quiz_premios
        WHERE ativo = 1 AND pontos_min <= ? AND pontos_max >= ?
        ORDER BY pontos_min DESC
        LIMIT 1
        """,
        (pontuacao, pontuacao),
    ).fetchone()
    return row


# ---------------------------------------------------------------------------
# Melhor tentativa por participante
# ---------------------------------------------------------------------------

# Usada pelo ranking (dia e geral) e pelas exportações do painel admin —
# mantida num só lugar porque é lógica de desempate não trivial (maior
# pontuação; empate → menor tempo) e todo mundo que "quem ganhou de quem"
# precisa concordar.
#
# {filtro} decide sobre QUAIS tentativas a "melhor" é calculada: todas ou
# só as de hoje. Aplicado nas três referências a quiz_tentativas para o
# desempate ficar coerente — senão a melhor pontuação viria do período
# todo, mas o tempo de desempate só de uma fatia dele. 'localtime'
# converte o timestamp (gravado em UTC pelo SQLite) para o fuso do totem
# antes de comparar a data, porque dia de feira é dia de calendário
# local, não dia UTC.
FILTRO_TENTATIVAS_GERAL = "1 = 1"
FILTRO_TENTATIVAS_HOJE = "date(data_hora, 'localtime') = date('now', 'localtime')"

_SQL_MELHOR_TENTATIVA_TMPL = """
    SELECT t.*
    FROM (SELECT * FROM quiz_tentativas WHERE {filtro}) t
    INNER JOIN (
        SELECT participante_id,
               MAX(pontuacao) AS max_pts
        FROM (SELECT * FROM quiz_tentativas WHERE {filtro})
        GROUP BY participante_id
    ) mp ON mp.participante_id = t.participante_id
        AND mp.max_pts = t.pontuacao
    INNER JOIN (
        SELECT participante_id,
               pontuacao,
               MIN(tempo_total_ms) AS min_tempo
        FROM (SELECT * FROM quiz_tentativas WHERE {filtro})
        GROUP BY participante_id, pontuacao
    ) mt ON mt.participante_id = t.participante_id
        AND mt.pontuacao = t.pontuacao
        AND mt.min_tempo = t.tempo_total_ms
    GROUP BY t.participante_id
"""


def sql_melhor_tentativa(filtro=FILTRO_TENTATIVAS_GERAL):
    """Devolve a subquery de melhor tentativa por participante, pronta pra usar num FROM/JOIN."""
    return _SQL_MELHOR_TENTATIVA_TMPL.format(filtro=filtro)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = init_db()
    print("Banco inicializado em:", DB_PATH)
    print("Configuracao do quiz:", cfg)
