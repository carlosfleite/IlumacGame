# -*- coding: utf-8 -*-
"""
Gerador do sprite de chama do Quiz SDAI (static/img/chama.png).

NAO faz parte do runtime do totem. Roda so quando a chama precisar mudar,
numa maquina de desenvolvimento:

    pip install Pillow
    python tools/gerar_chama.py

Por que gerar em vez de desenhar a mao num editor: a silhueta e feita por
coluna (altura em "pixels" logicos por coluna, uma lista por quadro), o
que da controle fino sobre as linguas de fogo sem depender de arrastar
pixel por pixel. As cores vem das mesmas variaveis --fogo-* do
style.css (nucleo/medio/borda), sem overlay ou dithering — bandas solidas
por altura relativa da coluna, para ficar legivel no tamanho pequeno em
que a chama e exibida no jogo (~50-95px de altura).

Sprite: 4 quadros de 16x22, lado a lado (64x22 total). O CSS anima
trocando background-position entre os quadros (steps) e aplica sway/vida
de cor por cima (static/css/style.css, regra .chama).
"""

from PIL import Image

W = 16   # colunas por quadro
H = 22   # altura da grade
FRAMES = 4

NUCLEO = (255, 244, 200, 255)
NUCLEO2 = (255, 214, 120, 255)
MEDIO = (255, 166, 40, 255)
MEDIO2 = (240, 110, 24, 255)
BORDA = (226, 51, 32, 255)
BORDA2 = (150, 26, 16, 255)

# Altura (em linhas) de cada coluna, por quadro — silhueta irregular com
# linguas de fogo, desenhada a mao para nao virar um triangulo simetrico.
COL_HEIGHTS = [
    #  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
    [4, 7, 10, 13, 16, 18, 19, 17, 20, 18, 15, 13, 10, 8, 5, 3],   # quadro 0
    [3, 6, 9, 12, 15, 17, 20, 19, 17, 19, 17, 14, 11, 8, 5, 3],    # quadro 1: pico central mais alto
    [4, 6, 9, 13, 16, 19, 18, 16, 18, 20, 16, 13, 10, 7, 5, 3],    # quadro 2: pico desloca p/ direita
    [3, 7, 10, 13, 15, 18, 19, 18, 16, 17, 15, 13, 11, 8, 6, 3],   # quadro 3: intermediario
]


def make_frame(idx):
    heights = COL_HEIGHTS[idx]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for x in range(W):
        h = heights[x]
        for row in range(h):
            y = H - 1 - row
            t = row / max(h - 1, 1)  # 0 na base da coluna, 1 no topo
            if t < 0.30:
                col = NUCLEO
            elif t < 0.48:
                col = NUCLEO2
            elif t < 0.68:
                col = MEDIO
            elif t < 0.85:
                col = MEDIO2
            elif t < 0.96:
                col = BORDA
            else:
                col = BORDA2
            px[x, y] = col
        if h > 0:
            px[x, H - 1] = BORDA2  # base sempre em vermelho profundo
    return img


def main():
    frames = [make_frame(i) for i in range(FRAMES)]
    sheet = Image.new("RGBA", (W * FRAMES, H), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * W, 0), frame)
    sheet.save("static/img/chama.png")
    print("static/img/chama.png gerado:", sheet.size)


if __name__ == "__main__":
    main()
