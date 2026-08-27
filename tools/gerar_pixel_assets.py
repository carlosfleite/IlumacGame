# -*- coding: utf-8 -*-
"""
Gerador dos assets em pixel art do Quiz SDAI.

NAO faz parte do runtime do totem. Roda so quando a marca muda, numa
maquina de desenvolvimento:

    pip install Pillow
    python tools/gerar_pixel_assets.py

Por que gerar em vez de versionar so o resultado: os PNG de marca em img/
sao ilustracoes suaves em alta resolucao e precisam ser reduzidas e
recortadas para o jogo. Fazer isso na mao e irreproduzivel; aqui fica
documentado.

Tecnica (revisada): a primeira versao reduzia com LANCZOS e depois
quantizava para poucas cores sem dithering. Isso parecia "pixel art" na
teoria, mas na pratica o quantize por pixel sobre uma imagem ja borrada
pelo LANCZOS produz ruido — cada pixel escolhe a cor mais proxima de forma
independente, sem coerencia com o vizinho, e o resultado fica com aspecto
sujo/apagado em vez de blocos limpos.

A versao atual so reduz com LANCZOS e mantem as cores originais (a
ilustracao de origem ja e cel-shading com paleta enxuta). O resultado e
mais nitido e continua lendo como "jogo" quando ampliado com
image-rendering: pixelated no CSS — cada pixel do arquivo vira um bloco
solido, sem antialiasing do navegador.
"""

import os
from collections import deque

from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.join(RAIZ, "img")
DESTINO_SPRITE = os.path.join(RAIZ, "static", "img", "ilumaquinho")
DESTINO_IMG = os.path.join(RAIZ, "static", "img")

# Paleta da marca
VERMELHO = (195, 25, 34)
VERMELHO_PROFUNDO = (122, 14, 21)


def _vizinhos(x, y, w, h):
    if x > 0:     yield x - 1, y
    if x < w - 1: yield x + 1, y
    if y > 0:     yield x, y - 1
    if y < h - 1: yield x, y + 1


def remover_cenario(im, tolerancia=45):
    """
    Isola o personagem de uma arte que veio como cena.

    Dois passos, porque um so nao resolve:

    1. Preenchimento a partir das bordas: apaga o fundo contiguo (o corpo
       da central de alarme). Segue gradiente suave e para no contorno
       escuro do mascote.
    2. Maior componente conectado: o passo 1 deixa ilhas soltas que a borda
       nao alcanca — o display verde, os textos dos botoes, a haste da
       antena. Como o mascote e o unico blob grande, ficar so com o maior
       componente limpa o resto.
    """
    im = im.copy()
    w, h = im.size
    px = im.load()

    def dist(p, q):
        return abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2])

    # 1) fundo contiguo a partir das bordas
    fundo = [[False] * h for _ in range(w)]
    fila = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not fundo[x][y]:
                fundo[x][y] = True
                fila.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not fundo[x][y]:
                fundo[x][y] = True
                fila.append((x, y))
    while fila:
        x, y = fila.popleft()
        c = px[x, y]
        for nx, ny in _vizinhos(x, y, w, h):
            if not fundo[nx][ny] and dist(px[nx, ny], c) <= tolerancia:
                fundo[nx][ny] = True
                fila.append((nx, ny))
    for x in range(w):
        for y in range(h):
            if fundo[x][y]:
                px[x, y] = (0, 0, 0, 0)

    # 2) so o maior componente conectado sobrevive
    visto = [[False] * h for _ in range(w)]
    maior = []
    for sx in range(w):
        for sy in range(h):
            if visto[sx][sy] or px[sx, sy][3] == 0:
                continue
            grupo = []
            visto[sx][sy] = True
            fila = deque([(sx, sy)])
            while fila:
                x, y = fila.popleft()
                grupo.append((x, y))
                for nx, ny in _vizinhos(x, y, w, h):
                    if not visto[nx][ny] and px[nx, ny][3] > 0:
                        visto[nx][ny] = True
                        fila.append((nx, ny))
            if len(grupo) > len(maior):
                maior = grupo

    manter = set(maior)
    for x in range(w):
        for y in range(h):
            if px[x, y][3] > 0 and (x, y) not in manter:
                px[x, y] = (0, 0, 0, 0)

    caixa = im.getbbox()
    return im.crop(caixa) if caixa else im


def _relatar(caminho, antes=None):
    n = os.path.getsize(caminho)
    im = Image.open(caminho)
    extra = "" if antes is None else "  (origem %.0f KB)" % (antes / 1024)
    print("  %-34s %5.1f KB  %dx%d%s"
          % (os.path.basename(caminho), n / 1024, im.width, im.height, extra))


