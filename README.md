# Quiz SDAI — Ilumac Fire Show 2026

Jogo de quiz interativo para totem touch (retrato), 100% offline.

## Requisitos

- Windows 10
- Python 3.10+ (recomendado)
- Microsoft Edge WebView2 (já incluso no Windows 10 atualizado)

## Como rodar

**No totem (recomendado):** dê dois cliques em `INICIAR_QUIZ.bat`.

O `.bat` verifica as dependências locais e abre o quiz em tela cheia. Ele não baixa pacotes: se faltar alguma biblioteca, informa o erro e encerra. Prepare e teste o computador antes da feira.

Preparação antes da feira (a instalação abaixo pode usar internet; nunca ocorre ao iniciar o jogo):

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

Para preparar sem internet, leve uma pasta `wheels` com todas as dependências compatíveis com a versão do Python e arquitetura do totem e instale com `.venv\Scripts\python -m pip install --no-index --find-links=wheels -r requirements.txt`. Python e WebView2 também precisam estar instalados previamente.

## Cadastro offline

O servidor e o formulário usam a mesma lista de domínios em `DOMINIOS_EMAIL`, no `app.py`. E-mails corporativos, subdomínios e domínios fora dessa lista são rejeitados. A validação confere formato e domínio permitido; não confirma existência da caixa ou propriedade do endereço. Cadastros anteriores são preservados.

## O que ajustar depois

| Conteúdo | Onde |
|---|---|
| Perguntas técnicas reais | `config/questions.json` — edite e reinicie o totem, sem apagar o banco |
| Prêmios / faixas de pontos | `config/premios.json` — mesma lógica |
| Sprites do Llumaquinho | Gerados por `tools/gerar_pixel_assets.py` a partir de `img/`; rode o script de novo se a arte de origem mudar |

O banco (`quiz.db`) nunca deve ser apagado durante o evento — ele guarda os cadastros e o ranking acumulado dos 3 dias. `config/*.json` é sincronizado com o banco a cada boot sem apagar nada.

## Fluxo das telas

1. Abertura (tela de repouso do totem) → 2. Cadastro (LGPD obrigatório) → 3. Regras → 4. Quiz (5 perguntas) → 5. Resultado → 6. Ranking → volta pra Abertura

## Painel do marketing (pós-feira)

Com o totem ligado, conecte o teclado/mouse wireless e abra no navegador:

```
http://127.0.0.1:5000/admin
```

Tabela com todos os cadastros — inclusive de quem se cadastrou mas não
terminou o quiz, porque para captação a lista de leads importa inteira
— e botões para exportar em **Excel**, **PDF** ou **CSV**. Cada linha
traz o que o marketing precisa pra entrar em contato: nome, telefone,
e-mail, consentimento LGPD, data de cadastro, melhor pontuação, tempo e
prêmio ganho (se houver). Tem uma busca simples por nome/e-mail/telefone
acima da tabela.

Sem senha de propósito: não fica linkado em nenhuma tela do jogo, e
como o `run.py` sobe o Flask apenas em `127.0.0.1`, esse endereço não é
alcançável de fora da própria máquina do totem — só quem está sentado
nela (ou sabe o endereço) abre.
