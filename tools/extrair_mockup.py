"""
Extrai os vetores do mockup do marketing (GAME_QUIZZ_TUDO_SOBRE_SDAI.ai) para
SVGs que o jogo usa direto — assim o fundo, o título, o mascote e as medalhas
são os desenhos originais, e não uma releitura.

O .ai é compatível com PDF: cada prancheta é uma página 1080x1920 (o tamanho
exato do totem), e quase tudo é vetor. O script lê os caminhos com PyMuPDF e
reescreve em SVG, filtrando por região:

  · fundo de cada tela = tudo da prancheta MENOS as regiões de conteúdo
    (textos, cartões, mascote, botões), que o HTML desenha por cima;
  · peças soltas (mascote, troféu, medalhas...) = só o que cai dentro da
    região informada, recortado no próprio tamanho.

Máscaras de recorte do Illustrator viram clipPath no SVG, e o que uma
máscara esconde por inteiro nem é exportado (o .ai tem desenhos guardados
atrás de máscaras vazias, que no mockup não aparecem).

Uso (PyMuPDF não é dependência do jogo, só desta ferramenta):
    pip install pymupdf
    python tools/extrair_mockup.py caminho/para/GAME_QUIZZ_TUDO_SOBRE_SDAI.ai
"""
import json
import os
import sys

import pymupdf as fitz

DESTINO = os.path.join(os.path.dirname(__file__), "..", "static", "img", "mockup")


def cor(c):
    if c is None:
        return "none"
    r, g, b = (max(0, min(255, round(v * 255))) for v in c[:3])
    return "#%02x%02x%02x" % (r, g, b)


def num(v):
    s = "%.2f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def caminho(d, dx, dy):
    partes = []
    atual = None

    def pt(p):
        return "%s %s" % (num(p.x - dx), num(p.y - dy))

    for it in d["items"]:
        op = it[0]
        if op == "l":
            a, b = it[1], it[2]
            if atual is None or abs(atual.x - a.x) > 0.01 or abs(atual.y - a.y) > 0.01:
                partes.append("M" + pt(a))
            partes.append("L" + pt(b))
            atual = b
        elif op == "c":
            a, c1, c2, b = it[1], it[2], it[3], it[4]
            if atual is None or abs(atual.x - a.x) > 0.01 or abs(atual.y - a.y) > 0.01:
                partes.append("M" + pt(a))
            partes.append("C" + pt(c1) + " " + pt(c2) + " " + pt(b))
            atual = b
        elif op == "re":
            r = it[1]
            partes.append("M%s %sh%sv%sh%sz" % (
                num(r.x0 - dx), num(r.y0 - dy), num(r.width), num(r.height), num(-r.width)))
            atual = None
        elif op == "qu":
            q = it[1]
            partes.append("M" + pt(q.ul) + "L" + pt(q.ur) + "L" + pt(q.lr) + "L" + pt(q.ll) + "z")
            atual = None
    if d.get("closePath"):
        partes.append("z")
    return "".join(partes)


_cache = {}


def _e_retangulo(clip):
    """A máscara é um retângulo alinhado (então o scissor já a descreve)?"""
    itens = clip["items"]
    if len(itens) == 1 and itens[0][0] == "re":
        return True
    return all(it[0] == "l" and (abs(it[1].x - it[2].x) < 0.01 or abs(it[1].y - it[2].y) < 0.01)
               for it in itens)


def desenhos(pagina):
    """
    Os caminhos visíveis da prancheta, na ordem de pintura, cada um com as
    máscaras que o recortam ("_clips") e o retângulo que de fato aparece
    ("rect", já cortado pelas máscaras).

    No get_drawings(extended=True) uma máscara de nível N vale para tudo
    que vem depois com nível maior que N, até aparecer algo de nível <= N.
    """
    chave = (id(pagina.parent), pagina.number)
    if chave in _cache:
        return _cache[chave]
    pilha, saida, n = [], [], 0
    for x in pagina.get_drawings(extended=True):
        while pilha and pilha[-1]["level"] >= x["level"]:
            pilha.pop()
        if x["type"] == "clip":
            n += 1
            x["_id"] = "m%d_%d" % (pagina.number, n)
            pilha.append(x)
            continue
        if x["type"] == "group":
            continue
        visivel = fitz.Rect(x["rect"])
        for c in pilha:
            visivel &= fitz.Rect(c["scissor"])
        if visivel.is_empty or visivel.width <= 0.01 or visivel.height <= 0.01:
            continue  # escondido por inteiro pela máscara
        d = dict(x)
        d["_original"] = fitz.Rect(x["rect"])
        d["rect"] = visivel
        # só guarda as máscaras que realmente cortam alguma coisa do desenho
        d["_clips"] = tuple(
            c for c in pilha
            if not (d["_original"] in fitz.Rect(c["scissor"]) and _e_retangulo(c))
        )
        saida.append(d)
    _cache[chave] = saida
    return saida


