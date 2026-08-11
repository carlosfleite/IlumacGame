# Quiz SDAI — Ilumac Fire Show 2026

Jogo de quiz interativo para totem touch (retrato), 100% offline.

## Requisitos

- Windows 10
- Python 3.10+ (recomendado)
- Microsoft Edge WebView2 (já incluso no Windows 10 atualizado)

## Como rodar

**No totem (recomendado):** dê dois cliques em `INICIAR_QUIZ.bat`.

O `.bat` cria o `.venv` se precisar, instala as dependências e abre o quiz em tela cheia.

Manual:

```bash
cd quiz_sdai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

O `run.py` sobe o Flask em `127.0.0.1:5000` e abre a janela pywebview em tela cheia.

Para desenvolver no navegador (sem pywebview):

```bash
python app.py
```

Abra `http://127.0.0.1:5000/`.

## O que ajustar depois

| Conteúdo | Onde |
|---|---|
| Perguntas técnicas reais | Tabela `quiz_perguntas` (ou `seed_perguntas` em `database.py` se recriar o banco) |
| Prêmios / faixas de pontos | Tabela `quiz_premios` (ou `seed_premios` em `database.py`) |
| Sprites do Ilumaquinho | `static/img/ilumaquinho/deu-bom.svg` e `deu-ruim.svg` |

Para resetar o banco: apague `quiz.db` e rode de novo — o schema e os seeds são recriados automaticamente.

## Fluxo das telas

1. Cadastro (LGPD obrigatório) → 2. Regras → 3. Quiz (5 perguntas) → 4. Resultado → 5. Ranking → novo participante
