/**
 * Quiz — cronômetro, perguntas, barra de fogo e feedback do Llumaquinho.
 *
 * SPRITES: gerados por tools/gerar_pixel_assets.py em /static/img/
 *   ilumaquinho/andando.png  → folha de 2 quadros (entrada puxando o card)
 *   ilumaquinho/deu-bom.png  → acertou
 *   ilumaquinho/deu-ruim.png → errou
 */
(function () {
  "use strict";

  var FEEDBACK_MS = 2200; // contado só depois que o card termina de entrar
  var ENTRADA_MS = 800;   // deve casar com a duração de reboque-entra no CSS

  var params = new URLSearchParams(window.location.search);
  var participanteId = parseInt(
    params.get("pid") || sessionStorage.getItem("participante_id"), 10);

  if (!participanteId) {
    window.location.replace("/");
    return;
  }
  sessionStorage.setItem("participante_id", String(participanteId));

  var elProgresso = document.getElementById("quiz-progresso");
  var elPontos = document.getElementById("quiz-pontos");
  var elPergunta = document.getElementById("quiz-pergunta");
  var elAlts = document.getElementById("quiz-alternativas");
  var elTimer = document.getElementById("quiz-timer");
  var elTrilho = document.getElementById("barra-trilho");
  var elChama = document.getElementById("chama");

  var elPlacar = document.getElementById("barra-placar");

  var overlay = document.getElementById("feedback-overlay");
  var reboque = document.getElementById("fb-reboque");
  var fbCard = document.getElementById("fb-card");
  var fbFaixa = document.getElementById("fb-faixa");
  var fbMascote = document.getElementById("fb-mascote");
  var fbMsg = document.getElementById("feedback-msg");
  var fbPontos = document.getElementById("feedback-pontos");

  var perguntas = [];
  var indice = 0;
  var pontuacao = 0;
  var acertos = 0;
  var pontosPorAcerto = 2;

  var timerId = null;
  var perguntaInicio = 0;
  // Soma do tempo das perguntas já respondidas. O cronômetro mostra
  // acumulado + pergunta atual, e congela durante o feedback — assim o
  // número na tela é exatamente o tempo que o servidor usa no desempate.
  var tempoAcumuladoMs = 0;

  var respondendo = false;
  var feedbackTimer = null;
  var entradaTimer = null;
  var chegou = false;
  var avancarFn = null;

  function fmtMs(ms) {
    var s = Math.floor(ms / 1000);
    var m = Math.floor(s / 60);
    s = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function pintarTimer() {
    elTimer.textContent = fmtMs(tempoAcumuladoMs + (Date.now() - perguntaInicio));
  }

  function pararTimer() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function iniciarTimer() {
    pararTimer();
    perguntaInicio = Date.now();
    pintarTimer();
    timerId = setInterval(pintarTimer, 250);
  }

  // ---------------------------------------------------------------------
  // Barra de fogo
  // ---------------------------------------------------------------------

  function montarBarra(total) {
    elTrilho.innerHTML = "";
    for (var i = 0; i < total; i++) {
      var b = document.createElement("span");
      b.className = "barra-bloco";
      elTrilho.appendChild(b);
    }
    elChama.setAttribute("data-nivel", "0");
    atualizarPlacar(total);
  }

  function atualizarPlacar(total) {
    if (elPlacar) {
      elPlacar.textContent = pontuacao + " / " + (total * pontosPorAcerto);
    }
  }

  function marcarBloco(i, acertou) {
    var blocos = elTrilho.querySelectorAll(".barra-bloco");
    if (blocos[i]) {
      blocos[i].classList.add(acertou ? "aceso" : "apagado");
    }
    // a chama cresce com os acertos, não com o número de perguntas
    elChama.setAttribute("data-nivel", String(acertos));
    atualizarPlacar(perguntas.length);
  }

  // ---------------------------------------------------------------------
  // Perguntas
  // ---------------------------------------------------------------------

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderPergunta() {
    var p = perguntas[indice];
    elProgresso.textContent = "Pergunta " + (indice + 1) + " / " + perguntas.length;
    elPontos.textContent = pontuacao + " pts";
    elPergunta.textContent = p.texto;
    elAlts.innerHTML = "";

    ["a", "b", "c", "d"].forEach(function (letra) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "alt-btn";
      btn.dataset.resposta = letra;
      btn.innerHTML =
        '<span class="alt-letra">' + letra.toUpperCase() + "</span>" +
        '<span class="alt-texto">' + escapeHtml(p["alt_" + letra]) + "</span>";
      btn.addEventListener("click", function () {
        responder(letra);
      });
      elAlts.appendChild(btn);
    });

    respondendo = false;
    iniciarTimer();
  }

  function desabilitarAlts() {
    var buttons = elAlts.querySelectorAll(".alt-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
    }
  }

  // ---------------------------------------------------------------------
  // Feedback: o mascote entra puxando o card
  // ---------------------------------------------------------------------

  /**
   * Fim da entrada: o mascote para de andar e assume a expressão, e só
   * então começa a contagem para avançar sozinho.
   *
   * Chamado por dois caminhos de propósito. O navegador congela animações
   * quando a página fica oculta (visibilityState "hidden") — se a janela
   * do totem for encoberta ou a máquina bloquear a tela no meio de uma
   * partida, o animationend nunca dispara e o participante ficaria preso
   * no card de feedback. O temporizador de reserva garante a saída.
   * Idempotente: vale quem chegar primeiro.
   */
  function aoChegar() {
    if (chegou) return;
    chegou = true;
    if (entradaTimer) {
      clearTimeout(entradaTimer);
      entradaTimer = null;
    }
    fbMascote.classList.add("parado");
    if (feedbackTimer) clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(continuarAposFeedback, FEEDBACK_MS);
  }

  reboque.addEventListener("animationend", function (ev) {
    if (ev.animationName === "reboque-entra") aoChegar();
  });

  function mostrarFeedback(acertou, mensagem, pontos) {
    var classe = acertou ? "is-bom" : "is-ruim";

    fbCard.className = "fb-card " + classe;
    fbFaixa.textContent = acertou ? "Resposta certa" : "Resposta errada";
    fbMsg.textContent = mensagem;
    fbPontos.textContent = acertou ? "+" + pontos + " pontos" : "0 pontos";

    // volta o mascote para o ciclo de caminhada antes de entrar de novo
    fbMascote.className = "fb-mascote " + classe;

    chegou = false;
    overlay.hidden = false;
    overlay.classList.remove("is-visible");
    void overlay.offsetWidth; // reflow: reinicia a animação de entrada
    overlay.classList.add("is-visible");

    // reserva, caso o animationend não venha (ver aoChegar)
    if (entradaTimer) clearTimeout(entradaTimer);
    entradaTimer = setTimeout(aoChegar, ENTRADA_MS + 300);
  }

  function esconderFeedback() {
    overlay.classList.remove("is-visible");
    overlay.hidden = true;
  }

  function continuarAposFeedback() {
    if (feedbackTimer) {
      clearTimeout(feedbackTimer);
      feedbackTimer = null;
    }
    if (entradaTimer) {
      clearTimeout(entradaTimer);
      entradaTimer = null;
    }
    esconderFeedback();
    if (typeof avancarFn === "function") {
      var fn = avancarFn;
      avancarFn = null;
      fn();
    }
  }

  overlay.addEventListener("click", continuarAposFeedback);

  // ---------------------------------------------------------------------

  function responder(letra) {
    if (respondendo) return;
    respondendo = true;
    desabilitarAlts();
    pararTimer();

    var tempoMs = Date.now() - perguntaInicio;
    var pergunta = perguntas[indice];
    var indiceAtual = indice;

    fetch("/api/quiz/responder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        participante_id: participanteId,
        pergunta_id: pergunta.id,
        resposta_dada: letra,
        tempo_resposta_ms: tempoMs,
      }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          throw new Error(data.erro || "Erro ao registrar resposta.");
        }

        // o tempo desta pergunta entra no acumulado; o relógio fica parado
        // enquanto o feedback está na tela
        tempoAcumuladoMs += tempoMs;
        elTimer.textContent = fmtMs(tempoAcumuladoMs);

        var pontos = data.pontos || pontosPorAcerto;
        if (data.acertou) {
          acertos += 1;
          pontuacao += pontos;
          elPontos.textContent = pontuacao + " pts";
        }
        marcarBloco(indiceAtual, data.acertou);
        mostrarFeedback(data.acertou, data.mensagem, pontos);

        avancarFn = function () {
          indice += 1;
          if (indice >= perguntas.length) {
            finalizar();
          } else {
            renderPergunta();
          }
        };
      })
      .catch(function (err) {
        respondendo = false;
        elPergunta.textContent = err.message || "Erro local ao responder.";
        var buttons = elAlts.querySelectorAll(".alt-btn");
        for (var i = 0; i < buttons.length; i++) buttons[i].disabled = false;
        iniciarTimer();
      });
  }

  function finalizar() {
    pararTimer();
    fetch("/api/quiz/finalizar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        participante_id: participanteId,
        pontuacao: pontuacao,
        tempo_total_ms: tempoAcumuladoMs, // servidor recalcula mesmo assim
      }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          throw new Error(data.erro || "Erro ao finalizar.");
        }
        sessionStorage.setItem("ultimo_resultado", JSON.stringify(data));
        window.location.href = "/resultado";
      })
      .catch(function (err) {
        elPergunta.textContent = err.message || "Erro ao finalizar o quiz.";
      });
  }

  // Boot
  elPergunta.textContent = "Sorteando perguntas…";
  fetch("/api/quiz/iniciar?participante_id=" + encodeURIComponent(participanteId))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (!data.ok) {
        throw new Error(data.erro || "Não foi possível iniciar o quiz.");
      }
      perguntas = data.perguntas || [];
      pontosPorAcerto = data.pontos_por_acerto || 2;
      if (perguntas.length === 0) {
        throw new Error("Nenhuma pergunta retornada.");
      }
      montarBarra(perguntas.length);
      renderPergunta();
    })
    .catch(function (err) {
      elPergunta.textContent = err.message || "Erro ao carregar o quiz.";
    });
})();
