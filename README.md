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
| Perguntas técnicas reais | `config/questions.json` — edite e reinicie o totem, sem apagar o banco |
| Prêmios / faixas de pontos | `config/premios.json` — mesma lógica |
| Sprites do Llumaquinho | Gerados por `tools/gerar_pixel_assets.py` a partir de `img/`; rode o script de novo se a arte de origem mudar |

O banco (`quiz.db`) nunca deve ser apagado durante o evento — ele guarda os cadastros e o ranking acumulado dos 3 dias. `config/*.json` é sincronizado com o banco a cada boot sem apagar nada.

## Fluxo das telas

1. Abertura (tela de repouso do totem) → 2. Cadastro (LGPD obrigatório) → 3. Regras → 4. Quiz (5 perguntas) → 5. Resultado → 6. Ranking → volta pra Abertura

## Exportar os dados (pós-feira)

Com o totem ligado, conecte o teclado/mouse wireless e abra no navegador:

```
http://127.0.0.1:5000/admin/exportar/participantes.csv
```

Baixa um CSV com todos os cadastros — inclusive de quem se cadastrou mas
não terminou o quiz, porque para captação a lista de leads importa
inteira. Uma linha por participante: dados de contato, consentimento
LGPD, melhor pontuação, tempo e prêmio ganho (se houver).

Abre direto no Excel em português sem passar pelo assistente de
importação (delimitador `;` e acentuação em UTF-8 com BOM). Não fica
linkado em nenhuma tela do jogo — é só para a equipe. Como o `run.py`
sobe o Flask apenas em `127.0.0.1`, esse endereço não é alcançável de
fora da própria máquina do totem.
