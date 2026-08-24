/**
 * Ranking — pontuação DESC, desempate por tempo ASC (mesmo grupo de pontos).
 *
 * Duas abas: "Hoje" (só as tentativas do dia corrente, no fuso do totem)
 * e "3 dias" (acumulado da feira inteira). Mesma lógica de desempate nos
 * dois casos — só muda o recorte de tentativas que entra no cálculo.
 */
(function () {
  var lista = document.getElementById("ranking-lista");
  var btnReiniciar = document.getElementById("btn-reiniciar");
  var tabDia = document.getElementById("tab-dia");
  var tabGeral = document.getElementById("tab-geral");

  var escopoAtual = "dia";
  var pedidoEmAndamento = 0;

  function fmtMs(ms) {
    var s = Math.floor((ms || 0) / 1000);
    var m = Math.floor(s / 60);
    s = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
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
          lista.innerHTML =
            escopo === "dia"
              ? '<li class="ranking-vazio">Nenhuma partida hoje ainda. Seja o primeiro!</li>'
              : '<li class="ranking-vazio">Nenhuma partida ainda. Seja o primeiro!</li>';
          return;
        }

        lista.innerHTML = rows
          .map(function (r) {
            var topClass = r.posicao === 1 ? " top-1" : "";
            return (
              '<li class="ranking-item' + topClass + '">' +
                '<span class="ranking-pos">' + r.posicao + "º</span>" +
                "<div>" +
                  '<p class="ranking-nome">' + escapeHtml(r.nome) + "</p>" +
                "</div>" +
                '<div class="ranking-stats">' +
                  '<p class="ranking-pts">' + r.pontuacao + " pts</p>" +
                  '<p class="ranking-tempo">' + fmtMs(r.tempo_total_ms) + "</p>" +
                "</div>" +
              "</li>"
            );
          })
          .join("");
      })
      .catch(function (err) {
        if (meuPedido !== pedidoEmAndamento) return;
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
