/**
 * Quiz — timer, perguntas, feedback do Ilumaquinho, finalização.
 *
 * SPRITES: troque os arquivos em /static/img/ilumaquinho/
 *   deu-bom.png  → sprite "acertou"  (Ilumaquinho comemorando)
 *   deu-ruim.png → sprite "errou"    (Ilumaquinho triste)
 * Gerados a partir dos PNG de marca em img/, redimensionados para 280px
 * de altura (2x do tamanho exibido) para não pesar no totem.
 */
(function () {
  var FEEDBACK_MS = 2500; // 2–3 s; toque pula antes

  var params = new URLSearchParams(window.location.search);
  var participanteId = parseInt(params.get("pid") || sessionStorage.getItem("participante_id"), 10);

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
  var overlay = document.getElementById("feedback-overlay");
  var feedbackCard = document.getElementById("feedback-card");
  var feedbackImg = document.getElementById("feedback-img");
  var feedbackMsg = document.getElementById("feedback-msg");

  var perguntas = [];
  var indice = 0;
  var pontuacao = 0;
  var pontosPorAcerto = 2;
  var timerId = null;
  var perguntaInicio = 0;
  var respondendo = false;
  var feedbackTimer = null;
  var avancarFn = null;

  function fmtMs(ms) {
    var s = Math.floor(ms / 1000);
    var m = Math.floor(s / 60);
    s = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
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
    elTimer.textContent = "00:00";
    timerId = setInterval(function () {
      elTimer.textContent = fmtMs(Date.now() - perguntaInicio);
    }, 200);
  }

  // Loop track — um nó por pergunta; acende conforme avança.
  function montarLoopTrack(total) {
    var track = document.getElementById("loop-track");
    if (!track) return;
    var antigos = track.querySelectorAll(".node");
    for (var i = 0; i < antigos.length; i++) antigos[i].remove();
    for (var n = 0; n < total; n++) {
      var no = document.createElement("div");
      no.className = "node";
      no.dataset.idx = String(n);
      no.textContent = String(n + 1);
      track.appendChild(no);
    }
  }

  function atualizarLoopTrack() {
    var nos = document.querySelectorAll("#loop-track .node");
    for (var i = 0; i < nos.length; i++) {
      nos[i].classList.remove("done", "current");
      if (i < indice) nos[i].classList.add("done");
      else if (i === indice) nos[i].classList.add("current");
    }
    var fill = document.getElementById("loop-fill");
    if (fill && perguntas.length) {
      fill.style.width = (indice / perguntas.length * 100) + "%";
    }
  }

  function renderPergunta() {
    var p = perguntas[indice];
    atualizarLoopTrack();
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

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function desabilitarAlts() {
    var buttons = elAlts.querySelectorAll(".alt-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
    }
  }

  function mostrarFeedback(acertou, mensagem) {
    feedbackCard.classList.remove("is-bom", "is-ruim");
    feedbackCard.classList.add(acertou ? "is-bom" : "is-ruim");
    // PLACEHOLDER: troque os SVGs pelos sprites oficiais do Ilumaquinho
    feedbackImg.src = acertou
      ? "/static/img/ilumaquinho/deu-bom.png"
      : "/static/img/ilumaquinho/deu-ruim.png";
    feedbackImg.alt = acertou ? "Ilumaquinho — deu bom" : "Ilumaquinho — deu ruim";
    feedbackMsg.textContent = mensagem;

    overlay.hidden = false;
    // força reflow para animar
    void overlay.offsetWidth;
    overlay.classList.add("is-visible");
  }

  function esconderFeedback() {
    overlay.classList.remove("is-visible");
    setTimeout(function () {
      overlay.hidden = true;
    }, 250);
  }

  function continuarAposFeedback() {
    if (feedbackTimer) {
      clearTimeout(feedbackTimer);
      feedbackTimer = null;
    }
    esconderFeedback();
    if (typeof avancarFn === "function") {
      var fn = avancarFn;
      avancarFn = null;
      fn();
    }
  }

  overlay.addEventListener("click", continuarAposFeedback);

  function responder(letra) {
    if (respondendo) return;
    respondendo = true;
    desabilitarAlts();
    pararTimer();

    var tempoMs = Date.now() - perguntaInicio;
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
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.data.ok) {
          throw new Error(result.data.erro || "Erro ao registrar resposta.");
        }
        if (result.data.acertou) {
          pontuacao += result.data.pontos || pontosPorAcerto;
          elPontos.textContent = pontuacao + " pts";
        }
        mostrarFeedback(result.data.acertou, result.data.mensagem);

        avancarFn = function () {
          indice += 1;
          if (indice >= perguntas.length) {
            finalizar();
          } else {
            renderPergunta();
          }
        };

        feedbackTimer = setTimeout(continuarAposFeedback, FEEDBACK_MS);
      })
      .catch(function (err) {
        respondendo = false;
        alert(err.message || "Erro local ao responder.");
        // reabilita para tentar de novo
        var buttons = elAlts.querySelectorAll(".alt-btn");
        for (var i = 0; i < buttons.length; i++) {
          buttons[i].disabled = false;
        }
        iniciarTimer();
      });
  }

  function finalizar() {
    fetch("/api/quiz/finalizar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        participante_id: participanteId,
        pontuacao: pontuacao,
        tempo_total_ms: 0, // servidor recalcula a partir das respostas
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.data.ok) {
          throw new Error(result.data.erro || "Erro ao finalizar.");
        }
        sessionStorage.setItem("ultimo_resultado", JSON.stringify(result.data));
        window.location.href = "/resultado";
      })
      .catch(function (err) {
        alert(err.message || "Erro ao finalizar o quiz.");
      });
  }

  // Boot
  elPergunta.textContent = "Sorteando perguntas…";
  fetch("/api/quiz/iniciar?participante_id=" + encodeURIComponent(participanteId))
    .then(function (res) {
      return res.json().then(function (data) {
        return { status: res.status, data: data };
      });
    })
    .then(function (result) {
      if (!result.data.ok) {
        throw new Error(result.data.erro || "Não foi possível iniciar o quiz.");
      }
      perguntas = result.data.perguntas || [];
      pontosPorAcerto = result.data.pontos_por_acerto || 2;
      if (perguntas.length === 0) {
        throw new Error("Nenhuma pergunta retornada.");
      }
      montarLoopTrack(perguntas.length);
      renderPergunta();
    })
    .catch(function (err) {
      elPergunta.textContent = err.message || "Erro ao carregar o quiz.";
    });
})();
