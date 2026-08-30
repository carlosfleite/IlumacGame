/**
 * Quiz — cronômetro, perguntas, barra de fogo e feedback do Llumaquinho.
 *
 * SPRITES: gerados por tools/gerar_pixel_assets.py em /static/img/
 *   ilumaquinho/andando.png  → 2 direcoes, nao 2 passos (ver style.css)
 *   ilumaquinho/deu-bom.png  → acertou
 *   ilumaquinho/deu-ruim.png → errou
 */
(function () {
  "use strict";

  var FEEDBACK_MS = 2600; // contado só depois que a tela termina de entrar
  var ENTRADA_MS = 1000;  // deve casar com --fb-entrada / reboque-entra no CSS
  var LIMITE_MS = 20000;  // tempo por pergunta; zerou, conta como erro

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
  var elAcertos = document.getElementById("quiz-acertos");
  var elChama = document.getElementById("chama");

  var elBarra = document.getElementById("barra-progresso");
  var elPrazo = document.getElementById("barra-prazo");

  var overlay = document.getElementById("feedback-overlay");
  var reboque = document.getElementById("fb-reboque");
  var fbCard = document.getElementById("fb-card");
  var fbTopoTxt = document.getElementById("fb-topo-txt");
  var fbMascote = document.getElementById("fb-mascote");
  var fbMsg = document.getElementById("feedback-msg");
  var fbPontos = document.getElementById("feedback-pontos");
  var fbRespRotulo = document.getElementById("fb-resposta-rotulo");
  var fbRespTexto = document.getElementById("feedback-detalhe");

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

  function fmtRelogio(ms) {
    var s = Math.ceil(ms / 1000);
    var m = Math.floor(s / 60);
    s = s % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function pintarAcertos() {
    var total = perguntas.length || 5;
    if (elAcertos) elAcertos.textContent = acertos + " / " + total;
  }

  // Cronômetro da pergunta: a barra da base drena com os segundos e, ao
  // zerar, a pergunta é enviada sem resposta (conta como erro).
  function tickPergunta() {
    var restante = LIMITE_MS - (Date.now() - perguntaInicio);
    if (restante < 0) restante = 0;
    var frac = restante / LIMITE_MS;
    if (elBarra) {
      elBarra.style.width = (frac * 100) + "%";
      elBarra.classList.toggle("is-alerta", frac <= 0.4 && frac > 0.15);
      elBarra.classList.toggle("is-critico", frac <= 0.15);
    }
    if (elPrazo) elPrazo.textContent = fmtRelogio(restante);
    if (restante <= 0) esgotouTempo();
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
    if (elBarra) {
      elBarra.classList.remove("is-alerta", "is-critico");
      elBarra.style.width = "100%";
    }
    if (elPrazo) elPrazo.textContent = fmtRelogio(LIMITE_MS);
    timerId = setInterval(tickPergunta, 100);
  }

  function esgotouTempo() {
    if (respondendo) return;
    pararTimer();
    responder(""); // sem resposta — o servidor marca como erro
  }

  // ---------------------------------------------------------------------
  // Barra de fogo
  // ---------------------------------------------------------------------

  function montarBarra() {
    if (elChama) elChama.setAttribute("data-nivel", "0");
    if (elBarra) elBarra.style.width = "100%";
    pintarAcertos();
  }

  function registrarResultado() {
    // a chama cresce com os acertos, não com o número de perguntas
    if (elChama) elChama.setAttribute("data-nivel", String(acertos));
    pintarAcertos();
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

  var VOLTAR_MS = 4000; // tempo pra ler a mensagem antes de voltar sozinho

  /**
   * Erro sem como continuar dali (sessão perdida num restart do watchdog,
   * banco fora do ar, etc.): mostra o motivo e volta pra abertura sozinho.
   * Sem isto, um erro de rede deixava o participante preso na tela do
   * quiz, com os botões desabilitados, até alguém da equipe perceber.
   */
  function voltarAoInicio(mensagem) {
    pararTimer();
    sessionStorage.removeItem("participante_id");
    elPergunta.textContent = mensagem;
    elAlts.innerHTML = "";
    setTimeout(function () {
      window.location.replace("/");
    }, VOLTAR_MS);
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

  function mostrarFeedback(acertou, mensagem, pontos, respostaCerta) {
    var classe = acertou ? "is-bom" : "is-ruim";

    fbCard.className = "fb-painel " + classe;
    overlay.classList.toggle("is-bom", acertou);
    overlay.classList.toggle("is-ruim", !acertou);
    fbTopoTxt.textContent = acertou ? "Resposta certa" : "Resposta errada";
    fbMsg.textContent = acertou ? "Ih, deu bom!" : "Ih, deu ruim!";
    fbPontos.textContent = acertou ? "+" + pontos + " pontos" : "0 pontos";
    fbRespRotulo.textContent = acertou ? "Resposta" : "A certa era";
    fbRespTexto.textContent = respostaCerta || mensagem;

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

    var tempoMs = Math.min(Date.now() - perguntaInicio, LIMITE_MS);
    var pergunta = perguntas[indice];

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

        // o tempo desta pergunta entra no acumulado usado no desempate
        tempoAcumuladoMs += tempoMs;

        var pontos = data.pontos || pontosPorAcerto;
        if (data.acertou) {
          acertos += 1;
          pontuacao += pontos;
          elPontos.textContent = pontuacao + " pts";
        }
        registrarResultado();

        var respostaCerta = "";
        if (data.correta && pergunta["alt_" + data.correta]) {
          respostaCerta = pergunta["alt_" + data.correta];
        }
        mostrarFeedback(data.acertou, data.mensagem, pontos, respostaCerta);

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
        voltarAoInicio(err.message || "Erro ao registrar resposta.");
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
        voltarAoInicio(err.message || "Erro ao finalizar o quiz.");
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
      montarBarra();
      renderPergunta();
    })
    .catch(function (err) {
      voltarAoInicio(err.message || "Erro ao carregar o quiz.");
    });
})();
