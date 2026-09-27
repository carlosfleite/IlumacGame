# Quiz SDAI — Ilumac Fire Show 2026

Jogo de quiz interativo para totem touch (retrato), 100% offline.

## Requisitos

- Windows 10/11, 64 bits
- Microsoft Edge WebView2 (já incluso no Windows 10/11 atualizado) — é o único requisito que precisa estar no totem antes da feira; o resto vai no pendrive
- Python **não precisa estar instalado no totem** — o `INICIAR_QUIZ.bat` se instala sozinho na máquina, veja abaixo

## Guia rápido para quem for operar o totem na feira

Isso aqui é pra explicar pra qualquer pessoa (técnica ou não) o que acontece quando o `INICIAR_QUIZ.bat` é executado, em qualquer um dos 3 dias, em qualquer mini PC:

1. **Dá dois cliques em `INICIAR_QUIZ.bat`.**
2. **Se for a primeira vez do jogo NAQUELE computador**, uma janela preta aparece escrito "Instalando o Python do totem agora... (100% local, sem internet)". Isso é o `.bat` copiando o Python e tudo que o jogo precisa de dentro do próprio pendrive pra dentro da pasta `python-embed\`, que fica do lado do jogo. **Não usa internet em nenhum momento** — só descompacta um arquivo que já veio no pendrive (`instalador\python-embed.zip`). Pode levar alguns minutos (varia com a velocidade do pendrive/HD e do antivírus da máquina); não precisa fazer nada, só esperar.
3. **Terminada a instalação** (ou direto, se já tinha instalado antes nessa máquina), o jogo abre sozinho em tela cheia.
4. **No segundo e terceiro dia, na MESMA máquina:** passo 2 não acontece de novo — `python-embed\` já está lá, o jogo abre na hora.
5. **Se o segundo ou terceiro dia usar um mini PC diferente** (ou a pasta `python-embed\` sumir/corromper por qualquer motivo): o passo 2 acontece de novo, automaticamente, sem ninguém precisar fazer nada além de esperar — sempre sem internet, sempre a partir do que já está no pendrive.
6. **No fim de cada dia da feira, antes de desligar aquele computador**, copie a pasta `backups\` (está dentro da própria pasta do jogo) para o pendrive ou outro lugar seguro. Esse é o único passo manual que existe — nenhum programa consegue mover arquivo de uma máquina pra outra sozinho sem internet. Veja a seção "Backups" abaixo para os detalhes.

Resumindo pra quem só vai operar: **plugou o pendrive, copiou/rodou o jogo, deu dois cliques no `.bat`, esperou o que precisar esperar, e no fim do dia salvou a pasta `backups\`.** Todo o resto é automático.

## Como o pendrive é preparado (sem Python, sem internet no dia da feira)

O `INICIAR_QUIZ.bat` é o único lugar onde a instalação acontece — ele conhece só dois arquivos, além do próprio jogo:

- `python-embed\` — o Python já instalado e pronto, se existir nesta máquina (fica pronto depois da primeira instalação).
- `instalador\python-embed.zip` — a cópia compactada do mesmo Python, que viaja com o jogo pra poder instalar em qualquer máquina nova.

Se `python-embed\` já existe, o `.bat` usa direto. Se não existe mas o `.zip` existe, o `.bat` extrai ele ali mesmo (`Expand-Archive` do Windows, sem internet) e só depois abre o jogo. Sem nenhum dos dois, ele cai num modo de desenvolvimento (exige Python instalado na máquina) — não deve acontecer no pendrive da feira.

**Gerar o instalador (uma vez, nesta máquina de desenvolvimento, com internet):**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tools\montar_python_embarcado.py
```

Isso cria `python-embed\` (pronto pra rodar aqui mesmo) e `instalador\python-embed.zip` (o que viaja pro pendrive e alimenta a instalação automática em qualquer outra máquina). Nenhum dos dois vai pro Git — são só binários; copie a pasta do projeto **inteira**, com os dois, para o pendrive.

Se trocar alguma dependência (`requirements.txt`), rode `tools\montar_python_embarcado.py` de novo antes de gravar o pendrive — ele reconstrói os dois arquivos do zero.

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

## Cadastro offline

O servidor e o formulário usam a mesma lista de domínios em `DOMINIOS_EMAIL`, no `app.py`. E-mails corporativos, subdomínios e domínios fora dessa lista são rejeitados. A validação confere formato e domínio permitido; não confirma existência da caixa ou propriedade do endereço. Cadastros anteriores são preservados.

## O que ajustar depois

| Conteúdo | Onde |
|---|---|
| Perguntas técnicas reais | `config/questions.json` — edite e reinicie o totem, sem apagar o banco |
| Prêmios / faixas de pontos | `config/premios.json` — mesma lógica |
| Sprites do Llumaquinho | Gerados por `tools/gerar_pixel_assets.py` a partir de `img/`; rode o script de novo se a arte de origem mudar |

O banco (`quiz.db`) nunca deve ser apagado durante o evento — ele guarda os cadastros e o ranking acumulado dos 3 dias. `config/*.json` é sincronizado com o banco a cada boot sem apagar nada.

## Backups (importante se o totem trocar de mini PC entre os dias)

`backups\` fica **sempre dentro da própria pasta do jogo** (do lado de `app.py`, `quiz.db`, `python-embed\` etc.) — nunca em outro lugar do disco, nunca fora dessa pasta. Copiar/gravar o backup é sempre copiar essa única pasta. O jogo salva sozinho uma cópia completa do banco (cadastros, tentativas, respostas) ali dentro, nomeada com data/hora e o motivo:

- **No boot** (`_boot.db`) — toda vez que o `INICIAR_QUIZ.bat`/`run.py` sobe, antes de sincronizar `config/*.json`. Cobre reinícios do watchdog e o começo de cada dia.
- **No fim do dia** (`_fim_do_dia.db`) — automático, a partir das 21h locais (ajustável em `HORA_BACKUP_FIM_DIA`, no topo do `run.py`), sem precisar reiniciar o totem. Cobre o totem que fica ligado o dia inteiro.
- **Manual** (`_manual.db`) — botão "Fazer backup agora" no painel admin (`/admin`), pra quando alguém quiser garantir um backup na hora, por exemplo pouco antes de desligar o totem.

**O que o backup automático NÃO resolve sozinho:** ele só grava dentro da própria máquina do totem. Se a feira usa um mini PC diferente a cada dia, alguém precisa **copiar a pasta `backups\` para o pendrive (ou outro lugar seguro) no fim de cada dia**, antes de desligar aquele computador — sem essa cópia manual entre máquinas, o dia fica só na máquina que já não vai mais ser usada. O painel admin mostra a hora do último backup salvo para facilitar essa conferência.

O ranking do totem já mostra "hoje" e "os 3 dias" separadamente (abas na tela de Ranking); os arquivos em `backups\` são o histórico bruto por trás disso, caso precise reabrir os dados de um dia específico depois — cada `.db` é um banco SQLite completo, dá pra abrir com `python -c "import sqlite3; ..."` ou qualquer visualizador de SQLite.

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