def elemento(d, dx, dy, defs=None):
    """<path> do desenho, dentro de um <g clip-path> para cada máscara."""
    svg = _caminho_svg(d, dx, dy)
    for c in reversed(d.get("_clips", ())):
        cid = "%s_%s_%s" % (c["_id"], num(dx).replace(".", "p"), num(dy).replace(".", "p"))
        if defs is not None and cid not in defs:
            regra = ' clip-rule="evenodd"' if c.get("even_odd") else ""
            defs[cid] = '<clipPath id="%s"><path d="%s"%s/></clipPath>' % (cid, caminho(c, dx, dy), regra)
        svg = '<g clip-path="url(#%s)">%s</g>' % (cid, svg)
    return svg


def _caminho_svg(d, dx, dy):
    attrs = ['d="%s"' % caminho(d, dx, dy)]
    t = d["type"]
    r = d["rect"]
    if t == "f" and r.width >= 1079 and d.get("fill") is not None:
        # Faixas do degradê de fundo: encostam uma na outra, e o
        # antisserrilhado da rasterização deixava um fio claro na junção.
        # Um traço da mesma cor fecha a costura.
        attrs.append('fill="%s" stroke="%s" stroke-width="2"' % (cor(d["fill"]), cor(d["fill"])))
        return "<path %s/>" % " ".join(attrs)
    if "f" in t and d.get("fill") is not None:
        attrs.append('fill="%s"' % cor(d["fill"]))
        if d.get("even_odd"):
            attrs.append('fill-rule="evenodd"')
        op = d.get("fill_opacity")
        if op is not None and op < 1:
            attrs.append('fill-opacity="%s"' % num(op))
    else:
        attrs.append('fill="none"')
    if "s" in t and d.get("color") is not None:
        attrs.append('stroke="%s"' % cor(d["color"]))
        attrs.append('stroke-width="%s"' % num(d.get("width") or 1))
        op = d.get("stroke_opacity")
        if op is not None and op < 1:
            attrs.append('stroke-opacity="%s"' % num(op))
        caps = {0: "butt", 1: "round", 2: "square"}
        lc = d.get("lineCap")
        if isinstance(lc, (tuple, list)):
            lc = lc[0]
        if lc in (1, 2):
            attrs.append('stroke-linecap="%s"' % caps[lc])
        lj = d.get("lineJoin")
        if lj == 1:
            attrs.append('stroke-linejoin="round"')
        elif lj == 2:
            attrs.append('stroke-linejoin="bevel"')
        else:
            attrs.append('stroke-miterlimit="10"')
    return "<path %s/>" % " ".join(attrs)


def dentro(r, zona, folga=1.0):
    return (r.x0 >= zona[0] - folga and r.y0 >= zona[1] - folga
            and r.x1 <= zona[2] + folga and r.y1 <= zona[3] + folga)


def cruza(r, zona):
    return not (r.x1 <= zona[0] or r.x0 >= zona[2] or r.y1 <= zona[1] or r.y0 >= zona[3])


def salvar(nome, largura, altura, corpo, defs=None):
    os.makedirs(DESTINO, exist_ok=True)
    defs_svg = "<defs>%s</defs>" % "".join(defs.values()) if defs else ""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s">%s%s</svg>'
           % (num(largura), num(altura), num(largura), num(altura), defs_svg, "".join(corpo)))
    with open(os.path.join(DESTINO, nome), "w", encoding="utf-8") as f:
        f.write(svg)
    print("%-28s %6.1f KB" % (nome, len(svg) / 1024))


def fundo(pagina, nome, tirar=(), manter=None, pular=()):
    """Prancheta inteira, sem os caminhos contidos nas zonas `tirar` nem os
    de índice em `pular`. `manter(i, d)` pode forçar a permanência."""
    corpo, defs = [], {}
    for i, d in enumerate(desenhos(pagina)):
        r = d["rect"]
        if i in pular:
            continue
        if manter and manter(i, d):
            corpo.append(elemento(d, 0, 0, defs))
            continue
        if any(dentro(r, z) for z in tirar):
            continue
        corpo.append(elemento(d, 0, 0, defs))
    salvar(nome, 1080, 1920, corpo, defs)


def peca(pagina, nome, zona, filtro=None, margem=0):
    """Só o que cabe inteiro em `zona`, recortado no tamanho da zona."""
    corpo, defs = [], {}
    x0, y0 = zona[0] - margem, zona[1] - margem
    for i, d in enumerate(desenhos(pagina)):
        if not dentro(d["rect"], zona):
            continue
        if filtro and not filtro(i, d):
            continue
        corpo.append(elemento(d, x0, y0, defs))
    salvar(nome, zona[2] - zona[0] + 2 * margem, zona[3] - zona[1] + 2 * margem, corpo, defs)


