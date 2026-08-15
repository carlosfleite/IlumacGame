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
# a = amarelo claro (nucleo)  b = laranja  c = vermelho  d = vermelho escuro
CHAMA_QUADROS = [
    [
        "....dd....",
        "...dccd...",
        "..dcbbcd..",
        "..dcbbcd..",
        ".dcbaabcd.",
        ".dcbaabcd.",
        "dcbaaaabcd",
        "dcbaaaabcd",
        ".dcbaabcd.",
        "..dccccd..",
        "...dccd...",
        "....dd....",
    ],
    [
        "...ddd....",
        "..ddccd...",
        "..dcbbcd..",
        ".dcbbbcd..",
        ".dcbaabcd.",
        "dcbaaabcd.",
        "dcbaaaabcd",
        ".dcbaaabcd",
        "..dcbaabcd",
        "..dccccd..",
        "...dccd...",
        "....dd....",
    ],
    [
        "....ddd...",
        "...dccdd..",
        "..dcbbcd..",
        "..dcbbbcd.",
        ".dcbaabcd.",
        ".dcbaaabcd",
        "dcbaaaabcd",
        "dcbaaabcd.",
        "dcbaabcd..",
        "..dccccd..",
        "...dccd...",
        "....dd....",
    ],
]

PALETA_CHAMA = {
    "a": (255, 236, 170, 255),
    "b": (255, 168, 46, 255),
    "c": (229, 57, 34, 255),
    "d": (138, 20, 26, 255),
    ".": (0, 0, 0, 0),
}


def gerar_chama(destino):
    """Folha horizontal com os 3 quadros da chama."""
    alt = len(CHAMA_QUADROS[0])
    larg = len(CHAMA_QUADROS[0][0])
    folha = Image.new("RGBA", (larg * len(CHAMA_QUADROS), alt), (0, 0, 0, 0))
    px = folha.load()
    for i, quadro in enumerate(CHAMA_QUADROS):
        for y, linha in enumerate(quadro):
            for x, ch in enumerate(linha):
                px[i * larg + x, y] = PALETA_CHAMA[ch]
    folha.save(destino, "PNG", optimize=True)
    _relatar(destino)
    return larg, alt


# ---------------------------------------------------------------------------
# 3. Fundo: o brasao em pixels
# ---------------------------------------------------------------------------

def _contorno_brasao(d, cx, cy, w, h, cor, espessura):
    """Desenha o contorno do escudo como polilinha (vira degrau na grade baixa)."""
    pontos = []
    meio = w / 2
    ombro = cy + h * 0.16
    pontos.append((cx - meio, cy - h / 2))
    pontos.append((cx + meio, cy - h / 2))
    pontos.append((cx + meio, ombro))
    # ponta inferior arredondada, amostrada em poucos passos
    for i in range(1, 13):
        t = i / 12
        x = cx + meio * (1 - t) ** 2 + cx * 0 + (cx - cx) * t
        # bezier quadratica: P0=(cx+meio,ombro) P1=(cx+meio,cy+h/2) P2=(cx,cy+h/2)
        bx = (1 - t) ** 2 * (cx + meio) + 2 * (1 - t) * t * (cx + meio) + t ** 2 * cx
        by = (1 - t) ** 2 * ombro + 2 * (1 - t) * t * (cy + h / 2) + t ** 2 * (cy + h / 2)
        pontos.append((bx, by))
    for i in range(1, 13):
        t = i / 12
        bx = (1 - t) ** 2 * cx + 2 * (1 - t) * t * (cx - meio) + t ** 2 * (cx - meio)
        by = (1 - t) ** 2 * (cy + h / 2) + 2 * (1 - t) * t * (cy + h / 2) + t ** 2 * ombro
        pontos.append((bx, by))
    pontos.append((cx - meio, cy - h / 2))
    d.line(pontos, fill=cor, width=espessura, joint=None)


def gerar_fundo(destino, larg=108, alt=192):
    """
    Padrao do brasao numa grade baixa (108x192 = 1/10 do totem).

    Exibido com background-size: cover e image-rendering: pixelated, cada
    pixel daqui vira um bloco de 10x10 na tela. O arquivo fica na casa de
    poucos KB e o navegador rasteriza uma vez so.
    """
    im = Image.new("RGBA", (larg, alt), VERMELHO + (255,))
    d = ImageDraw.Draw(im)

    claro = (214, 62, 70, 255)   # vermelho levemente mais claro
    escuro = (168, 20, 28, 255)  # vermelho levemente mais escuro

    # dois escudos concentricos grandes
    _contorno_brasao(d, larg * 0.5, alt * 0.46, larg * 0.62, alt * 0.60, claro, 1)
    _contorno_brasao(d, larg * 0.5, alt * 0.46, larg * 0.44, alt * 0.44, escuro, 1)

    # riscos longos acompanhando a curvatura do escudo
    for (x0, y0, x1, y1, x2, y2) in [
        (-20, 18, 34, 52, 44, 190),
        (128, 12, 74, 46, 66, 196),
        (-14, 70, 32, 84, 54, 122),
        (122, 62, 78, 76, 58, 116),
    ]:
        pts = []
        for i in range(41):
            t = i / 40
            bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t ** 2 * x2
            by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t ** 2 * y2
            pts.append((bx, by))
        d.line(pts, fill=claro, width=1)

    # dithering leve nos cantos: textura de pixel art sem custo de render
    px = im.load()
    for y in range(alt):
        for x in range(larg):
            borda = min(x, larg - 1 - x) / (larg / 2)
            topo = min(y, alt - 1 - y) / (alt / 2)
            if (x + y) % 2 == 0 and borda < 0.32 and topo < 0.42:
                r, g, b, a = px[x, y]
                px[x, y] = (max(0, r - 14), max(0, g - 6), max(0, b - 6), a)

    im.save(destino, "PNG", optimize=True)
    _relatar(destino)


# ---------------------------------------------------------------------------

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

    print("Fundo do brasao em pixels:")
    gerar_fundo(os.path.join(DESTINO_IMG, "padrao-brasao.png"))


if __name__ == "__main__":
    main()
