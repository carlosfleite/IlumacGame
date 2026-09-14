# Quiz SDAI — Ilumac Fire Show 2026

Jogo de quiz interativo para totem touch (retrato), 100% offline.

## Requisitos

- Windows 10/11, 64 bits
- Microsoft Edge WebView2 (já incluso no Windows 10/11 atualizado) — é o único requisito que precisa estar no totem antes da feira; o resto vai no pendrive
- Python **não precisa estar instalado no totem** — veja "Pendrive (sem Python, sem internet)" abaixo

## Pendrive (sem Python, sem internet)

O jogo carrega um Python completo dentro da própria pasta, em `python-embed\`. O `INICIAR_QUIZ.bat` usa esse Python automaticamente quando a pasta existe — nada é baixado nem instalado no totem no dia da feira.

**Preparar o pendrive (uma vez, nesta máquina de desenvolvimento, com internet):**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tools\montar_python_embarcado.py
```

Isso cria `python-embed\` com o interpretador e todas as dependências já instaladas e testadas. Depois é só copiar a pasta do projeto **inteira** (incluindo `python-embed\`, que não vai pro Git por ser só binário) para o pendrive.

**No totem:** dê dois cliques em `INICIAR_QUIZ.bat`. Ele detecta `python-embed\`, confere as dependências e abre o quiz em tela cheia — sem precisar de Python instalado, sem internet, sem passos manuais. Ainda assim, teste esse fluxo completo (pendrive → totem limpo) antes da feira.

## Desenvolvimento (com Python instalado nesta máquina)

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

Se a `.venv` já existir com uma dependência nova instalada, rode `tools\montar_python_embarcado.py` de novo para atualizar `python-embed\` antes de gravar o pendrive.

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