def decoracao(pagina, prefixo, tirar):
    """Separa a decoração em pixel (setas, X, blocos) do fundo, uma peça
    por grupo de caminhos encostados, para o CSS animar cada uma.
    Devolve os índices usados (para o fundo pular) e a lista de peças com
    a posição na prancheta."""
    grupos = []
    for i, d in enumerate(desenhos(pagina)):
        r = d["rect"]
        if r.width >= 1079 or any(dentro(r, z) for z in tirar):
            continue  # faixa do degradê, conteúdo, logos ou título
        grupos.append([r.x0, r.y0, r.x1, r.y1, [i]])
    juntou = True
    while juntou:
        juntou = False
        saida = []
        for g in grupos:
            for o in saida:
                if not (g[2] + 3 < o[0] or g[0] - 3 > o[2] or g[3] + 3 < o[1] or g[1] - 3 > o[3]):
                    o[0], o[1] = min(o[0], g[0]), min(o[1], g[1])
                    o[2], o[3] = max(o[2], g[2]), max(o[3], g[3])
                    o[4] += g[4]
                    juntou = True
                    break
            else:
                saida.append(g)
        grupos = saida

    lista = desenhos(pagina)
    pecas, usados = [], set()
    for n, (x0, y0, x1, y1, idx) in enumerate(sorted(grupos, key=lambda g: (g[1], g[0]))):
        nome = "deco-%s-%d.svg" % (prefixo, n + 1)
        idx = sorted(idx)
        defs = {}
        corpo = [elemento(lista[i], x0, y0, defs) for i in idx]
        salvar(nome, x1 - x0, y1 - y0, corpo, defs)
        usados.update(idx)
        pecas.append({"src": nome, "x": round(x0, 1), "y": round(y0, 1),
                      "w": round(x1 - x0, 1), "h": round(y1 - y0, 1)})
    return usados, pecas


def rasterizar(nome):
    """Troca o SVG por PNG 1:1. Os fundos e o título têm milhares de
    caminhos (as hachuras 3D do SDAI): como SVG passam de 600 KB e custam
    caro para redesenhar na Intel HD do totem; como PNG no tamanho exato
    da tela ficam nítidos e leves."""
    svg = os.path.join(DESTINO, nome)
    png = svg[:-4] + ".png"
    pix = fitz.open(svg)[0].get_pixmap(alpha=not nome.startswith("fundo"))
    pix.save(png)
    os.remove(svg)
    print("%-28s %6.1f KB" % (os.path.basename(png), os.path.getsize(png) / 1024))


