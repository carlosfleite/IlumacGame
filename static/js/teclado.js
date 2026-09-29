/**
 * Teclado virtual do totem.
 *
 * POR QUE NAO USAR O TECLADO DO WINDOWS
 * Ele depende de tres coisas que nao controlamos no dia do evento: a
 * configuracao do SO, nao haver teclado fisico plugado, e a altura da
 * janela dele. Pior: e uma janela POR CIMA, entao a pagina nem fica
 * sabendo que abriu — no retrato 1080x1920 ele come ~768px e engole o
 * botao Continuar, sem nada rolar para compensar.
 *
 * Aqui a altura e nossa: o teclado ocupa a faixa de baixo do palco
 * (prancheta 5 do mockup), abaixo dos campos e do botao Continuar.
 *
 * Alimenta os campos disparando eventos "input" de verdade, senao a
 * mascara de telefone e a limpeza de erro do cadastro.js nao rodariam.
 */
(function () {
  "use strict";

  var form = document.getElementById("form-cadastro");
  if (!form) return;

  var alvos = Array.prototype.slice.call(
    form.querySelectorAll('input[type="text"], input[type="tel"], input[type="email"]')
  );
  if (!alvos.length) return;

  // ---------------------------------------------------------------------
  // Layouts
  // ---------------------------------------------------------------------
  // t = texto da tecla · a = acao · s = quantas colunas ocupa (padrao 2,
  // porque a grade tem 20 colunas para caber meias-teclas nas bordas).

  function letras(str) {
    return str.split(" ").map(function (c) { return { t: c }; });
  }

  var LAYOUTS = {
    texto: {
      colunas: 20,
      linhas: [
        letras("1 2 3 4 5 6 7 8 9 0"),
        letras("Q W E R T Y U I O P"),
        letras("A S D F G H J K L Ç"),
        [{ t: "⇧", a: "maiusc", s: 3 }].concat(
          letras("Z X C V B N M"),
          [{ t: "⌫", a: "apagar", s: 3 }]
        ),
        [
          { t: "ÁÉÍ", a: "modo:acentos", s: 3 },
          { t: "@" },
          { t: "ESPAÇO", a: "espaco", s: 8 },
          { t: "." },
          { t: "PRÓXIMO →", a: "proximo", s: 5 },
        ],
      ],
    },

    acentos: {
      colunas: 20,
      linhas: [
        letras("Á À Â Ã É Ê Í Ó Ô Õ"),
        [].concat(
          letras("Ú Ü Ç Ñ"),
          [
            { t: "ESPAÇO", a: "espaco", s: 6 },
            { t: "⌫", a: "apagar", s: 3 },
            { t: "ABC", a: "modo:texto", s: 3 },
          ]
        ),
      ],
    },

    // Telefone: teclado de telefone mesmo, nao uma fileira de digitos.
    numero: {
      colunas: 3,
      estreito: true,
      linhas: [
        letras("1 2 3"),
        letras("4 5 6"),
        letras("7 8 9"),
        [
          { t: "⌫", a: "apagar", s: 1 },
          { t: "0", s: 1 },
          { t: "PRÓXIMO →", a: "proximo", s: 1 },
        ],
      ],
    },
  };

  // ---------------------------------------------------------------------
  // Estado
  // ---------------------------------------------------------------------

  var campo = null;      // input em foco
  var modo = "texto";
  var maiuscula = true;
  var fecharTimer = null;

  // ---------------------------------------------------------------------
  // Cursor de texto
  // ---------------------------------------------------------------------
  // Os campos são readOnly (bloqueia teclado físico/do Windows) e, com
  // isso, o Chromium não desenha o cursor nativo — mesmo focado e com
  // selectionStart certo. Desenhamos um em cima do campo, medindo o texto
  // com canvas para achar a posição em pixels, igual o navegador faria.

  var cursor = document.createElement("span");
  cursor.className = "campo-cursor";
  cursor.hidden = true;

  var canvasMedida = document.createElement("canvas");
  var ctxMedida = canvasMedida.getContext("2d");

  function medirLargura(el, texto) {
    var estilo = getComputedStyle(el);
    ctxMedida.font = estilo.fontStyle + " " + estilo.fontWeight + " " +
      estilo.fontSize + " " + estilo.fontFamily;
    return ctxMedida.measureText(texto).width;
  }

  /**
   * Em qual índice do texto cai um toque, pelo x em coordenadas de tela.
   *
   * Campo readOnly: o Chromium não reposiciona o cursor pelo clique como
   * faria num campo normal — o toque no meio de "CARLOS" leva o cursor
   * pro FIM do texto, não pro ponto tocado. Sem isso, dava pra digitar
   * mas não dava pra apagar uma letra do meio sem apagar tudo depois
   * dela também. Por isso medimos a posição à mão, igual medimos pra
   * desenhar o cursor.
   */
  function indicePeloToque(el, clienteX) {
    var estilo = getComputedStyle(el);
    var rect = el.getBoundingClientRect();
    // .tela inteira encolhe/cresce por transform: scale (--escala); rect é
    // em pixels de tela (pós-escala), offsetWidth não muda com a escala.
    var fatorEscala = rect.width / el.offsetWidth || 1;
    var base = (parseFloat(estilo.borderLeftWidth) || 0) +
      (parseFloat(estilo.paddingLeft) || 0) - el.scrollLeft;
    var alvo = (clienteX - rect.left) / fatorEscala - base;

    var texto = el.value;
    var melhorIndice = 0;
    var melhorDist = Math.abs(alvo);
    for (var i = 1; i <= texto.length; i++) {
      var dist = Math.abs(medirLargura(el, texto.slice(0, i)) - alvo);
      if (dist <= melhorDist) { melhorDist = dist; melhorIndice = i; }
    }
    return melhorIndice;
  }

  function atualizarCursor() {
    if (!campo) return;
    var estilo = getComputedStyle(campo);
    var pos = campo.selectionStart;
    // type=email não expõe selectionStart no Chromium (fica null); nesse
    // caso o toque no teclado sempre escreve/apaga no fim do texto (ver
    // selecao()), então o cursor também fica no fim.
    if (pos === null || pos === undefined) pos = campo.value.length;

    var esquerda = (parseFloat(estilo.borderLeftWidth) || 0) +
      (parseFloat(estilo.paddingLeft) || 0) +
      medirLargura(campo, campo.value.slice(0, pos)) -
      campo.scrollLeft;
    var altura = parseFloat(estilo.fontSize) * 1.2;

    cursor.style.left = esquerda + "px";
    cursor.style.top = ((campo.clientHeight - altura) / 2) + "px";
    cursor.style.height = altura + "px";
    cursor.hidden = false;

    // Reinicia o piscar a cada movimento — igual o cursor de verdade,
    // que fica aceso um instante toda vez que ele se mexe.
    cursor.style.animation = "none";
    void cursor.offsetWidth;
    cursor.style.animation = "";
  }

  // Cobre tanto o toque nas teclas do jogo (inserir/apagar) quanto o
  // toque direto no campo para reposicionar o cursor no meio do texto —
  // os dois mexem em selectionStart, e selectionchange dispara pros dois.
  document.addEventListener("selectionchange", function () {
    if (campo && document.activeElement === campo) atualizarCursor();
  });

  var caixa = document.createElement("div");
  caixa.className = "teclado";
  caixa.setAttribute("role", "group");
  caixa.setAttribute("aria-label", "Teclado");
  caixa.hidden = true;

  var grade = document.createElement("div");
  grade.className = "teclado-grade";
  caixa.appendChild(grade);
  // Dentro do palco (.tela), na faixa de baixo — como na prancheta 5 do
  // mockup. Assim ele escala junto com o resto da tela.
  (document.querySelector(".tela") || document.body).appendChild(caixa);

  // O toque na tecla NAO pode tirar o foco do campo: sem foco nao ha
  // cursor e o proprio navegador fecharia o teclado.
  caixa.addEventListener("pointerdown", function (ev) {
    ev.preventDefault();
  });

  // ---------------------------------------------------------------------
  // Desenho
  // ---------------------------------------------------------------------

  function desenhar() {
    var layout = LAYOUTS[modo];
    grade.innerHTML = "";
    grade.classList.toggle("estreita", !!layout.estreito);
    grade.style.setProperty("--teclado-colunas", layout.colunas);

    layout.linhas.forEach(function (linha) {
      linha.forEach(function (tecla) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "tecla" + (tecla.a ? " tecla-acao" : "");
        if (tecla.a) b.setAttribute("data-acao", tecla.a);
        b.style.gridColumn = "span " + (tecla.s || (layout.estreito ? 1 : 2));

        var rotulo = tecla.t;
        if (!tecla.a && rotulo.length === 1 && /[A-ZÀ-Ý]/.test(rotulo)) {
          rotulo = maiuscula ? rotulo : rotulo.toLowerCase();
        }
        b.textContent = rotulo;

        if (tecla.a === "maiusc" && maiuscula) b.classList.add("ativa");

        b.addEventListener("click", function () {
          acionar(tecla);
        });
        grade.appendChild(b);
      });
    });

    // Cada layout tem um numero de linhas diferente (texto 5, numero 4,
    // acentos 2), entao trocar de layout muda a altura. Sem remedir aqui,
    // a tela continua encolhida pela altura do layout ANTERIOR e sobra um
    // vao morto entre o formulario e o teclado.
    if (!caixa.hidden) medir();
  }

  // ---------------------------------------------------------------------
  // Acoes
  // ---------------------------------------------------------------------

  function disparar(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /**
   * Posicao do cursor, quando o campo deixa consultar.
   * input[type=email] nao expoe selectionStart no Chromium: devolve null e
   * setSelectionRange levanta erro. Nesse caso a digitacao vai para o fim,
   * que e o comportamento normal de quem digita num totem.
   */
  function selecao(el) {
    try {
      if (el.selectionStart === null || el.selectionStart === undefined) {
        return null;
      }
      return { ini: el.selectionStart, fim: el.selectionEnd };
    } catch (e) {
      return null;
    }
  }

  function posicionar(el, pos) {
    try { el.setSelectionRange(pos, pos); } catch (e) { /* type=email */ }
  }

  function inserir(texto) {
    if (!campo) return;
    var sel = selecao(campo) || { ini: campo.value.length, fim: campo.value.length };
    var novo = campo.value.slice(0, sel.ini) + texto + campo.value.slice(sel.fim);

    var max = parseInt(campo.getAttribute("maxlength") || "0", 10);
    if (max > 0 && novo.length > max) return;

    campo.value = novo;
    posicionar(campo, sel.ini + texto.length);
    disparar(campo);
    ajustarMaiuscula();
    // Chamada direta, não só via selectionchange: em type=email o
    // Chromium nem sempre dispara esse evento (setSelectionRange falha
    // silenciosamente ali, ver posicionar()).
    atualizarCursor();
  }

  function apagar() {
    if (!campo) return;
    var sel = selecao(campo) || { ini: campo.value.length, fim: campo.value.length };
    var ini = sel.ini;
    if (sel.ini === sel.fim) {
      if (ini === 0) return;
      ini = ini - 1;
    }
    campo.value = campo.value.slice(0, ini) + campo.value.slice(sel.fim);
    posicionar(campo, ini);
    disparar(campo);
    ajustarMaiuscula();
    atualizarCursor();
  }

  function proximo() {
    var i = alvos.indexOf(campo);
    if (i > -1 && i < alvos.length - 1) alvos[i + 1].focus();
    else fechar();
  }

  function acionar(tecla) {
    if (!tecla.a) {
      var c = tecla.t;
      if (c.length === 1 && /[A-ZÀ-Ý]/.test(c) && !maiuscula) c = c.toLowerCase();
      inserir(c);
      return;
    }
    if (tecla.a === "apagar") return apagar();
    if (tecla.a === "espaco") return inserir(" ");
    if (tecla.a === "proximo") return proximo();
    if (tecla.a === "maiusc") {
      maiuscula = !maiuscula;
      return desenhar();
    }
    if (tecla.a.indexOf("modo:") === 0) {
      modo = tecla.a.slice(5);
      return desenhar();
    }
  }

  /**
   * Maiuscula automatica no nome: comeco do campo e depois de espaco.
   * E-mail fica sempre minusculo — ninguem tem e-mail com maiuscula e
   * corrigir isso no totem custa toques que a fila nao tem.
   */
  function ajustarMaiuscula() {
    if (!campo) return;
    var antes = maiuscula;
    if (campo.type === "email") {
      maiuscula = false;
    } else if (campo.id === "nome") {
      var v = campo.value;
      maiuscula = v.length === 0 || /\s$/.test(v);
    }
    if (maiuscula !== antes) desenhar();
  }

  // ---------------------------------------------------------------------
  // Abrir / fechar
  // ---------------------------------------------------------------------

  function medir() {
    document.body.style.setProperty(
      "--teclado-h", Math.ceil(caixa.getBoundingClientRect().height) + "px"
    );
  }

  function abrir(el) {
    campo = el;
    modo = el.type === "tel" ? "numero" : "texto";
    maiuscula = el.type !== "email";
    ajustarMaiuscula();
    desenhar();

    // O cursor é um só, reaproveitado: muda de campo junto com o foco.
    el.parentElement.appendChild(cursor);
    atualizarCursor();

    caixa.hidden = false;
    document.body.classList.add("com-teclado");
    medir();

    // Sem scrollIntoView: o palco tem tamanho fixo e os campos ficam acima
    // do teclado; rolar o palco deslocaria a arte do fundo.
    window.requestAnimationFrame(medir);
  }

  function fechar() {
    campo = null;
    cursor.hidden = true;
    caixa.hidden = true;
    document.body.classList.remove("com-teclado");
    document.body.style.removeProperty("--teclado-h");
  }

  alvos.forEach(function (el) {
    // readonly e a barreira efetiva contra o teclado virtual do Windows e
    // contra teclados fisicos. O teclado do jogo continua funcionando porque
    // altera el.value diretamente e dispara o evento input. inputmode=none
    // fica como reforco para navegadores que ainda tentem abrir o painel de
    // entrada ao tocar num campo somente leitura.
    el.readOnly = true;
    el.setAttribute("inputmode", "none");

    // Bloqueia tambem colagem, arrastar texto e eventos de entrada externos.
    // As teclas do jogo nao passam por estes eventos: chamam inserir/apagar.
    el.addEventListener("beforeinput", function (ev) { ev.preventDefault(); });
    el.addEventListener("paste", function (ev) { ev.preventDefault(); });
    el.addEventListener("drop", function (ev) { ev.preventDefault(); });
    el.addEventListener("keydown", function (ev) { ev.preventDefault(); });

    el.addEventListener("focus", function () {
      if (fecharTimer) { clearTimeout(fecharTimer); fecharTimer = null; }
      abrir(el);
    });

    // Toque direto no campo, no meio do texto: reposiciona o cursor no
    // ponto tocado (ver indicePeloToque). O evento "click" chega depois
    // do "focus" mesmo no primeiro toque do campo, então já vale de
    // cara — não só em toques seguintes com o campo já aberto.
    el.addEventListener("click", function (ev) {
      posicionar(el, indicePeloToque(el, ev.clientX));
      atualizarCursor();
    });

    el.addEventListener("blur", function () {
      // Sai e volta ao trocar de campo: so fecha se ninguem mais assumiu.
      fecharTimer = setTimeout(function () {
        if (alvos.indexOf(document.activeElement) === -1) fechar();
      }, 60);
    });
  });

  // Tocar fora dos campos e do teclado encerra a digitacao.
  document.addEventListener("pointerdown", function (ev) {
    if (!campo) return;
    if (caixa.contains(ev.target) || alvos.indexOf(ev.target) > -1) return;
    campo.blur();
  });

  window.addEventListener("resize", function () {
    if (!caixa.hidden) medir();
  });
})();
