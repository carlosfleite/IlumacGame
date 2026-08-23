/**
 * Cadastro do participante — tela 1.
 *
 * Três campos apenas (nome, telefone, e-mail). Num totem de feira a fila
 * anda: cada campo a mais é gente que desiste no meio.
 *
 * A validação roda no cliente para dar retorno imediato, mas o servidor
 * revalida tudo — o navegador é do participante, não nosso.
 */
(function () {
  "use strict";

  var form = document.getElementById("form-cadastro");
  var erroEl = document.getElementById("erro-cadastro");
  var btn = document.getElementById("btn-cadastrar");

  var campos = {
    nome: {
      input: document.getElementById("nome"),
      wrap: document.getElementById("campo-nome"),
      dica: document.getElementById("dica-nome"),
    },
    telefone: {
      input: document.getElementById("telefone"),
      wrap: document.getElementById("campo-telefone"),
      dica: document.getElementById("dica-telefone"),
    },
    email: {
      input: document.getElementById("email"),
      wrap: document.getElementById("campo-email"),
      dica: document.getElementById("dica-email"),
    },
  };

  // -------------------------------------------------------------------
  // Máscara de telefone: (00) 00000-0000
  // -------------------------------------------------------------------

  function soDigitos(valor) {
    return (valor || "").replace(/\D/g, "");
  }

  /**
   * Formata progressivamente, aceitando fixo (10 dígitos) e celular (11).
   * Não completa nada sozinha: só põe os separadores do que já foi digitado,
   * senão o campo "briga" com quem está digitando.
   */
  function mascararTelefone(valor) {
    var d = soDigitos(valor).slice(0, 11);
    if (d.length === 0) return "";
    if (d.length <= 2) return "(" + d;
    if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length <= 10) {
      return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    }
    return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
  }

  campos.telefone.input.addEventListener("input", function () {
    var antes = this.value;
    var noFim = this.selectionStart === antes.length;
    this.value = mascararTelefone(antes);
    // com o cursor no fim (caso normal no touch) ele acompanha sozinho;
    // no meio do texto, devolve para onde estava
    if (!noFim) {
      var pos = this.selectionStart;
      try { this.setSelectionRange(pos, pos); } catch (e) { /* ignora */ }
    }
    limparCampo("telefone");
  });

  // -------------------------------------------------------------------
  // Validações
  // -------------------------------------------------------------------

  /** Exige nome e sobrenome, cada um com 2+ letras. */
  function validarNome(valor) {
    var nome = (valor || "").trim().replace(/\s+/g, " ");
    if (!nome) return "Informe seu nome completo.";
    var partes = nome.split(" ").filter(function (p) {
      return p.length > 0;
    });
    if (partes.length < 2) return "Informe nome e sobrenome.";
    var curtas = partes.filter(function (p) { return p.length < 2; });
    if (curtas.length === partes.length) return "Informe nome e sobrenome.";
    if (!/^[A-Za-zÀ-ÖØ-öø-ÿ' .-]+$/.test(nome)) {
      return "Use apenas letras no nome.";
    }
    return null;
  }

  /** Aceita fixo (10) e celular (11). No celular, exige o 9 inicial. */
  function validarTelefone(valor) {
    var d = soDigitos(valor);
    if (!d) return "Informe seu telefone.";
    if (d.length < 10) return "Telefone incompleto — use DDD + número.";
    var ddd = parseInt(d.slice(0, 2), 10);
    if (ddd < 11 || ddd > 99) return "DDD inválido.";
    if (d.length === 11 && d[2] !== "9") return "Celular deve começar com 9 após o DDD.";
    return null;
  }

  /**
   * Verificação de e-mail sem regex heroica: formato básico, um único @,
   * domínio com ponto e TLD de 2+ letras. Pega o que erra de verdade num
   * totem — digitar sem @, sem domínio ou terminar com ponto.
   */
  function validarEmail(valor) {
    var email = (valor || "").trim();
    if (!email) return "Informe seu e-mail.";
    if (/\s/.test(email)) return "O e-mail não pode conter espaços.";
    if ((email.match(/@/g) || []).length !== 1) return "E-mail deve ter um @.";

    var partes = email.split("@");
    var local = partes[0];
    var dominio = partes[1];

    if (!local) return "Falta o trecho antes do @.";
    if (!dominio) return "Falta o domínio depois do @.";
    if (dominio.indexOf(".") === -1) return "Domínio incompleto (ex.: empresa.com.br).";
    if (/^[.-]|[.-]$/.test(dominio)) return "Domínio inválido.";
    if (dominio.indexOf("..") !== -1) return "Domínio inválido.";
    if (!/^[A-Za-z0-9._%+-]+$/.test(local)) return "E-mail com caractere inválido.";
    if (!/^[A-Za-z0-9.-]+$/.test(dominio)) return "Domínio com caractere inválido.";

    var tld = dominio.split(".").pop();
    if (!/^[A-Za-z]{2,}$/.test(tld)) return "Terminação do e-mail inválida.";
    return null;
  }

  var VALIDADORES = {
    nome: validarNome,
    telefone: validarTelefone,
    email: validarEmail,
  };

  function marcarCampo(nome, mensagem) {
    var c = campos[nome];
    c.wrap.classList.add("invalido");
    c.dica.textContent = mensagem;
    c.dica.hidden = false;
  }

  function limparCampo(nome) {
    var c = campos[nome];
    c.wrap.classList.remove("invalido");
    c.dica.hidden = true;
    c.dica.textContent = "";
  }

  // valida ao sair do campo; limpa o erro assim que a pessoa corrige
  Object.keys(campos).forEach(function (nome) {
    var c = campos[nome];
    c.input.addEventListener("blur", function () {
      var erro = VALIDADORES[nome](c.input.value);
      if (erro) marcarCampo(nome, erro);
      else limparCampo(nome);
    });
    c.input.addEventListener("input", function () {
      if (c.wrap.classList.contains("invalido")) limparCampo(nome);
    });
  });

  function mostrarErro(msg) {
    erroEl.hidden = false;
    erroEl.textContent = msg;
  }

  function limparErro() {
    erroEl.hidden = true;
    erroEl.textContent = "";
  }

  // -------------------------------------------------------------------

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    limparErro();

    var primeiroInvalido = null;
    Object.keys(campos).forEach(function (nome) {
      var erro = VALIDADORES[nome](campos[nome].input.value);
      if (erro) {
        marcarCampo(nome, erro);
        if (!primeiroInvalido) primeiroInvalido = nome;
      } else {
        limparCampo(nome);
      }
    });

    if (primeiroInvalido) {
      mostrarErro("*Confira os campos destacados.");
      campos[primeiroInvalido].input.focus();
      return;
    }

    if (!document.getElementById("consentimento_lgpd").checked) {
      mostrarErro("É necessário marcar o consentimento LGPD para participar.");
      return;
    }

    btn.disabled = true;
    btn.textContent = "Salvando…";

    fetch("/api/cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome: campos.nome.input.value.trim().replace(/\s+/g, " "),
        telefone: campos.telefone.input.value.trim(),
        email: campos.email.input.value.trim(),
        consentimento_lgpd: true,
      }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          throw new Error(data.erro || "Não foi possível cadastrar.");
        }
        sessionStorage.clear();
        sessionStorage.setItem("participante_id", String(data.participante_id));
        window.location.href = "/regras?pid=" + encodeURIComponent(data.participante_id);
      })
      .catch(function (err) {
        mostrarErro(err.message || "Erro de conexão local.");
        btn.disabled = false;
        btn.textContent = "Continuar";
      });
  });
})();
