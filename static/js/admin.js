/**
 * Painel admin — filtro de busca client-side sobre a tabela já renderizada.
 * Sem chamada ao servidor: a lista de participantes de uma feira cabe
 * inteira numa página só, então filtrar no próprio navegador é instantâneo
 * e não precisa de paginação nem endpoint novo.
 */
(function () {
  "use strict";

  var busca = document.getElementById("busca");
  var corpo = document.getElementById("corpo-tabela");
  if (!busca || !corpo) return;

  var linhas = Array.prototype.slice.call(corpo.querySelectorAll("tr"));

  busca.addEventListener("input", function () {
    var termo = busca.value.trim().toLowerCase();
    linhas.forEach(function (linha) {
      var texto = linha.textContent.toLowerCase();
      linha.style.display = !termo || texto.indexOf(termo) !== -1 ? "" : "none";
    });
  });
})();
