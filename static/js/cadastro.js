/**
 * Cadastro do participante — tela 1
 */
(function () {
  var form = document.getElementById("form-cadastro");
  var erroEl = document.getElementById("erro-cadastro");
  var btn = document.getElementById("btn-cadastrar");

  function mostrarErro(msg) {
    erroEl.hidden = false;
    erroEl.textContent = msg;
  }

  function limparErro() {
    erroEl.hidden = true;
    erroEl.textContent = "";
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    limparErro();

    var nome = (document.getElementById("nome").value || "").trim();
    var consent = document.getElementById("consentimento_lgpd").checked;

    if (!nome) {
      mostrarErro("Informe seu nome para continuar.");
      document.getElementById("nome").focus();
      return;
    }
    if (!consent) {
      mostrarErro("É necessário marcar o consentimento LGPD.");
      return;
    }

    btn.disabled = true;
    btn.textContent = "Salvando…";

    fetch("/api/cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome: nome,
        empresa: (document.getElementById("empresa").value || "").trim(),
        email: (document.getElementById("email").value || "").trim(),
        telefone: (document.getElementById("telefone").value || "").trim(),
        cargo: (document.getElementById("cargo").value || "").trim(),
        consentimento_lgpd: consent,
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.data.ok) {
          throw new Error(result.data.erro || "Não foi possível cadastrar.");
        }
        sessionStorage.clear();
        sessionStorage.setItem("participante_id", String(result.data.participante_id));
        window.location.href = "/regras?pid=" + encodeURIComponent(result.data.participante_id);
      })
      .catch(function (err) {
        mostrarErro(err.message || "Erro de conexão local.");
        btn.disabled = false;
        btn.textContent = "Continuar";
      });
  });
})();
