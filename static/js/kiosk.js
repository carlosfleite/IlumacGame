/**
 * kiosk.js — comportamento de totem, carregado em TODAS as telas.
 *
 * Resolve dois problemas de operação desassistida na feira:
 *
 * 1. Abandono no meio do fluxo. Sem isto, um participante que desiste na
 *    tela de cadastro deixa o totem travado ali até alguém da equipe
 *    perceber. Após N segundos sem interação a tela avisa e volta sozinha
 *    para a abertura, limpando os dados da sessão anterior.
 *
 * 2. Saída acidental do app. Existe teclado/mouse wireless no estande;
 *    F5, F11, F12, Ctrl+R e o menu de contexto são bloqueados. Alt+F4 e
 *    Alt+Tab são do sistema operacional e não dá para interceptar aqui —
 *    quem cobre esse caso é o watchdog do INICIAR_QUIZ.bat.
 *
 * Tempo de inatividade por tela: atributo data-kiosk-timeout no <body>,
 * em segundos. 0 ou ausente desliga o reset (usado na tela de abertura,
 * que já é o estado de repouso).
 *
 * QUEM TRAVA É O TOTEM, NÃO O NAVEGADOR. O run.py abre a janela do
 * pywebview em ?kiosk=1; esse parâmetro liga o travamento e fica gravado
 * no localStorage daquela instalação. Um navegador aberto na mão nunca
 * recebe o parâmetro, então já nasce destravado — é assim que se testa
 * responsividade no F12 sem precisar lembrar de nenhum truque.
 *
 * O localStorage do pywebview é separado do localStorage do Chrome (perfis
 * diferentes, e o run.py ainda usa 127.0.0.1 enquanto no navegador se
 * digita localhost, que é outra origem), então marcar o totem não
 * contamina a máquina de desenvolvimento.
 *
 * Escotilhas manuais, para o caso de precisar mexer no proprio totem:
 *   ?dev=1   destrava temporariamente (mostra um selo amarelo no canto)
 *   ?dev=0   volta a travar
 *   ?kiosk=0 desmarca a instalação como totem
 */
