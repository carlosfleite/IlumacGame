/**
 * Ranking — pontuação DESC, desempate por tempo ASC (mesmo grupo de pontos).
 *
 * Duas abas: "Ranking do dia" (só as tentativas do dia corrente, no fuso
 * do totem) e "Ranking geral (3 dias)" (acumulado da feira inteira). Mesma lógica de desempate nos
 * dois casos — só muda o recorte de tentativas que entra no cálculo.
 */
(function () {
  var lista = document.getElementById("ranking-lista");
  var podio = document.getElementById("ranking-podio");
  var btnReiniciar = document.getElementById("btn-reiniciar");
  var tabDia = document.getElementById("tab-dia");
  var tabGeral = document.getElementById("tab-geral");

  var escopoAtual = "dia";
  var pedidoEmAndamento = 0;

  // 0:55, como no mockup
  function fmtMs(ms) {
    var s = Math.floor((ms || 0) / 1000);
    var m = Math.floor(s / 60);
    s = s % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  // Primeiro e último nome: o mockup mostra apelidos curtos, e um nome
  // completo na barra ficaria ilegível de tão reduzido.
  function nomeCurto(nome) {
    var partes = String(nome || "").trim().split(/\s+/);
    return partes.length > 2 ? partes[0] + " " + partes[partes.length - 1] : partes.join(" ");
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Quantas linhas cabem no palco, como nas pranchetas 2 e 3 do mockup:
  // no dia, 8 linhas (a 9ª da prancheta daria lugar ao botão de voltar);
  // no geral, o pódio e mais 4 linhas.
  var LINHAS_DIA = 8;
  var LINHAS_GERAL = 4;

  var IMG = "/static/img/mockup/";

  // Troféu no 1º; medalha prata, bronze e a rosada do 4º em diante, com o
  // número por cima (no .ai o número também é texto sobre a medalha).
  function icone(posicao, classe) {
    if (posicao === 1) {
      return '<span class="' + classe + ' trofeu"><img src="' + IMG + 'trofeu.svg" alt="1º lugar"></span>';
    }
    var arte = posicao === 2 ? "medalha-2" : posicao === 3 ? "medalha-3" : "medalha-n";
    return (
      '<span class="' + classe + " " + arte + '">' +
        '<img src="' + IMG + arte + '.svg" alt="">' +
        '<span class="px medalha-num">' + posicao + "</span>" +
      "</span>"
    );
  }

  function pontos(n) {
    return n + "<sup>pts</sup>";
  }

  // Pódio: 1º, 2º e 3º viram três cards, o do 1º maior e no centro.
  function renderPodio(topRows) {
    podio.innerHTML = topRows
      .map(function (r) {
        return (
          '<div class="podio-posto posto-' + r.posicao + '">' +
            icone(r.posicao, "podio-icone") +
            '<p class="px podio-nome">' + escapeHtml(nomeCurto(r.nome)) + "</p>" +
            '<p class="px podio-pts">' + pontos(r.pontuacao) + "</p>" +
            '<p class="px podio-tempo">' + fmtMs(r.tempo_total_ms) + "</p>" +
          "</div>"
        );
      })
      .join("");
    Array.prototype.forEach.call(podio.querySelectorAll(".podio-nome"), function (el) {
      window.caberNaLinha(el);
    });
  }

  function renderLista(rows) {
    lista.innerHTML = rows
      .map(function (r) {
        return (
          '<li class="ranking-item" value="' + r.posicao + '">' +
            '<span class="rk-barra"></span>' +
            icone(r.posicao, "rk-medalha") +
            '<p class="px rk-nome">' + escapeHtml(nomeCurto(r.nome)) + "</p>" +
            '<p class="px rk-pts">' + pontos(r.pontuacao) + "</p>" +
          "</li>"
        );
      })
      .join("");
    Array.prototype.forEach.call(lista.querySelectorAll(".rk-nome"), function (el) {
      window.caberNaLinha(el);
    });
  }

  btnReiniciar.addEventListener("click", function () {
    sessionStorage.removeItem("participante_id");
    sessionStorage.removeItem("ultimo_resultado");
  });

  function carregarRanking(escopo) {
    escopoAtual = escopo;
    tabDia.classList.toggle("is-ativa", escopo === "dia");
    tabDia.setAttribute("aria-selected", escopo === "dia" ? "true" : "false");
    tabGeral.classList.toggle("is-ativa", escopo === "geral");
    tabGeral.setAttribute("aria-selected", escopo === "geral" ? "true" : "false");

    podio.innerHTML = "";
    podio.hidden = escopo === "dia";
    lista.classList.toggle("lista-geral", escopo === "geral");
    lista.innerHTML = '<li class="ranking-vazio">Carregando…</li>';

    // Descarta resposta de um pedido antigo se o usuário trocar de aba
    // rápido antes dela voltar — senão a lista errada pode "vencer" a
    // corrida e ficar na tela até o próximo clique.
    var meuPedido = ++pedidoEmAndamento;

    fetch("/api/ranking?limite=20&escopo=" + encodeURIComponent(escopo))
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (meuPedido !== pedidoEmAndamento) return;
        if (!data.ok) {
          throw new Error(data.erro || "Falha ao carregar ranking.");
        }
        var rows = data.ranking || [];
        if (rows.length === 0) {
          podio.innerHTML = "";
          lista.innerHTML =
            escopo === "dia"
              ? '<li class="ranking-vazio">Nenhuma partida hoje ainda.<br>Seja o primeiro!</li>'
              : '<li class="ranking-vazio">Nenhuma partida ainda.<br>Seja o primeiro!</li>';
          return;
        }

        if (escopo === "dia") {
          renderLista(rows.slice(0, LINHAS_DIA));
        } else {
          renderPodio(rows.slice(0, 3));
          renderLista(rows.slice(3, 3 + LINHAS_GERAL));
        }
      })
      .catch(function (err) {
        if (meuPedido !== pedidoEmAndamento) return;
        podio.innerHTML = "";
        lista.innerHTML =
          '<li class="ranking-vazio">' + escapeHtml(err.message) + "</li>";
      });
  }

  tabDia.addEventListener("click", function () {
    if (escopoAtual !== "dia") carregarRanking("dia");
  });
  tabGeral.addEventListener("click", function () {
    if (escopoAtual !== "geral") carregarRanking("geral");
  });

  carregarRanking("dia");
})();
