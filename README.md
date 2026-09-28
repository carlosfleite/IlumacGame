# Quiz SDAI — Ilumac Fire Show 2026

Jogo de quiz interativo para totem touch (retrato), 100% offline.

## Requisitos

- Windows 10/11, 64 bits
- Microsoft Edge WebView2 (já incluso no Windows 10/11 atualizado). Se faltar, o jogo **não quebra**: abre sozinho no próprio Edge em modo quiosque (tela cheia, sem barra de endereço), que vem em todo Windows 10/11
- Python **não precisa estar instalado no totem** — o `INICIAR_QUIZ.bat` se instala sozinho na máquina, veja abaixo

## Guia rápido para quem for operar o totem na feira

Isso aqui é pra explicar pra qualquer pessoa (técnica ou não) o que acontece quando o `INICIAR_QUIZ.bat` é executado, em qualquer um dos 3 dias, em qualquer mini PC:

1. **Dá dois cliques em `INICIAR_QUIZ.bat`.**
2. **Se for a primeira vez do jogo NAQUELE computador**, uma janela preta aparece escrito "Instalando o Python do totem agora... (100% local, sem internet)". Isso é o `.bat` copiando o Python e tudo que o jogo precisa de dentro do próprio pendrive pra dentro da pasta `python-embed\`, que fica do lado do jogo. **Não usa internet em nenhum momento** — só descompacta um arquivo que já veio no pendrive (`instalador\python-embed.zip`). Pode levar alguns minutos (varia com a velocidade do pendrive/HD e do antivírus da máquina); não precisa fazer nada, só esperar.
3. **Terminada a instalação** (ou direto, se já tinha instalado antes nessa máquina), o jogo abre sozinho em tela cheia.
4. **No segundo e terceiro dia, na MESMA máquina:** passo 2 não acontece de novo — `python-embed\` já está lá, o jogo abre na hora.
5. **Se o segundo ou terceiro dia usar um mini PC diferente** (ou a pasta `python-embed\` sumir/corromper por qualquer motivo): o passo 2 acontece de novo, automaticamente, sem ninguém precisar fazer nada além de esperar — sempre sem internet, sempre a partir do que já está no pendrive.
6. **Deixe o pendrive de backup espetado no totem** (um pendrive com uma pasta chamada `ILUMAC_BACKUP` na raiz). O jogo copia cada backup para ele sozinho. Sem esse pendrive, no fim de cada dia copie a pasta `backups\` à mão antes de desligar o computador. Veja a seção "Backups" abaixo.

Resumindo pra quem só vai operar: **plugou o pendrive, deu dois cliques no `.bat`, esperou o que precisar esperar.** Todo o resto é automático.

### Baixando o jogo pelo GitHub (.zip)

Na página do repositório: **Code → Download ZIP** (branch `main`). Extraia o .zip num lugar de **caminho curto**, por exemplo `C:\IlumacGame` ou a Área de Trabalho — dentro de muitas pastas (ou no OneDrive) o caminho fica longo demais para o Windows e o Python do jogo não instala; o `.bat` avisa se for o caso. O .zip já traz o instalador do Python (`instalador\python-embed.zip`): a primeira abertura instala tudo sem internet, em cerca de 1 minuto.

Baixou uma versão nova em outra pasta? Rode o `ABRIR_JUNTO_COM_WINDOWS.bat` da pasta nova: o atalho de abertura automática passa a apontar para ela (o `VERIFICAR_TOTEM.bat` avisa se ele ainda aponta para a cópia antiga). O banco (`quiz.db`) e os `backups\` ficam na pasta antiga — copie os dois para a nova se já houver cadastros.

### Antes da feira, em cada computador do totem

1. **`VERIFICAR_TOTEM.bat`** — dois cliques. Confere tudo (Python, janela, arquivos, perguntas, prêmios, banco, backups, pendrive, disco) e diz em português se está pronto. Só lê, não muda nada.
2. **`ABRIR_JUNTO_COM_WINDOWS.bat`** — dois cliques, uma vez. O jogo passa a abrir sozinho quando o computador liga: se faltar energia ou o Windows reiniciar para atualizar, o totem volta sozinho. Rodar de novo oferece desfazer.

### O que já é automático

- **Jogo fechou ou travou:** o `INICIAR_QUIZ.bat` reabre em 5 s.
- **`.bat` aberto duas vezes:** a segunda cópia percebe e fecha, sem empilhar janelas.
- **Tela apagando / computador suspendendo:** bloqueado enquanto o jogo está aberto (sem mexer na configuração de energia da máquina).
- **Sem WebView2:** abre no Edge em modo quiosque. Para ver como fica, rode `python-embed\python.exe run.py --navegador`.
- **Banco danificado** (queda de energia no meio de uma gravação): ao abrir, o jogo detecta, guarda o arquivo danificado em `backups\` e volta sozinho para o último backup bom.
- **Tela de qualquer tamanho:** o jogo foi desenhado para 1080x1920 e, em qualquer outra tela, encolhe inteiro e centraliza, sem cortar nada.

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

`backups\` fica **sempre dentro da própria pasta do jogo** (do lado de `app.py`, `quiz.db`, `python-embed\` etc.) — nunca em outro lugar do disco do computador. Copiar/gravar o backup é sempre copiar essa única pasta. O jogo salva sozinho uma cópia completa do banco (cadastros, tentativas, respostas) ali dentro, nomeada com data/hora e o motivo:

- **No boot** (`_boot.db`) — toda vez que o `INICIAR_QUIZ.bat`/`run.py` sobe, antes de sincronizar `config/*.json`. Cobre reinícios do watchdog e o começo de cada dia.
- **De hora em hora** (`_hora14.db`, `_hora15.db`...) — só nas horas em que entrou cadastro ou partida nova. Se o computador morrer à tarde, a manhã já está salva.
- **No fim do dia** (`_fim_do_dia.db`) — automático, a partir das 21h locais (ajustável em `HORA_BACKUP_FIM_DIA`, no topo do `run.py`), sem precisar reiniciar o totem. Cobre o totem que fica ligado o dia inteiro.
- **Manual** (`_manual.db`) — botão "Fazer backup agora" no painel admin (`/admin`), pra quando alguém quiser garantir um backup na hora, por exemplo pouco antes de desligar o totem.

**Pendrive de backup (cópia automática para fora do computador):** crie uma pasta chamada **`ILUMAC_BACKUP`** na raiz de um pendrive e deixe-o espetado no totem. Cada backup acima é copiado também para `ILUMAC_BACKUP\<nome do computador>\` — assim, se o computador do totem pifar, os dados já estão fora dele, e mini PCs diferentes não misturam arquivos. Só pendrive com essa pasta recebe dados (um pendrive qualquer espetado no totem nunca recebe cadastro de ninguém). Pendrive cheio ou arrancado não atrapalha o jogo: o backup local continua saindo.

Sem o pendrive de backup conectado, o backup só fica na máquina do totem: nesse caso, alguém precisa **copiar a pasta `backups\` para um pendrive no fim de cada dia**, antes de desligar aquele computador. O painel admin mostra a hora do último backup salvo para facilitar essa conferência.

**Cada gravação vai para o disco na hora:** o banco grava em modo `synchronous=FULL`, então uma queda de energia não leva as últimas partidas.

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