(function () {
  "use strict";

  var AVISO_S = 10; // segundos de contagem regressiva antes de resetar
  var URL_REPOUSO = "/";
  var CHAVE_TOTEM = "kiosk-totem";
  var CHAVE_DEV = "kiosk-dev";

  // ---------------------------------------------------------------------
  // Travado ou não
  // ---------------------------------------------------------------------

  var params = new URLSearchParams(window.location.search);

  /**
   * Lê uma chave que pode ser ligada/desligada por parâmetro na URL e fica
   * gravada depois disso. Precisa ficar gravada porque a navegação interna
   * do app (e o reset para URL_REPOUSO) não carrega parâmetro nenhum.
   */
  function bandeira(chave, param) {
    try {
      if (params.has(param)) {
        if (params.get(param) === "0") {
          localStorage.removeItem(chave);
        } else {
          localStorage.setItem(chave, "1");
        }
      }
      return localStorage.getItem(chave) === "1";
    } catch (e) {
      // storage indisponível: vale só o que veio na URL desta carga
      return params.get(param) === "1";
    }
  }

  var ehTotem = bandeira(CHAVE_TOTEM, "kiosk");
  var modoDev = bandeira(CHAVE_DEV, "dev");
  var travado = ehTotem && !modoDev;

  // Selo visível só quando um totem de verdade foi destravado na mão: sem
  // ele, quem ligou o modo dev e esqueceu deixaria o totem aberto na feira
  // sem nenhum sinal na tela. No navegador comum não aparece — ali estar
  // destravado é o normal, e um selo permanente seria só estorvo.
  function marcarModoDev() {
    var selo = document.createElement("button");
    selo.type = "button";
    selo.textContent = "MODO DEV — destravado (?dev=0 sai)";
    selo.title = "Clique para ocultar o selo nesta tela";
    selo.setAttribute("style", [
      "position:fixed", "z-index:9999", "left:0", "bottom:0",
      "margin:0", "padding:4px 10px", "border:0",
      "font:600 11px/1.4 monospace", "letter-spacing:.08em",
      "color:#1c1517", "background:#ffd21e", "cursor:pointer",
      "border-top-right-radius:2px"
    ].join(";"));
    // O selo pousa em cima da barra de fogo no quiz. Some no clique para
    // nao atrapalhar a inspecao, e volta no proximo carregamento — o aviso
    // de que o totem esta destravado nao se perde.
    selo.addEventListener("click", function () {
      selo.remove();
    });
    document.body.appendChild(selo);
  }

  // ---------------------------------------------------------------------
  // Bloqueio de saída acidental
  // ---------------------------------------------------------------------

  if (ehTotem && modoDev) {
    marcarModoDev();
  }

  document.addEventListener("contextmenu", function (ev) {
    if (!travado) return;
    ev.preventDefault();
  });

  document.addEventListener("dragstart", function (ev) {
    ev.preventDefault();
  });

  function ehCampoDeTexto(el) {
    if (!el) return false;
    var tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
  }

  document.addEventListener(
    "keydown",
    function (ev) {
      if (!travado) return;
      var k = ev.key;

      // Backspace fora de campo de texto navega para trás em alguns motores
      if (k === "Backspace" && !ehCampoDeTexto(ev.target)) {
        ev.preventDefault();
        return;
      }

      // Teclas de função: recarregar, tela cheia, devtools
      if (/^F([1-9]|1[0-2])$/.test(k)) {
        ev.preventDefault();
        return;
      }

      // Navegação pelo histórico
      if (ev.altKey && (k === "ArrowLeft" || k === "ArrowRight")) {
        ev.preventDefault();
        return;
      }

      if (ev.ctrlKey || ev.metaKey) {
        var letra = String(k).toLowerCase();
        // Devtools
        if (ev.shiftKey && (letra === "i" || letra === "j" || letra === "c")) {
          ev.preventDefault();
          return;
        }
        // Recarregar, fechar, nova aba/janela, imprimir, salvar, buscar
        if ("rwntpsfu".indexOf(letra) !== -1 && letra.length === 1) {
          ev.preventDefault();
        }
      }
    },
    true
  );

  // ---------------------------------------------------------------------
  // Reset por inatividade
  // ---------------------------------------------------------------------

  // Fora do totem o reset por inatividade também sai: inspecionar elemento
  // leva mais que o timeout, e a tela voltando para a abertura no meio da
  // conferência é o mesmo estorvo que o bloqueio de tecla.
  if (!travado) return;

  var timeoutS = parseInt(document.body.getAttribute("data-kiosk-timeout"), 10);
  if (!timeoutS || timeoutS <= 0) return;

  var ocioso = null; // timer até começar o aviso
  var regressiva = null; // interval da contagem regressiva
  var overlay = null;
  var elSegundos = null;

  function montarOverlay() {
    overlay = document.createElement("div");
    overlay.className = "kiosk-inatividade";
    overlay.setAttribute("hidden", "");
    overlay.innerHTML =
      '<div class="kiosk-inatividade-card">' +
      "<p class=\"kiosk-inatividade-titulo\">Ainda está aí?</p>" +
      '<p class="kiosk-inatividade-texto">' +
      "Sem resposta, o quiz volta para o início em " +
      '<strong class="kiosk-inatividade-contador">' +
      AVISO_S +
      "</strong>s." +
      "</p>" +
      '<button type="button" class="btn btn-primary kiosk-inatividade-btn">' +
      "Continuar jogando" +
      "</button>" +
      "</div>";
    document.body.appendChild(overlay);
    elSegundos = overlay.querySelector(".kiosk-inatividade-contador");
    // Interagir com o aviso (botão ou qualquer ponto) cancela o reset
    overlay.addEventListener("click", reiniciarContagem);
  }

  function resetar() {
    try {
      sessionStorage.clear();
    } catch (e) {
      /* sessionStorage indisponível: segue para o repouso mesmo assim */
    }
    window.location.replace(URL_REPOUSO);
  }

  function esconderAviso() {
    if (regressiva) {
      clearInterval(regressiva);
      regressiva = null;
    }
    if (overlay) overlay.setAttribute("hidden", "");
  }

  function mostrarAviso() {
    var restante = AVISO_S;
    elSegundos.textContent = String(restante);
    overlay.removeAttribute("hidden");

    regressiva = setInterval(function () {
      restante -= 1;
      if (restante <= 0) {
        esconderAviso();
        resetar();
        return;
      }
      elSegundos.textContent = String(restante);
    }, 1000);
  }

  function reiniciarContagem() {
    // Enquanto o aviso está na tela, só um toque explícito nele reinicia —
    // tratado pelo listener do próprio overlay, que chama esta função.
    esconderAviso();
    if (ocioso) clearTimeout(ocioso);
    ocioso = setTimeout(mostrarAviso, timeoutS * 1000);
  }

  function aoInteragir() {
    // Se o aviso já está visível, ignora movimento acidental: exige o toque
    // no overlay. Evita que o cursor esbarrando cancele o reset.
    if (regressiva) return;
    reiniciarContagem();
  }

  montarOverlay();
  reiniciarContagem();

  ["pointerdown", "keydown", "touchstart", "input"].forEach(function (evt) {
    document.addEventListener(evt, aoInteragir, { passive: true });
  });
})();
