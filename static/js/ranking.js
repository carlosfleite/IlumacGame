/**
 * Ranking — pontuação DESC, desempate por tempo ASC (mesmo grupo de pontos).
 */
(function () {
  var lista = document.getElementById("ranking-lista");
  var btnReiniciar = document.getElementById("btn-reiniciar");

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

  fetch("/api/ranking?limite=20")
    .then(function (res) {
      return res.json();
    })
    .then(function (data) {
      if (!data.ok) {
        throw new Error(data.erro || "Falha ao carregar ranking.");
      }
      var rows = data.ranking || [];
      if (rows.length === 0) {
        lista.innerHTML = '<li class="ranking-vazio">Nenhuma partida ainda. Seja o primeiro!</li>';
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
      lista.innerHTML =
        '<li class="ranking-vazio">' + escapeHtml(err.message) + "</li>";
    });
})();