# ---------------------------------------------------------------------------
# 1. Sprites do Llumaquinho
# ---------------------------------------------------------------------------

def _reduzir(im, altura):
    """
    So reduz com LANCZOS e binariza o alpha. Ver nota tecnica no topo do
    arquivo sobre por que a quantizacao por pixel foi abandonada.
    """
    escala = altura / im.height
    im = im.resize((max(1, round(im.width * escala)), altura), Image.LANCZOS)
    alpha = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    saida = im.convert("RGB").convert("RGBA")
    saida.putalpha(alpha)
    return saida


def pixelar_sprite(origem, destino, altura=128, recorte=None, isolar=False):
    """
    Isola e reduz um personagem para uso como sprite do jogo.

    'recorte' e uma tupla de fracoes (esq, topo, dir, baixo) aplicada depois
    de tirar a moldura transparente. Serve para isolar o mascote quando a
    arte de origem e uma cena: o 'triste' vem sentado na frente de uma
    central de alarme, e sem recorte o mascote ficaria minusculo dentro do
    quadro.
    """
    im = Image.open(origem).convert("RGBA")
    antes = os.path.getsize(origem)

    caixa = im.getbbox()          # tira a moldura transparente
    if caixa:
        im = im.crop(caixa)

    if recorte:
        e, t, d, b = recorte
        im = im.crop((round(im.width * e), round(im.height * t),
                      round(im.width * d), round(im.height * b)))
        caixa = im.getbbox()
        if caixa:
            im = im.crop(caixa)

    if isolar:
        # antes de reduzir: na resolucao cheia o contorno do mascote ainda
        # esta nitido, o que faz o preenchimento parar no lugar certo
        im = remover_cenario(im)

    saida = _reduzir(im, altura)
    saida.save(destino, "PNG", optimize=True)
    _relatar(destino, antes)
    return saida


def compor_triste_na_lyax(origem_mascote, origem_lyax, destino, altura=200):
    """
    O Llumaquinho triste, encostado na Central Lyax de verdade.

    A arte original ja mostra o mascote sentado com os bracos cruzados na
    frente de uma central generica (a legenda no rodape diz "MAX", nao
    "LYAX" — nao e o produto certo). Aqui o mascote e isolado da cena
    original e recomposto encostado na Central Lyax de fato
    (img/Central Lyax.png, que ja vem com fundo transparente — nao
    precisa de remocao de fundo).

    Os dois entram em alta resolucao, so reduzidos no fim (uma unica
    passagem de LANCZOS na composicao final, em vez de duas passagens
    perdendo qualidade cada uma).
    """
    mascote = Image.open(origem_mascote).convert("RGBA")
    caixa = mascote.getbbox()
    if caixa:
        mascote = mascote.crop(caixa)
    # a mesma janela de recorte usada no sprite pequeno, isolando so o
    # mascote sentado no canto inferior esquerdo da cena original
    e, t, d, b = (0.02, 0.31, 0.63, 1.0)
    mascote = mascote.crop((round(mascote.width * e), round(mascote.height * t),
                            round(mascote.width * d), round(mascote.height * b)))
    caixa = mascote.getbbox()
    if caixa:
        mascote = mascote.crop(caixa)
    mascote = remover_cenario(mascote)

    lyax = Image.open(origem_lyax).convert("RGBA")
    caixa = lyax.getbbox()
    if caixa:
        lyax = lyax.crop(caixa)

    # Lyax como pano de fundo: mais alta que o mascote, para dar a
    # sensacao de mobilia — o mascote encosta nela, nao o contrario.
    alt_lyax = int(mascote.height * 1.35)
    esc = alt_lyax / lyax.height
    lyax = lyax.resize((max(1, round(lyax.width * esc)), alt_lyax), Image.LANCZOS)

    # Sobreposicao: o ombro direito do mascote entra por baixo da quina
    # esquerda da central, como se estivesse mesmo apoiado nela.
    sobrepor = int(mascote.width * 0.22)
    largura_total = mascote.width + lyax.width - sobrepor
    altura_total = max(mascote.height, lyax.height)

    cena = Image.new("RGBA", (largura_total, altura_total), (0, 0, 0, 0))
    # a central fica atras, apoiada no chao (base alinhada)
    cena.alpha_composite(lyax, (mascote.width - sobrepor, altura_total - lyax.height))
    # o mascote na frente, tambem com os pes no chao
    cena.alpha_composite(mascote, (0, altura_total - mascote.height))

    caixa = cena.getbbox()
    if caixa:
        cena = cena.crop(caixa)

    saida = _reduzir(cena, altura)
    saida.save(destino, "PNG", optimize=True)
    _relatar(destino)
    return saida


