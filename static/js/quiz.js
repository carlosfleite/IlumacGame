/**
 * Quiz — cronômetro, perguntas, barra de fogo e feedback.
 *
 * O feedback reproduz as pranchetas 8 (acerto) e 9 (erro) do mockup: a
 * tela inteira troca de fundo e mostra a resposta certa.
 */
(function () {
  "use strict";

  // Reserva por inatividade: a tela de feedback é pra ficar travada até
  // a pessoa tocar em "Toque para continuar" — isso só existe pra não
  // prender alguém ali pra sempre se ninguém interagir. Contado só
  // depois que a tela termina de entrar.
  var FEEDBACK_MS = 10000;
  var ENTRADA_MS = 250;   // deve casar com a animação reboque-entra no CSS
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
  var fbDeco = document.getElementById("fb-deco");
  var fbMsg = document.getElementById("feedback-msg");
  var fbPontos = document.getElementById("feedback-pontos");
  var fbRespRotulo = document.getElementById("fb-resposta-rotulo");
  var fbRespTexto = document.getElementById("feedback-detalhe");
  var fbMascote = document.getElementById("fb-mascote");
  var fbContinuar = document.getElementById("feedback-continuar");

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
  // Feedback: a tela de acerto/erro entra por cima da pergunta
  // ---------------------------------------------------------------------

  /**
   * Fim da entrada: só então começa a contagem para avançar sozinho.
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
    if (feedbackTimer) clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(continuarAposFeedback, FEEDBACK_MS);
  }

  reboque.addEventListener("animationend", function (ev) {
    if (ev.animationName === "reboque-entra") aoChegar();
  });

  /**
   * Decoração do fundo como peças soltas (static/js/deco-mockup.js, gerado
   * do .ai): setas no acerto, X no erro. Recriadas a cada feedback para a
   * animação de entrada recomeçar do zero.
   */
  function montarDeco(acertou) {
    var pecas = (window.DECO_MOCKUP || {})[acertou ? "certo" : "errado"] || [];
    fbDeco.innerHTML = "";
    pecas.forEach(function (p, i) {
      var img = document.createElement("img");
      img.src = "/static/img/mockup/" + p.src;
      img.alt = "";
      img.className = acertou ? "deco-seta" : "deco-x";
      img.style.left = p.x + "px";
      img.style.top = p.y + "px";
      img.style.width = p.w + "px";
      img.style.height = p.h + "px";
      img.style.setProperty("--i", String(i));
      fbDeco.appendChild(img);
    });
  }

  // Pré-carrega a arte do feedback: sem isso, no primeiro acerto/erro o
  // fundo e as peças apareciam alguns quadros depois do texto.
  (function preCarregar() {
    var d = window.DECO_MOCKUP || {};
    var arquivos = ["fundo-certo.png", "fundo-errado.png", "selo-pontos-certo.svg",
      "selo-pontos-errado.svg", "moldura-premio.svg", "btn-toque.svg", "mascote.svg",
      "ilumaquinho-triste.png"];
    (d.certo || []).concat(d.errado || []).forEach(function (p) { arquivos.push(p.src); });
    arquivos.forEach(function (a) { new Image().src = "/static/img/mockup/" + a; });
  })();

  function mostrarFeedback(acertou, mensagem, pontos, respostaCerta) {
    overlay.classList.toggle("is-bom", acertou);
    overlay.classList.toggle("is-ruim", !acertou);
    montarDeco(acertou);
    fbMsg.textContent = acertou ? "Resposta certa!" : "Resposta errada!";
    fbPontos.textContent = acertou ? "+" + pontos + " pontos" : "0 pontos";
    fbRespRotulo.textContent = acertou ? "Resposta" : "A certa era";
    fbRespTexto.textContent = respostaCerta || mensagem;
    fbMascote.src = acertou
      ? "/static/img/mockup/mascote.svg"
      : "/static/img/mockup/ilumaquinho-triste.png";

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

  // Só esse botão avança — não o overlay inteiro (ver comentário no CSS
  // de .feedback-tap). Toque não muda o tempo já registrado nem a
  // resposta já gravada: isso já aconteceu antes do feedback aparecer,
  // em responder(); aqui só decide quando a tela sai da frente.
  fbContinuar.addEventListener("click", continuarAposFeedback);

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
