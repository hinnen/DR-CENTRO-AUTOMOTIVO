/**
 * Reportar bug — botão flutuante global (desktop + /m/).
 * Atalho: Alt+B
 */
(function (global) {
  "use strict";

  var DEVICE_ID_KEY = "dr_device_id_v1";
  var DEVICE_LABEL_KEY = "dr_device_label_v1";
  var ROOT_ID = "dr-bug-report-root";
  var REACH_ID = "dr-bug-reach";
  var BUG_ICON = "\uD83D\uDC1E";
  var HTML2CANVAS_SRC = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
  var Z_FORM = 2147483645;
  var Z_REACH = 2147483637;

  var open = false;
  var sending = false;
  var html2canvasLoading = null;

  function isMobileApp() {
    return document.body && document.body.classList.contains("m-app");
  }

  function csrfToken() {
    try {
      var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
      if (m) return decodeURIComponent(m[1]);
    } catch (e) {}
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function uuid() {
    try {
      if (global.crypto && typeof global.crypto.randomUUID === "function") {
        return global.crypto.randomUUID();
      }
    } catch (e) {}
    return "d-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  function deviceId() {
    try {
      var id = localStorage.getItem(DEVICE_ID_KEY);
      if (id && id.length >= 8) return id;
      id = uuid();
      localStorage.setItem(DEVICE_ID_KEY, id);
      return id;
    } catch (e) {
      return uuid();
    }
  }

  function deviceLabel() {
    try {
      return (localStorage.getItem(DEVICE_LABEL_KEY) || "").trim();
    } catch (e) {
      return "";
    }
  }

  function setDeviceLabel(v) {
    try {
      localStorage.setItem(DEVICE_LABEL_KEY, String(v || "").trim().slice(0, 80));
    } catch (e) {}
  }

  function sugestaoDispositivo() {
    var atual = deviceLabel();
    if (atual) return atual;
    return isMobileApp() ? "Celular vistoria" : "PC recepção";
  }

  function usuarioNomePadrao() {
    try {
      var meta = document.querySelector('meta[name="dr-user-display"]');
      if (meta && meta.content) return String(meta.content).trim();
    } catch (e) {}
    return "";
  }

  function telaStr() {
    try {
      return (
        Math.round(global.screen.width || 0) +
        "x" +
        Math.round(global.screen.height || 0) +
        "@" +
        Math.round(global.devicePixelRatio || 1)
      );
    } catch (e) {
      return "";
    }
  }

  function ensureCss() {
    if (document.getElementById("dr-bug-report-css")) return;
    var st = document.createElement("style");
    st.id = "dr-bug-report-css";
    st.textContent =
      "#" +
      REACH_ID +
      "{position:fixed;right:max(.65rem,env(safe-area-inset-right,0px));bottom:max(.65rem,env(safe-area-inset-bottom,0px));z-index:" +
      Z_REACH +
      ";width:3rem;height:3rem;padding:0;border-radius:999px;border:2px solid #a31b33;background:#152e69;color:#fff;font-size:1.35rem;line-height:1;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 6px 20px rgba(21,46,105,.35);touch-action:manipulation}" +
      "body.m-app #" +
      REACH_ID +
      "{bottom:calc(4.25rem + env(safe-area-inset-bottom,0px))}" +
      "#" +
      REACH_ID +
      ":hover{background:#0f2250;border-color:#c41e3a}" +
      "#" +
      REACH_ID +
      "[hidden]{display:none!important}" +
      ".dr-bug-overlay{position:fixed;inset:0;z-index:" +
      Z_FORM +
      ";display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(11,24,56,.45);backdrop-filter:blur(2px);font-family:system-ui,sans-serif}" +
      ".dr-bug-panel{width:min(100%,26rem);max-height:min(94dvh,560px);overflow:auto;border-radius:12px;border:2px solid rgba(163,27,51,.25);background:#fff;box-shadow:0 24px 60px rgba(11,24,56,.25);padding:1.15rem 1.25rem;color:#14192b}" +
      ".dr-bug-title{margin:0 0 .25rem;font-size:1.15rem;font-weight:800;color:#152e69}" +
      ".dr-bug-lead{margin:0 0 .75rem;font-size:.88rem;color:#5c6675;line-height:1.4}" +
      ".dr-bug-label{display:block;margin:0 0 .25rem;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#152e69}" +
      ".dr-bug-input,.dr-bug-ta{width:100%;box-sizing:border-box;border:1px solid #d8dee6;border-radius:8px;padding:.55rem .7rem;font-size:.95rem;color:#14192b;background:#fff;margin-bottom:.65rem}" +
      ".dr-bug-ta{min-height:4.2rem;resize:vertical}" +
      ".dr-bug-input:focus,.dr-bug-ta:focus{outline:none;border-color:#a31b33;box-shadow:0 0 0 2px rgba(163,27,51,.15)}" +
      ".dr-bug-meta{margin:0 0 .75rem;font-size:.72rem;font-weight:600;color:#87909e;line-height:1.35}" +
      ".dr-bug-actions{display:flex;flex-wrap:wrap;gap:.5rem}" +
      ".dr-bug-btn{flex:1 1 7rem;min-height:2.75rem;border-radius:8px;border:1px solid transparent;font-size:.9rem;font-weight:700;cursor:pointer}" +
      ".dr-bug-btn--muted{background:#fff;border-color:#d8dee6;color:#5c6675}" +
      ".dr-bug-btn--primary{background:#a31b33;color:#fff}" +
      ".dr-bug-btn--primary:disabled{opacity:.5;cursor:not-allowed}" +
      ".dr-bug-ok{margin:0;font-size:1.05rem;font-weight:800;color:#17784a;text-align:center}" +
      ".dr-bug-err{margin:.35rem 0 0;font-size:.82rem;font-weight:700;color:#a31b33}";
    document.head.appendChild(st);
  }

  function ensureReachButton() {
    ensureCss();
    var btn = document.getElementById(REACH_ID);
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button";
      btn.id = REACH_ID;
      btn.title = "Reportar bug (Alt+B)";
      btn.setAttribute("aria-label", "Reportar bug");
      btn.textContent = BUG_ICON;
      document.body.appendChild(btn);
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        openModal();
      });
    }
    if (open) btn.setAttribute("hidden", "");
    else btn.removeAttribute("hidden");
    return btn;
  }

  function wireHotkey() {
    if (global.__drBugHotkey) return;
    global.__drBugHotkey = true;
    document.addEventListener("keydown", function (ev) {
      var altB = ev.altKey && !ev.ctrlKey && !ev.metaKey && String(ev.key || "").toLowerCase() === "b";
      if (!altB) return;
      ev.preventDefault();
      openModal();
    });
  }

  function loadHtml2Canvas() {
    if (global.html2canvas) return Promise.resolve(global.html2canvas);
    if (html2canvasLoading) return html2canvasLoading;
    html2canvasLoading = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = HTML2CANVAS_SRC;
      s.async = true;
      s.onload = function () {
        if (global.html2canvas) resolve(global.html2canvas);
        else reject(new Error("html2canvas"));
      };
      s.onerror = function () {
        reject(new Error("html2canvas"));
      };
      document.head.appendChild(s);
    });
    return html2canvasLoading;
  }

  function maskSensitive() {
    var nodes = document.querySelectorAll(
      'input[type="password"], input[name*="pin"], input[id*="pin"], input[name*="senha"]'
    );
    var saved = [];
    for (var i = 0; i < nodes.length; i++) {
      saved.push({ el: nodes[i], value: nodes[i].value });
      try {
        nodes[i].value = nodes[i].value ? "••••••" : "";
      } catch (e) {}
    }
    return function restore() {
      for (var j = 0; j < saved.length; j++) {
        try {
          saved[j].el.value = saved[j].value;
        } catch (e2) {}
      }
    };
  }

  function capturePrint() {
    var restore = maskSensitive();
    var overlay = document.getElementById(ROOT_ID);
    var fab = document.getElementById(REACH_ID);
    if (fab) fab.style.visibility = "hidden";
    if (overlay) overlay.style.visibility = "hidden";
    return loadHtml2Canvas()
      .then(function (h2c) {
        return h2c(document.body, {
          useCORS: true,
          allowTaint: true,
          logging: false,
          scale: Math.min(1, 1280 / Math.max(document.documentElement.clientWidth || 1280, 1)),
        });
      })
      .then(function (canvas) {
        var maxW = 1280;
        var out = canvas;
        if (canvas.width > maxW) {
          var ratio = maxW / canvas.width;
          var c2 = document.createElement("canvas");
          c2.width = maxW;
          c2.height = Math.round(canvas.height * ratio);
          c2.getContext("2d").drawImage(canvas, 0, 0, c2.width, c2.height);
          out = c2;
        }
        return out.toDataURL("image/jpeg", 0.55);
      })
      .catch(function () {
        return "";
      })
      .finally(function () {
        restore();
        if (fab) fab.style.visibility = "";
        if (overlay) overlay.style.visibility = "";
      });
  }

  function closeModal() {
    var root = document.getElementById(ROOT_ID);
    if (root) root.remove();
    open = false;
    ensureReachButton();
  }

  function showOk(id) {
    var root = document.getElementById(ROOT_ID);
    if (!root) return;
    root.innerHTML =
      '<div class="dr-bug-panel" role="dialog" aria-modal="true">' +
      '<p class="dr-bug-ok">Recebido — #' +
      id +
      "</p>" +
      '<div class="dr-bug-actions" style="margin-top:1rem"><button type="button" class="dr-bug-btn dr-bug-btn--primary" id="dr-bug-ok-close">OK</button></div>' +
      "</div>";
    document.getElementById("dr-bug-ok-close").onclick = closeModal;
    setTimeout(closeModal, 2200);
  }

  function setErr(msg) {
    var el = document.getElementById("dr-bug-err");
    if (!el) return;
    if (!msg) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = msg;
  }

  function openModal() {
    if (open) return;
    ensureCss();
    open = true;
    ensureReachButton();
    var root = document.createElement("div");
    root.id = ROOT_ID;
    root.className = "dr-bug-overlay";
    root.innerHTML =
      '<div class="dr-bug-panel" role="dialog" aria-modal="true" aria-labelledby="dr-bug-title">' +
      '<h2 class="dr-bug-title" id="dr-bug-title">Reportar bug</h2>' +
      '<p class="dr-bug-lead">Conte o que aconteceu. Um print da tela vai junto automaticamente.</p>' +
      '<label class="dr-bug-label" for="dr-bug-aconteceu">O que aconteceu?</label>' +
      '<textarea class="dr-bug-ta" id="dr-bug-aconteceu" maxlength="4000" placeholder="Ex.: Cliquei em salvar e nada aconteceu"></textarea>' +
      '<label class="dr-bug-label" for="dr-bug-esperava">O que esperava?</label>' +
      '<textarea class="dr-bug-ta" id="dr-bug-esperava" maxlength="2000" placeholder="Ex.: Devia abrir a vistoria"></textarea>' +
      '<label class="dr-bug-label" for="dr-bug-usuario">Seu nome</label>' +
      '<input class="dr-bug-input" id="dr-bug-usuario" maxlength="120" autocomplete="name" />' +
      '<label class="dr-bug-label" for="dr-bug-pc">Este aparelho</label>' +
      '<input class="dr-bug-input" id="dr-bug-pc" maxlength="80" placeholder="Ex.: PC recepção / Celular pátio" />' +
      '<p class="dr-bug-meta" id="dr-bug-meta"></p>' +
      '<div class="dr-bug-actions">' +
      '<button type="button" class="dr-bug-btn dr-bug-btn--muted" id="dr-bug-cancel">Cancelar</button>' +
      '<button type="button" class="dr-bug-btn dr-bug-btn--primary" id="dr-bug-send">Enviar</button>' +
      "</div>" +
      '<p class="dr-bug-err" id="dr-bug-err" hidden></p>' +
      "</div>";
    document.body.appendChild(root);
    document.getElementById("dr-bug-usuario").value = usuarioNomePadrao();
    document.getElementById("dr-bug-pc").value = sugestaoDispositivo();
    document.getElementById("dr-bug-meta").textContent =
      (isMobileApp() ? "App vistoria" : "Sistema PC") +
      " · id " +
      deviceId().slice(0, 8) +
      " · Alt+B";
    document.getElementById("dr-bug-cancel").onclick = closeModal;
    document.getElementById("dr-bug-send").onclick = submitReport;
    setTimeout(function () {
      document.getElementById("dr-bug-aconteceu").focus();
    }, 50);
  }

  function submitReport() {
    if (sending) return;
    var aconteceu = (document.getElementById("dr-bug-aconteceu").value || "").trim();
    if (aconteceu.length < 3) {
      setErr("Escreva o que aconteceu.");
      return;
    }
    var esperava = (document.getElementById("dr-bug-esperava").value || "").trim();
    var usuario = (document.getElementById("dr-bug-usuario").value || "").trim();
    var pcNome = (document.getElementById("dr-bug-pc").value || "").trim();
    if (pcNome) setDeviceLabel(pcNome);
    var btn = document.getElementById("dr-bug-send");
    sending = true;
    btn.disabled = true;
    btn.textContent = "Enviando…";
    setErr("");
    capturePrint()
      .then(function (printData) {
        return fetch("/api/bug-report/", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
          body: JSON.stringify({
            o_que_aconteceu: aconteceu,
            o_que_esperava: esperava,
            usuario_nome: usuario,
            device_id: deviceId(),
            dispositivo_nome: pcNome || sugestaoDispositivo(),
            app_context: isMobileApp() ? "mobile" : "desktop",
            url_pagina: String(location.href || "").slice(0, 500),
            user_agent: String(navigator.userAgent || "").slice(0, 400),
            tela: telaStr(),
            print_base64: printData || "",
          }),
        });
      })
      .then(function (r) {
        return r.text().then(function (t) {
          var j = null;
          try {
            j = JSON.parse(t);
          } catch (e) {
            j = null;
          }
          if (!j) {
            var login =
              r.status === 401 ||
              r.status === 403 ||
              /entrar|login|sessão/i.test(String(t || "").slice(0, 800));
            return {
              j: {
                ok: false,
                erro: login
                  ? "Sessão expirada — entre de novo e tente outra vez."
                  : "Resposta inválida (" + r.status + ").",
              },
            };
          }
          return { j: j };
        });
      })
      .then(function (pack) {
        sending = false;
        if (!pack.j || !pack.j.ok) {
          btn.disabled = false;
          btn.textContent = "Enviar";
          setErr((pack.j && pack.j.erro) || "Não deu para enviar.");
          return;
        }
        showOk(pack.j.id);
      })
      .catch(function () {
        sending = false;
        btn.disabled = false;
        btn.textContent = "Enviar";
        setErr("Falha de rede. Verifique a internet.");
      });
  }

  function boot() {
    try {
      deviceId();
      wireHotkey();
      ensureReachButton();
      global.DrBugReport = { open: openModal, close: closeModal };
    } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window);
