/**
 * Painel admin — filtro de busca client-side sobre a tabela já renderizada.
 * Sem chamada ao servidor: a lista de participantes de uma feira cabe
 * inteira numa página só, então filtrar no próprio navegador é instantâneo
 * e não precisa de paginação nem endpoint novo.
 */
(function () {
  "use strict";

  // Marca o formato de exportação escolhido — fica vermelho com um pulso.
  // O clique dispara um download, não recarrega a página, então a classe
  // persiste como pista visual de qual botão foi acionado por último.
  var exportar = document.querySelector(".admin-exportar");
  if (exportar) {
    var botoes = Array.prototype.slice.call(
      exportar.querySelectorAll(".admin-btn")
    );
    botoes.forEach(function (botao) {
      botao.addEventListener("click", function () {
        botoes.forEach(function (outro) {
          outro.classList.remove("is-selecionado");
        });
        void botao.offsetWidth; // reinicia a animação se reclicar o mesmo
        botao.classList.add("is-selecionado");
      });
    });
  }

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
