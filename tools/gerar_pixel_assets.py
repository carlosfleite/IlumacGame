# -*- coding: utf-8 -*-
"""
Gerador dos assets em pixel art do Quiz SDAI.

NAO faz parte do runtime do totem. Roda so quando a marca muda, numa
maquina de desenvolvimento:

    pip install Pillow
    python tools/gerar_pixel_assets.py

Por que gerar em vez de versionar so o resultado: os PNG de marca em img/
sao ilustracoes suaves em alta resolucao. A estetica do jogo e pixel art,
entao cada sprite precisa ser reduzido a uma grade baixa e ter a paleta
achatada. Fazer isso na mao e irreproduzivel; aqui fica documentado.

Tecnica: reduzir com LANCZOS (media boa de cor), achatar a paleta com
quantizacao sem dithering (pixel art tem cor chapada, nao ruido) e exibir
ampliado com image-rendering: pixelated no CSS. O navegador faz o upscale
em nearest-neighbor, entao cada pixel do arquivo vira um bloco nitido.
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

def pixelar_sprite(origem, destino, altura=64, cores=24, recorte=None,
                   isolar=False):
    """
    Reduz a ilustracao a uma grade baixa com paleta chapada.

    'recorte' e uma tupla de fracoes (esq, topo, dir, baixo) aplicada depois
    de tirar a moldura transparente. Serve para isolar o mascote quando a
    arte de origem e uma cena: o 'triste' vem sentado na frente de uma
    central de alarme, e sem recorte o mascote ficaria minusculo dentro do
    quadro, ilegivel nos 64px do sprite.
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

    escala = altura / im.height
    im = im.resize((max(1, round(im.width * escala)), altura), Image.LANCZOS)

    # Quantiza so as cores visiveis; o alpha vira binario para a silhueta
    # ficar recortada como pixel art, sem borda meio-transparente.
    alpha = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    rgb = im.convert("RGB").quantize(colors=cores, dither=Image.Dither.NONE)
    saida = rgb.convert("RGBA")
    saida.putalpha(alpha)

    saida.save(destino, "PNG", optimize=True)
    _relatar(destino, antes)
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
# 2. Chama em pixel art (desenhada a mao, nao derivada de foto)
# ---------------------------------------------------------------------------

# . = transparente
# a = nucleo claro   b = laranja   c = vermelho   d = contorno escuro
CHAMA_BASE = [
    ".......dd.......",
    "......dccd......",
    "......dccd......",
    ".....dcbbcd.....",
    ".....dcbbcd.....",
    "....dcbaabcd....",
    "....dcbaabcd....",
    "...dcbaaaabcd...",
    "...dcbaaaabcd...",
    "..dcbaaaaaabcd..",
    "..dcbaaaaaabcd..",
    ".dcbaaaaaaaabcd.",
    ".dcbaaaaaaaabcd.",
    "dcbaaaaaaaaaabcd",
    "dcbaaaaaaaaaabcd",
    "dcbaaaaaaaaaabcd",
    ".dcbaaaaaaaabcd.",
    "..dcbbbbbbbbcd..",
    "...dcccccccd....",
    "....ddddddd.....",
]

PALETA_CHAMA = {
    "a": (255, 240, 186, 255),
    "b": (255, 166, 40, 255),
    "c": (226, 51, 32, 255),
    "d": (122, 14, 21, 255),
    ".": (0, 0, 0, 0),
}

# A ponta balanca: os quadros so deslocam as linhas de cima, o que mantem
# a base plantada e da o movimento de labareda sem redesenhar tudo.
INCLINACAO = (0, -1, 1)
LINHAS_DA_PONTA = 7


def _desloca(linha, dx):
    if dx == 0:
        return linha
    if dx < 0:
        return linha[-dx:] + "." * (-dx)
    return "." * dx + linha[:-dx]


def gerar_chama(destino):
    """Folha horizontal com os quadros da chama."""
    alt = len(CHAMA_BASE)
    larg = len(CHAMA_BASE[0])
    assert all(len(l) == larg for l in CHAMA_BASE), "linhas de tamanhos diferentes"

    folha = Image.new("RGBA", (larg * len(INCLINACAO), alt), (0, 0, 0, 0))
    px = folha.load()
    for i, dx in enumerate(INCLINACAO):
        for y, linha in enumerate(CHAMA_BASE):
            atual = _desloca(linha, dx) if y < LINHAS_DA_PONTA else linha
            for x, ch in enumerate(atual):
                px[i * larg + x, y] = PALETA_CHAMA[ch]
    folha.save(destino, "PNG", optimize=True)
    _relatar(destino)
    return larg, alt


def main():
    os.makedirs(DESTINO_SPRITE, exist_ok=True)
    os.makedirs(DESTINO_IMG, exist_ok=True)

    print("Sprites do Llumaquinho (64px, paleta chapada):")
    pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-comemoracao.png"),
                   os.path.join(DESTINO_SPRITE, "deu-bom.png"))
    # a arte triste e uma cena; isola o mascote no canto inferior esquerdo
    pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-triste.png"),
                   os.path.join(DESTINO_SPRITE, "deu-ruim.png"),
                   recorte=(0.02, 0.31, 0.63, 1.0), isolar=True)
    pixelar_sprite(os.path.join(ORIGEM, "Ilumaquinho-Idle.png"),
                   os.path.join(DESTINO_SPRITE, "idle.png"))

    print("Folha de caminhada (2 quadros, para a animacao de puxar o card):")
    andar = [
        pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-andar-direita.png"),
                       os.path.join(DESTINO_SPRITE, "_andar-1.png")),
        pixelar_sprite(os.path.join(ORIGEM, "ilumaquinho-andar-esquerda.png"),
                       os.path.join(DESTINO_SPRITE, "_andar-2.png")),
    ]
    larg, alt = folha_de_caminhada(andar, os.path.join(DESTINO_SPRITE, "andando.png"))
    for tmp in ("_andar-1.png", "_andar-2.png"):
        os.remove(os.path.join(DESTINO_SPRITE, tmp))
    print("    -> celula da folha: %dx%d" % (larg, alt))

    print("Chama da barra de progresso:")
    clarg, calt = gerar_chama(os.path.join(DESTINO_IMG, "chama.png"))
    print("    -> celula da folha: %dx%d" % (clarg, calt))



if __name__ == "__main__":
    main()
