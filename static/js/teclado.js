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
 * Aqui a altura e nossa, entao a tela encolhe junto (body.com-teclado +
 * --teclado-h no CSS) e o botao continua alcancavel.
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
        [{ t: "MAIÚSC", a: "maiusc", s: 3 }].concat(
          letras("Z X C V B N M"),
          [{ t: "APAGAR", a: "apagar", s: 3 }]
        ),
        [
          { t: "ÁÉÍ", a: "modo:acentos", s: 3 },
          { t: "@" },
          { t: "ESPAÇO", a: "espaco", s: 8 },
          { t: "." },
          { t: "PRÓXIMO", a: "proximo", s: 5 },
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
            { t: "APAGAR", a: "apagar", s: 3 },
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
          { t: "APAGAR", a: "apagar", s: 1 },
          { t: "0", s: 1 },
          { t: "PRÓXIMO", a: "proximo", s: 1 },
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

  var caixa = document.createElement("div");
  caixa.className = "teclado";
  caixa.setAttribute("role", "group");
  caixa.setAttribute("aria-label", "Teclado");
  caixa.hidden = true;

  var grade = document.createElement("div");
  grade.className = "teclado-grade";
  caixa.appendChild(grade);
  document.body.appendChild(caixa);

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

    caixa.hidden = false;
    document.body.classList.add("com-teclado");
    medir();

    // depois do reflow, garante que o campo em foco ficou visivel
    window.requestAnimationFrame(function () {
      medir();
      if (campo) campo.scrollIntoView({ block: "center" });
    });
  }

  function fechar() {
    campo = null;
    caixa.hidden = true;
    document.body.classList.remove("com-teclado");
    document.body.style.removeProperty("--teclado-h");
  }

  alvos.forEach(function (el) {
    // Desliga o teclado nativo: com o nosso na tela, os dois juntos
    // brigariam pelo mesmo espaco. Fica no JS e nao no HTML de proposito —
    // se este script nao carregar, o campo volta a aceitar o teclado do
    // sistema em vez de ficar impossivel de preencher.
    el.setAttribute("inputmode", "none");

    el.addEventListener("focus", function () {
      if (fecharTimer) { clearTimeout(fecharTimer); fecharTimer = null; }
      abrir(el);
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
