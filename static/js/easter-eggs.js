/**
 * Easter eggs visuais do Quiz SDAI.
 * Não alteram perguntas, pontuação, prêmios nem dados do participante.
 */
(function () {
  "use strict";

  function criarAviso(texto, classe) {
    var tela = document.querySelector(".tela");
    if (!tela) return null;
    var aviso = document.createElement("div");
    aviso.className = "px egg-aviso " + (classe || "");
    aviso.textContent = texto;
    tela.appendChild(aviso);
    requestAnimationFrame(function () { aviso.classList.add("is-visible"); });
    // 2600ms era curto: no totem real, com barulho e gente em volta, muita
    // gente batia o olho e o aviso já tinha sumido. 3400ms dá tempo de ler.
    setTimeout(function () {
      aviso.classList.remove("is-visible");
      setTimeout(function () { aviso.remove(); }, 350);
    }, 3400);
    return aviso;
  }

  function prepararAbertura() {
    var mascote = document.querySelector(".ab-mascote");
    var tela = document.querySelector(".tela--abertura");
    if (!mascote || !tela) return;

    // 2. Cinco toques no Ilumaquinho revelam uma Ilumacoin, uma vez por
    // sessão. O brasão continua reservado exclusivamente para a saída.
    var toques = 0;
    var ultimoToque = 0;
    mascote.classList.add("egg-clicavel");
    mascote.addEventListener("click", function (ev) {
      ev.preventDefault();
      var agora = Date.now();
      if (agora - ultimoToque > 2200) toques = 0;
      ultimoToque = agora;
      toques += 1;
      mascote.classList.remove("egg-pulinho");
      void mascote.offsetWidth;
      mascote.classList.add("egg-pulinho");

      if (toques < 5 || sessionStorage.getItem("egg_ilumaquinho_abertura")) return;
      toques = 0;
      sessionStorage.setItem("egg_ilumaquinho_abertura", "1");
      mascote.classList.add("egg-comemorando");

      var moeda = document.createElement("img");
      moeda.className = "egg-moeda-abertura";
      moeda.src = "/static/img/ILUMACOIN.png";
      moeda.alt = "Ilumacoin encontrada";
      tela.appendChild(moeda);
      // O aviso tem z-index maior que a moeda e cai bem em cima dela: se
      // aparecesse junto, cobria a moeda antes de ela terminar de "surgir".
      // Meio segundo de atraso deixa a moeda ser vista primeiro.
      setTimeout(function () {
        criarAviso("Você encontrou o Ilumaquinho secreto!", "egg-aviso-abertura");
      }, 500);
      setTimeout(function () { moeda.remove(); }, 3800);
      setTimeout(function () { mascote.classList.remove("egg-comemorando"); }, 3800);
    });

    // 8. Depois de um minuto sem interação, o Ilumaquinho cochila. O
    // primeiro toque em qualquer ponto o acorda e continua sua ação normal.
    var timerSono = null;
    var dormindo = false;
    var zzz = document.createElement("span");
    zzz.className = "px egg-zzz";
    zzz.textContent = "Zzz";
    zzz.hidden = true;
    tela.appendChild(zzz);

    function dormir() {
      dormindo = true;
      mascote.classList.add("egg-dormindo");
      zzz.hidden = false;
    }

    function reiniciarSono() {
      clearTimeout(timerSono);
      if (dormindo) {
        dormindo = false;
        mascote.classList.remove("egg-dormindo");
        mascote.classList.add("egg-acordando");
        zzz.hidden = true;
        setTimeout(function () { mascote.classList.remove("egg-acordando"); }, 650);
      }
      timerSono = setTimeout(dormir, 60000);
    }

    ["pointerdown", "keydown"].forEach(function (evento) {
      document.addEventListener(evento, reiniciarSono, true);
    });
    reiniciarSono();
  }

  function prepararCadastro() {
    var mascote = document.querySelector(".cad-mascote");
    var convite = document.querySelector(".balao-convite");
    var erro = document.getElementById("erro-cadastro");
    if (!mascote || !convite) return;

    // 5. Quatro toques fazem o Ilumaquinho responder como um técnico SDAI.
    var frases = [
      "Laço verificado!",
      "Central comunicando!",
      "Dispositivo endereçado!",
      "Sistema normal!",
      "Sinal recebido com sucesso!"
    ];
    var original = convite.innerHTML;
    var toques = 0;
    var ultimoToque = 0;
    var restaurar = null;
    mascote.classList.add("egg-clicavel");
    mascote.addEventListener("click", function (ev) {
      ev.preventDefault();
      var agora = Date.now();
      if (agora - ultimoToque > 2200) toques = 0;
      ultimoToque = agora;
      mascote.classList.remove("egg-pulinho");
      void mascote.offsetWidth;
      mascote.classList.add("egg-pulinho");

      // Com o erro de validação na tela, o toque só faz o mascote pular;
      // não soma para a piada. Sem isso, toques dados enquanto o erro
      // estava visível ficavam guardados e a piada disparava de surpresa
      // assim que a pessoa corrigisse o campo.
      if (erro && !erro.hidden) { toques = 0; return; }

      toques += 1;
      if (toques < 4) return;

      toques = 0;
      clearTimeout(restaurar);
      convite.innerHTML = "<b>Ilumaquinho técnico</b>" +
        frases[Math.floor(Math.random() * frases.length)];
      convite.classList.add("egg-fala-tecnica");
      restaurar = setTimeout(function () {
        convite.innerHTML = original;
        convite.classList.remove("egg-fala-tecnica");
      }, 3000);
    });
  }

  function prepararRanking() {
    var tela = document.querySelector(".tela--ranking");
    if (!tela) return;

    // Quem já achou a moeda leva um selinho de Ilumacoin junto da tag
    // "Você" na própria linha do ranking. A lista é redesenhada do zero a
    // cada troca de aba (dia/geral), então reaplicamos o selo sempre que
    // ela mudar — não só no instante em que a moeda foi pega.
    var lista = document.getElementById("ranking-lista");
    function marcarVoceComMoeda() {
      if (!sessionStorage.getItem("egg_ilumacoin_ranking")) return;
      var tag = document.querySelector(".rk-voce");
      if (tag) tag.classList.add("egg-achou-moeda");
    }
    if (lista && window.MutationObserver) {
      new MutationObserver(marcarVoceComMoeda).observe(lista, { childList: true });
    }
    marcarVoceComMoeda();

    if (sessionStorage.getItem("egg_ilumacoin_ranking")) return;

    // 6. Aparição rara: aproximadamente uma em cada quatro visitas ao
    // ranking. Se não for capturada, pode reaparecer em uma visita futura.
    if (Math.random() > 0.25) return;
    setTimeout(function () {
      if (!document.body.contains(tela)) return;
      var moeda = document.createElement("button");
      moeda.type = "button";
      moeda.className = "egg-moeda-ranking";
      moeda.setAttribute("aria-label", "Ilumacoin rara");
      moeda.innerHTML = '<img src="/static/img/ILUMACOIN.png" alt="">';
      tela.appendChild(moeda);

      moeda.addEventListener("click", function () {
        sessionStorage.setItem("egg_ilumacoin_ranking", "1");
        moeda.classList.add("is-encontrada");
        marcarVoceComMoeda();
        // Mesmo motivo do easter egg da abertura: o aviso cai bem em cima
        // da moeda (mesmo "top"), então esperamos a animação de "pegar"
        // (0.45s) aparecer antes de cobrir a área com o aviso.
        setTimeout(function () {
          criarAviso("Ilumacoin encontrada!", "egg-aviso-ranking");
        }, 300);
        setTimeout(function () { moeda.remove(); }, 500);
      });
      moeda.addEventListener("animationend", function () { moeda.remove(); });
    }, 1400);
  }

  if (document.body.classList.contains("page-abertura")) prepararAbertura();
  if (document.body.classList.contains("page-cadastro")) prepararCadastro();
  if (document.body.classList.contains("page-ranking")) prepararRanking();
})();