def folha_de_caminhada(quadros, destino):
    """
    Junta os quadros de caminhada numa folha horizontal.

    Uma folha unica evita trocar o src da <img> a cada quadro: o CSS anima
    background-position com steps(), que nao dispara requisicao nem
    recalculo de layout. Num i3 de 2011 isso importa.
    """
    larg = max(q.width for q in quadros)
    alt = max(q.height for q in quadros)
    folha = Image.new("RGBA", (larg * len(quadros), alt), (0, 0, 0, 0))
    for i, q in enumerate(quadros):
        # centraliza cada quadro na sua celula para o mascote nao "pular"
        folha.paste(q, (i * larg + (larg - q.width) // 2, alt - q.height))
    folha.save(destino, "PNG", optimize=True)
    _relatar(destino)
    return larg, alt


# ---------------------------------------------------------------------------
# 2. Chama: recorte da folha do designer
# ---------------------------------------------------------------------------

# A versao anterior desenhava a chama a mao aqui, em ASCII. Foi substituida
# pela arte de img/sprite-fogo.webp (16 quadros num grid 4x4). ATENCAO: a
# folha vem com fundo branco e o numero do quadro impresso em cinza no
# canto — por isso o recorte nao pode ser um simples getbbox().

CHAMA_GRID = 4                       # 4x4 = 16 quadros
CHAMA_ALTURA = 30                    # altura nativa; o CSS so amplia em 2x/3x/4x

# As tres cores reais da arte. Tudo que nao for "quente" (branco do fundo,
# cinza do numero, franja da compressao webp) vira transparente, e o que
# sobra e preso a estas tres — o webp e com perda e espalha dezenas de
# tons intermediarios que sujariam a pixel art.
CHAMA_PALETA = ((255, 200, 48), (251, 139, 6), (249, 58, 1))


def _quente(p):
    r, g, b = p[:3]
    return r > 140 and (r - b) > 60


def _prender_na_paleta(p):
    return min(CHAMA_PALETA,
               key=lambda q: sum(abs(a - b) for a, b in zip(p[:3], q)))


def gerar_chama(origem, destino):
    """
    Folha horizontal de 16 quadros recortada do grid 4x4 do designer.

    O recorte usa uma caixa unica para todos os quadros (a uniao das caixas
    individuais), nao a caixa de cada um: recortado quadro a quadro, cada
    labareda ficaria centrada na propria caixa e a chama pularia de lugar a
    cada troca de quadro.
    """
    im = Image.open(origem).convert("RGB")
    largura_celula = im.width // CHAMA_GRID
    altura_celula = im.height // CHAMA_GRID
    px = im.load()

    def limpar(ox, oy):
        cel = Image.new("RGBA", (largura_celula, altura_celula), (0, 0, 0, 0))
        cp = cel.load()
        for y in range(altura_celula):
            for x in range(largura_celula):
                p = px[ox + x, oy + y]
                if _quente(p):
                    cp[x, y] = _prender_na_paleta(p) + (255,)
        return cel

    total = CHAMA_GRID * CHAMA_GRID
    quadros = [limpar((i % CHAMA_GRID) * largura_celula,
                      (i // CHAMA_GRID) * altura_celula)
               for i in range(total)]

    esq = topo = 10 ** 9
    dir_ = base = -1
    for q in quadros:
        caixa = q.getbbox()
        if caixa:
            esq, topo = min(esq, caixa[0]), min(topo, caixa[1])
            dir_, base = max(dir_, caixa[2]), max(base, caixa[3])

    larg = round((dir_ - esq) * CHAMA_ALTURA / (base - topo))

    def reduzir(q):
        s = q.crop((esq, topo, dir_, base)).resize(
            (larg, CHAMA_ALTURA), Image.LANCZOS)
        sp = s.load()
        for y in range(CHAMA_ALTURA):
            for x in range(larg):
                p = sp[x, y]
                # alpha binario: meio-tom de borda le como sujeira quando o
                # CSS amplia com image-rendering: pixelated
                sp[x, y] = (0, 0, 0, 0) if p[3] < 110 else _prender_na_paleta(p) + (255,)
        return s

    folha = Image.new("RGBA", (larg * total, CHAMA_ALTURA), (0, 0, 0, 0))
    for i, q in enumerate(quadros):
        folha.paste(reduzir(q), (i * larg, 0))
    folha.save(destino, "PNG", optimize=True)
    _relatar(destino, os.path.getsize(origem))
    return larg, CHAMA_ALTURA


# ---------------------------------------------------------------------------
# 3. Elementos decorativos (ja sao pixel art pronta — so recorta e copia)
# ---------------------------------------------------------------------------

def preparar_decorativo(origem, destino):
    """
    Recorta a moldura transparente e salva. Os arquivos em img/ (estrela,
    balao de fogos, seta, logo Iluma Game) ja sao pixel art feita por
    designer — ao contrario dos PNG do Llumaquinho, aqui nao ha reducao
    nem tratamento de cor, so remove a margem vazia ao redor.
    """
    im = Image.open(origem).convert("RGBA")
    antes = os.path.getsize(origem)
    caixa = im.getbbox()
    if caixa:
        im = im.crop(caixa)
    im.save(destino, "PNG", optimize=True)
    _relatar(destino, antes)
    return im


# Altura nativa dos sprites do mascote. O dobro da versao anterior (64px):
# a tecnica sem quantizacao rende muito melhor com mais pixels de origem,
# e o CSS compensa o tamanho do arquivo escalando o multiplicador de
# exibicao para baixo (ver style.css) — o tamanho na tela nao muda.
ALTURA_MASCOTE = 128


def main():
    os.makedirs(DESTINO_SPRITE, exist_ok=True)
    os.makedirs(DESTINO_IMG, exist_ok=True)

    print("Sprites do Llumaquinho (%dpx, sem quantizacao):" % ALTURA_MASCOTE)
    pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-comemoracao.png"),
                   os.path.join(DESTINO_SPRITE, "deu-bom.png"),
                   altura=ALTURA_MASCOTE)
    pixelar_sprite(os.path.join(ORIGEM, "Ilumaquinho-Idle.png"),
                   os.path.join(DESTINO_SPRITE, "idle.png"),
                   altura=ALTURA_MASCOTE)

    print("Llumaquinho com o trofeu (painel admin):")
    pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-trofeu.png"),
                   os.path.join(DESTINO_SPRITE, "trofeu.png"),
                   altura=ALTURA_MASCOTE + 40)

    print("Llumaquinho triste encostado na Central Lyax:")
    compor_triste_na_lyax(
        os.path.join(ORIGEM, "ilumaquinho-triste.png"),
        os.path.join(ORIGEM, "Central Lyax.png"),
        os.path.join(DESTINO_SPRITE, "deu-ruim.png"),
        altura=ALTURA_MASCOTE + 40,  # a cena e mais larga; um pouco mais alta ajuda a leitura
    )

    print("Folha de caminhada (2 quadros, para a animacao de puxar o card):")
    andar = [
        pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-andar-direita.png"),
                       os.path.join(DESTINO_SPRITE, "_andar-1.png"),
                       altura=ALTURA_MASCOTE),
        pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-andar-esquerda.png"),
                       os.path.join(DESTINO_SPRITE, "_andar-2.png"),
                       altura=ALTURA_MASCOTE),
    ]
    larg, alt = folha_de_caminhada(andar, os.path.join(DESTINO_SPRITE, "andando.png"))
    for tmp in ("_andar-1.png", "_andar-2.png"):
        os.remove(os.path.join(DESTINO_SPRITE, tmp))
    print("    -> celula da folha: %dx%d" % (larg, alt))

    print("Chama da barra de progresso (16 quadros da folha do designer):")
    clarg, calt = gerar_chama(os.path.join(DESTINO_IMG, "sprite-fogo.webp"),
                              os.path.join(DESTINO_IMG, "chama.png"))
    print("    -> celula da folha: %dx%d" % (clarg, calt))

    print("Elementos decorativos (tela de abertura):")
    preparar_decorativo(os.path.join(ORIGEM, "Ativo 2.png"),
                        os.path.join(DESTINO_IMG, "ilumagame.png"))
    preparar_decorativo(os.path.join(ORIGEM, "ESTRELA.png"),
                        os.path.join(DESTINO_IMG, "estrela.png"))
    preparar_decorativo(os.path.join(ORIGEM, "BALÃO_FOGOS.png"),
                        os.path.join(DESTINO_IMG, "balao-fogos.png"))
    preparar_decorativo(os.path.join(ORIGEM, "SETA.png"),
                        os.path.join(DESTINO_IMG, "seta.png"))


if __name__ == "__main__":
    main()
