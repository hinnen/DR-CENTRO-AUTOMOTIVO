/* Comportamentos base do layout: toasts e atalhos. */

(function () {
  "use strict";

  // ---------- Toasts ----------

  function dismissToast(toast) {
    toast.classList.add("is-leaving");
    setTimeout(() => toast.remove(), 220);
  }

  function scheduleDismiss(toast) {
    setTimeout(() => {
      if (toast.isConnected) dismissToast(toast);
    }, 6000);
  }

  document.querySelectorAll("[data-toast]").forEach(scheduleDismiss);

  document.addEventListener("click", (event) => {
    const closeBtn = event.target.closest("[data-dismiss-toast]");
    if (!closeBtn) return;
    const toast = closeBtn.closest("[data-toast]");
    if (toast) dismissToast(toast);
  });

  // Avisos criados pelo JavaScript (Kanban) usam o mesmo visual das mensagens
  // vindas do Django, para o usuário não perceber diferença.
  document.addEventListener("app:toast", (event) => {
    const container = document.getElementById("toasts");
    if (!container) return;

    const level = event.detail.level === "error" ? "error" : "success";
    const toast = document.createElement("div");
    toast.className = "toast toast--" + level;
    toast.setAttribute("data-toast", "");
    toast.innerHTML =
      '<span class="toast__text"></span>' +
      '<button class="toast__close" type="button" aria-label="Fechar aviso" data-dismiss-toast>×</button>';
    toast.querySelector(".toast__text").textContent = event.detail.message;

    container.appendChild(toast);
    scheduleDismiss(toast);
  });

  // ---------- Abas ----------

  // As seções da OS chegam do servidor todas visíveis. Só depois que este
  // código roda é que passam a ser abas — assim a página continua legível
  // se o script falhar, e o Ctrl+F do navegador ainda encontra tudo antes.
  function initTabs(nav) {
    const buttons = Array.from(nav.querySelectorAll("[data-tab-target]"));
    const panels = buttons
      .map((btn) => document.getElementById(btn.dataset.tabTarget))
      .filter(Boolean);

    if (panels.length !== buttons.length) return;

    nav.setAttribute("role", "tablist");
    document.documentElement.setAttribute("data-tabs-ready", "");

    function select(id, updateHash) {
      buttons.forEach((btn) => {
        const active = btn.dataset.tabTarget === id;
        btn.setAttribute("aria-selected", String(active));
        btn.setAttribute("role", "tab");
        btn.setAttribute("tabindex", active ? "0" : "-1");
      });
      panels.forEach((panel) => {
        panel.hidden = panel.id !== id;
      });
      if (updateHash) {
        history.replaceState(null, "", "#" + id);
      }
    }

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => select(btn.dataset.tabTarget, true));
    });

    // Setas navegam entre abas, como esperado em um tablist.
    nav.addEventListener("keydown", (event) => {
      const index = buttons.indexOf(document.activeElement);
      if (index === -1) return;
      let next = null;
      if (event.key === "ArrowRight") next = (index + 1) % buttons.length;
      if (event.key === "ArrowLeft") next = (index - 1 + buttons.length) % buttons.length;
      if (next === null) return;
      event.preventDefault();
      buttons[next].focus();
      select(buttons[next].dataset.tabTarget, true);
    });

    // Um link para #fotos deve abrir a aba que contém aquela âncora, e não
    // apenas rolar para uma seção escondida.
    function selectFromHash() {
      const hash = location.hash.replace("#", "");
      if (!hash) return select(buttons[0].dataset.tabTarget, false);

      const direct = buttons.find((btn) => btn.dataset.tabTarget === hash);
      if (direct) return select(hash, false);

      const target = document.getElementById(hash);
      const owner = target && target.closest(".tab-panel");
      select(owner ? owner.id : buttons[0].dataset.tabTarget, false);
      if (target && owner) target.scrollIntoView({ block: "start" });
    }

    selectFromHash();
    window.addEventListener("hashchange", selectFromHash);
  }

  document.querySelectorAll("[data-tabs]").forEach(initTabs);

  // ---------- Atalhos de teclado ----------

  function isTyping(target) {
    if (!target) return false;
    const tag = target.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      return;
    }

    // Ctrl+K / Cmd+K vale mesmo com o cursor dentro de um campo: é o atalho
    // que todo mundo já usa para "procurar alguma coisa aqui dentro".
    if ((event.ctrlKey || event.metaKey) && (event.key === "k" || event.key === "K")) {
      const search = document.getElementById("busca-global");
      if (search) {
        event.preventDefault();
        search.focus();
        search.select();
      }
      return;
    }

    if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;

    if (event.key === "/") {
      const search = document.getElementById("busca-global");
      if (search && !search.disabled) {
        event.preventDefault();
        search.focus();
      }
      return;
    }

    if (event.key === "n" || event.key === "N") {
      const newEntry = document.querySelector("[data-shortcut-new-entry]");
      if (newEntry) {
        event.preventDefault();
        newEntry.click();
      }
    }
  });

  // ---------- WhatsApp (atalho wa.me no header) ----------

  function initWhatsAppPicker() {
    const root = document.querySelector("[data-wa-picker]");
    if (!root || root.dataset.waReady === "1") return;
    root.dataset.waReady = "1";

    const toggle = root.querySelector("[data-wa-toggle]");
    const panel = root.querySelector("[data-wa-panel]");
    const results = root.querySelector("[data-wa-results]");
    const search = root.querySelector("[data-wa-search]");
    const focusInput = root.querySelector("[data-wa-focus-input]");
    if (!toggle || !panel || !results) return;

    const url = search && search.getAttribute("hx-get");

    function close() {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      root.classList.remove("is-open");
    }

    function open() {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      root.classList.add("is-open");
      if (search) {
        search.focus();
        if (window.htmx && url) {
          const focus = focusInput ? focusInput.value : "";
          const qs = new URLSearchParams();
          if (search.value) qs.set("q", search.value);
          if (focus) qs.set("focus", focus);
          window.htmx.ajax("GET", url + (qs.toString() ? "?" + qs.toString() : ""), {
            target: "#wa-picker-results",
            swap: "innerHTML",
          });
        }
      }
    }

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (panel.hidden) open();
      else close();
    });

    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) close();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) {
        close();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWhatsAppPicker);
  } else {
    initWhatsAppPicker();
  }

  // ---------- Select + cadastrar (mecânico / localização) ----------

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".creatable-select__panel:not(:empty)").forEach((panel) => {
      panel.innerHTML = "";
    });
  });

  document.body.addEventListener("htmx:afterSwap", (event) => {
    const panel = event.target.closest?.(".creatable-select__panel");
    if (!panel) return;
    const focusable = panel.querySelector("input:not([type=hidden]), select, textarea, button");
    if (focusable) focusable.focus();
  });
})();