def main(caminho_ai):
    doc = fitz.open(caminho_ai)
    # índice das pranchetas no .ai
    ABERTURA, RANK_GERAL, RANK_DIA, CADASTRO, _TECLADO, REGRAS, RESULTADO, CERTO, ERRADO = range(9)

    # Zonas de conteúdo (coordenadas da prancheta, px do totem)
    ZONAS = {
        ABERTURA: [(150, 280, 940, 1720)],
        RANK_DIA: [(60, 380, 1060, 1830)],
        CADASTRO: [(150, 380, 960, 1600)],
        REGRAS: [(250, 380, 870, 1900)],
        RESULTADO: [(250, 370, 870, 1560), (150, 1700, 960, 1800)],
        CERTO: [(180, 400, 900, 1900)],
        ERRADO: [(180, 400, 900, 1900)],
    }

    def painel(i, d):
        # o painel vermelho central atravessa as zonas: fica sempre no fundo
        return d["rect"].width > 700 and d["rect"].height > 1000

    fundo(doc[ABERTURA], "fundo-abertura.svg", ZONAS[ABERTURA], painel)
    # sem o balão de chamas do canto: ele só existe na aba do ranking geral
    # e ficaria cortado atrás da lista do dia
    fundo(doc[RANK_GERAL], "fundo-ranking.svg", ZONAS[RANK_DIA] + [(860, 1500, 1400, 1740)], painel)
    fundo(doc[CADASTRO], "fundo-cadastro.svg", ZONAS[CADASTRO], painel)
    fundo(doc[REGRAS], "fundo-regras.svg", ZONAS[REGRAS], painel)
    # Na faixa dos botões, o X do canto encosta no "VER RANKING": os
    # quadradinhos dele (pixel da arte, < 40px) ficam; só a forma dos
    # botões sai, porque o HTML desenha os botões por cima.
    fundo(doc[RESULTADO], "fundo-resultado.svg", ZONAS[RESULTADO],
          lambda i, d: painel(i, d) or (d["rect"].y0 >= 1700 and d["rect"].width < 40))
    # Acerto e erro: setas e X saem do fundo e viram peças soltas, que o
    # feedback anima (setas sobem no acerto, X balançam no erro).
    logos_titulo = (80, 55, 1000, 360)
    deco = {}
    for pag, chave in ((CERTO, "certo"), (ERRADO, "errado")):
        usados, deco[chave] = decoracao(doc[pag], chave, ZONAS[pag] + [logos_titulo])
        fundo(doc[pag], "fundo-%s.svg" % chave, ZONAS[pag], painel, usados)
    js = os.path.join(os.path.dirname(__file__), "..", "static", "js", "deco-mockup.js")
    with open(js, "w", encoding="utf-8") as f:
        f.write("// Gerado por tools/extrair_mockup.py: decoração das telas de acerto e\n"
                "// erro, com a posição de cada peça na prancheta (px do totem).\n"
                "window.DECO_MOCKUP = %s;\n" % json.dumps(deco, indent=2))

    # Peças soltas
    peca(doc[ABERTURA], "titulo-grande.svg", (215, 280, 905, 830))
    # A sombra do mascote é vinho sólido na prancheta vermelha; translúcida,
    # ela assume o tom de qualquer fundo (no verde do acerto, inclusive).
    peca(doc[ABERTURA], "mascote.svg", (380, 1270, 700, 1670),
         lambda i, d: True)
    arq = os.path.join(DESTINO, "mascote.svg")
    with open(arq, encoding="utf-8") as f:
        svg = f.read()
    svg = svg.replace(
        'fill="#70000e" stroke="#70000e" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"',
        'fill="#000" fill-opacity=".38"', 1)
    with open(arq, "w", encoding="utf-8") as f:
        f.write(svg)
    peca(doc[RANK_DIA], "trofeu.svg", (180, 600, 350, 752))
    peca(doc[RANK_DIA], "medalha-2.svg", (200, 755, 315, 875))
    peca(doc[RANK_DIA], "medalha-3.svg", (200, 875, 315, 995))
    # a 4ª medalha da lista do dia tem um caminho que vaza a zona; a da
    # lista do ranking geral é o mesmo desenho, inteira
    peca(doc[RANK_GERAL], "medalha-n.svg", (190, 1050, 310, 1170))

    # Moldes de interface (cor e contorno pixelado originais)
    grande = lambda i, d: d["rect"].width > 150
    peca(doc[ABERTURA], "btn-escuro.svg", (330, 1060, 750, 1205))
    peca(doc[RESULTADO], "btn-escuro-p.svg", (160, 1720, 482, 1795))
    peca(doc[RESULTADO], "btn-contorno.svg", (477, 1720, 918, 1795))
    peca(doc[RANK_GERAL], "aba-cheia.svg", (470, 490, 970, 566))
    peca(doc[RANK_GERAL], "aba-contorno.svg", (108, 490, 465, 566))
    peca(doc[RANK_GERAL], "podio-card-1.svg", (360, 595, 720, 1012), grande)
    peca(doc[RANK_GERAL], "podio-card-2.svg", (65, 660, 355, 990), grande)
    peca(doc[RANK_DIA], "linha-ranking.svg", (276, 998, 898, 1101), lambda i, d: d["rect"].x0 >= 279)
    peca(doc[CADASTRO], "caixa-lgpd.svg", (212, 984, 864, 1186))
    peca(doc[CADASTRO], "balao-fala.svg", (405, 1206, 860, 1308))
    peca(doc[REGRAS], "moldura-regra.svg", (272, 494, 824, 760), grande)
    peca(doc[REGRAS], "selo-numero.svg", (255, 478, 362, 582), lambda i, d: d["rect"].width < 150)
    peca(doc[RESULTADO], "moldura-premio.svg", (272, 1074, 826, 1340))
    peca(doc[CERTO], "selo-pontos-certo.svg", (400, 698, 683, 785))
    peca(doc[ERRADO], "selo-pontos-errado.svg", (400, 698, 683, 785))
    peca(doc[CERTO], "btn-toque.svg", (278, 1720, 802, 1795))

    # Balão com chamas do canto do ranking geral (prancheta 2). Sai do fundo
    # porque só aparece nessa aba; a parte que passa da borda da prancheta
    # é cortada pelo próprio palco.
    peca(doc[RANK_GERAL], "baloes-fogo.svg", (860, 1500, 1400, 1740),
         lambda i, d: d["rect"].width < 1079 and not painel(i, d))

    for nome in sorted(os.listdir(DESTINO)):
        if nome.endswith(".svg") and (nome.startswith("fundo") or nome in ("titulo-grande.svg", "baloes-fogo.svg")):
            rasterizar(nome)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
