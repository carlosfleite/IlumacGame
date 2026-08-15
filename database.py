# -*- coding: utf-8 -*-
"""
Conexão SQLite, inicialização do schema e seed de dados de exemplo.

AJUSTES FUTUROS:
- Substitua as perguntas placeholder em seed_perguntas() pelo conteúdo técnico real da Ilumac.
- Ajuste faixas e nomes dos prêmios em seed_premios() conforme a premiação oficial do evento.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz.db")


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


def init_db():
    """Cria tabelas se o banco não existir / estiver vazio e popula seeds."""
    conn = get_connection()
    try:
        conn.executescript(
            """
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
                texto TEXT NOT NULL,
                alt_a TEXT NOT NULL,
                alt_b TEXT NOT NULL,
                alt_c TEXT NOT NULL,
                alt_d TEXT NOT NULL,
                correta TEXT NOT NULL CHECK (correta IN ('a','b','c','d')),
                ativa INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS quiz_premios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            """
        )
        conn.commit()

        # Seed só se ainda não houver dados (permite reabrir o app sem duplicar)
        qtd_perguntas = conn.execute("SELECT COUNT(*) AS n FROM quiz_perguntas").fetchone()["n"]
        if qtd_perguntas == 0:
            seed_perguntas(conn)

        qtd_premios = conn.execute("SELECT COUNT(*) AS n FROM quiz_premios").fetchone()["n"]
        if qtd_premios == 0:
            seed_premios(conn)

        conn.commit()
    finally:
        conn.close()


def seed_perguntas(conn):
    """
    PLACEHOLDER — 15 perguntas genéricas sobre SDAI.
    Substitua depois pelo conteúdo técnico real da Ilumac (Fire Show 2026).
    """
    perguntas = [
        (
            "[PLACEHOLDER] O que significa a sigla SDAI?",
            "Sistema de Detecção e Alarme de Incêndio",
            "Sistema de Distribuição de Água Interna",
            "Sensor de Densidade Ambiental Inteligente",
            "Sistema de Dutos de Ar Industrial",
            "a",
        ),
        (
            "[PLACEHOLDER] Qual é a função principal de um detector de fumaça?",
            "Medir a temperatura do ambiente",
            "Detectar partículas de fumaça no ar",
            "Apagar o foco de incêndio automaticamente",
            "Acionar apenas a iluminação de emergência",
            "b",
        ),
        (
            "[PLACEHOLDER] Em um SDAI, a central de alarme serve para:",
            "Somente registrar histórico de manutenções",
            "Receber sinais dos detectores e acionar alarmes",
            "Substituir o sistema de sprinklers",
            "Controlar apenas a climatização do prédio",
            "b",
        ),
        (
            "[PLACEHOLDER] Qual tipo de dispositivo alerta ocupantes com sinal sonoro?",
            "Detector de fluxo",
            "Módulo de entrada",
            "Sirene / aviso sonoro",
            "Válvula de retenção",
            "c",
        ),
        (
            "[PLACEHOLDER] Detectores do tipo pontual são tipicamente instalados:",
            "No teto ou área a proteger, em pontos definidos",
            "Somente no subsolo",
            "Apenas fora do edifício",
            "Exclusivamente dentro de dutos de ar",
            "a",
        ),
        (
            "[PLACEHOLDER] Um acionador manual (botoeira) permite que a pessoa:",
            "Desligue a energia do prédio",
            "Inicie o alarme de forma manual",
            "Ajuste a sensibilidade dos detectores",
            "Reinicie o servidor de rede",
            "b",
        ),
        (
            "[PLACEHOLDER] Qual benefício de um SDAI endereçável?",
            "Elimina a necessidade de detectores",
            "Identifica o dispositivo/zona que gerou o alarme",
            "Funciona sem alimentação elétrica",
            "Substitui o plano de abandono",
            "b",
        ),
        (
            "[PLACEHOLDER] Em caso de alarme verdadeiro, a prioridade imediata é:",
            "Atualizar o software da central",
            "Garantir a segurança das pessoas e seguir o plano de abandono",
            "Fotografar o ambiente para redes sociais",
            "Desligar todos os detectores",
            "b",
        ),
        (
            "[PLACEHOLDER] Manutenção periódica do SDAI é importante porque:",
            "Aumenta o consumo de energia",
            "Garante funcionamento confiável dos dispositivos",
            "Remove a necessidade de treinamento",
            "Substitui a inspeção do Corpo de Bombeiros",
            "b",
        ),
        (
            "[PLACEHOLDER] Um detector térmico responde principalmente a:",
            "Variação ou limiar de temperatura",
            "Cor da pintura da parede",
            "Nível de umidade do solo",
            "Pressão atmosférica externa",
            "a",
        ),
        (
            "[PLACEHOLDER] Laços (loops) em sistemas endereçáveis interligam:",
            "Apenas tomadas elétricas",
            "Dispositivos de detecção e acionamento à central",
            "Somente câmeras de CFTV",
            "Bombas de recalque de água potável",
            "b",
        ),
        (
            "[PLACEHOLDER] Sinalização visual de alarme (strobes) é útil especialmente para:",
            "Ambientes silenciosos ou pessoas com deficiência auditiva",
            "Decoração do stand",
            "Medição de monóxido de carbono",
            "Controle de acesso biométrico",
            "a",
        ),
        (
            "[PLACEHOLDER] Zona de detecção refere-se a:",
            "Uma área/agrupamento monitorado pelo sistema",
            "O número de andares do shopping",
            "A cor do cabo utilizado",
            "O horário de funcionamento do evento",
            "a",
        ),
        (
            "[PLACEHOLDER] Qual prática NÃO é recomendada no dia a dia com SDAI?",
            "Seguir o plano de emergência do local",
            "Tampar ou obstruir detectores por estética",
            "Participar de treinamentos de abandono",
            "Reportar falhas à equipe responsável",
            "b",
        ),
        (
            "[PLACEHOLDER] Integração do SDAI com outros sistemas pode incluir:",
            "Somente redes sociais",
            "Portas corta-fogo, elevadores e exaustão (conforme projeto)",
            "Impressoras do escritório",
            "Máquinas de café do café",
            "b",
        ),
    ]

    conn.executemany(
        """
        INSERT INTO quiz_perguntas (texto, alt_a, alt_b, alt_c, alt_d, correta, ativa)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        perguntas,
    )


def seed_premios(conn):
    """
    PLACEHOLDER — faixas de prêmio do evento.
    Ajuste pontos_min/pontos_max, nome e descricao conforme a premiação oficial.
    """
    premios = [
        (0, 2, "Sem prêmio", "Participação registrada — tente novamente!", 1),
        (4, 6, "Brinde intermediário", "[PLACEHOLDER] Descrição do brinde intermediário", 1),
        (8, 8, "Brinde de maior valor", "[PLACEHOLDER] Descrição do brinde de maior valor", 1),
        (10, 10, "Garrafa vermelha ou moletom", "[PLACEHOLDER] Escolha entre garrafa vermelha ou moletom", 1),
    ]
    conn.executemany(
        """
        INSERT INTO quiz_premios (pontos_min, pontos_max, nome, descricao, ativo)
        VALUES (?, ?, ?, ?, ?)
        """,
        premios,
    )


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


if __name__ == "__main__":
    init_db()
    print("Banco inicializado em:", DB_PATH)
