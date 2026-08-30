/* Arrastar-e-soltar do Kanban.
 *
 * O navegador nunca decide o status: ele pede a mudança e o backend valida.
 * Se a resposta não for ok, o card volta para a coluna de origem — assim duas
 * pessoas mexendo ao mesmo tempo não geram estado divergente na tela.
 */

(function () {
  "use strict";

  let isDragging = false;
  let isMoving = false;

  const STORAGE_DEFAULT = "kanban-cards-collapsed";
  const STORAGE_OVERRIDES = "kanban-card-overrides";
  const DESKTOP_MIN = 1024;

  function csrfToken() {
    const match = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
    if (match) return match[2];
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function toast(message, level) {
    document.dispatchEvent(
      new CustomEvent("app:toast", { detail: { message: message, level: level || "success" } })
    );
  }

  function isDesktop() {
    return window.matchMedia("(min-width: " + DESKTOP_MIN + "px)").matches;
  }

  function updateColumnCounts() {
    let total = 0;
    document.querySelectorAll(".kanban__column").forEach((column) => {
      const cards = column.querySelectorAll(".card-os").length;
      total += cards;
      const counter = column.querySelector(".kanban__count");
      if (counter) counter.textContent = String(cards);

      const tabCount = document.querySelector(
        '[data-board-tab="' + column.dataset.columnSlug + '"] .board-tabs__count'
      );
      if (tabCount) tabCount.textContent = String(cards);

      const empty = column.querySelector(".kanban__empty");
      if (cards > 0 && empty) empty.remove();
      if (cards === 0 && !empty) {
        const placeholder = document.createElement("p");
        placeholder.className = "kanban__empty";
        placeholder.textContent = "Nenhum veículo";
        column.querySelector(".kanban__cards").appendChild(placeholder);
      }
    });

    const allTab = document.querySelector('[data-board-tab="all"] .board-tabs__count');
    if (allTab) allTab.textContent = String(total);
  }

  async function moveCard(card, newStatus, revert) {
    isMoving = true;
    const body = new FormData();
    body.append("status", newStatus);

    try {
      const response = await fetch(card.dataset.moveUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
        body: body,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        revert();
        toast(data.error || "Não foi possível mover o veículo.", "error");
        return;
      }

      card.dataset.orderStatus = data.status;
      toast(data.message);
    } catch (error) {
      revert();
      toast("Sem conexão com o servidor. O card voltou para a posição anterior.", "error");
    } finally {
      isMoving = false;
      updateColumnCounts();
    }
  }

  function initBoard() {
    const board = document.querySelector("[data-kanban]");
    if (!board || typeof window.Sortable === "undefined") return;

    // No celular o status muda pela tela da OS — Sortable só no desktop.
    if (!isDesktop()) return;

    board.querySelectorAll("[data-column-status]").forEach((container) => {
      if (container.dataset.sortableReady === "1") return;
      container.dataset.sortableReady = "1";

      window.Sortable.create(container, {
        group: "kanban",
        animation: 150,
        draggable: ".card-os",
        sort: false,
        filter: "[data-card-toggle]",
        preventOnFilter: true,
        ghostClass: "card-os--ghost",
        chosenClass: "card-os--chosen",
        dragClass: "card-os--dragging",
        forceFallback: true,
        fallbackOnBody: true,
        fallbackTolerance: 4,
        fallbackClass: "card-os--fallback",
        delay: 140,
        delayOnTouchOnly: true,
        touchStartThreshold: 5,
        emptyInsertThreshold: 120,

        onStart: function (event) {
          isDragging = true;
          document.body.classList.add("is-kanban-dragging");
          document.querySelectorAll(".kanban__empty").forEach((el) => el.remove());

          const fallback = document.querySelector(".card-os--fallback, .sortable-fallback");
          if (fallback && event.item) {
            const rect = event.item.getBoundingClientRect();
            fallback.style.width = rect.width + "px";
            fallback.style.height = rect.height + "px";
            fallback.style.transition = "none";
          }
        },

        onEnd: function (event) {
          isDragging = false;
          document.body.classList.remove("is-kanban-dragging");
          const card = event.item;
          const target = event.to && event.to.dataset.columnStatus;
          const origin = event.from && event.from.dataset.columnStatus;

          if (!target || !origin || target === origin) {
            updateColumnCounts();
            return;
          }

          const originContainer = event.from;
          const originIndex = event.oldIndex;

          const revert = function () {
            if (!card.isConnected || !originContainer.isConnected) return;
            const reference = originContainer.querySelectorAll(".card-os")[originIndex];
            if (reference) {
              originContainer.insertBefore(card, reference);
            } else {
              originContainer.appendChild(card);
            }
            updateColumnCounts();
          };

          moveCard(card, target, revert);
        },
      });
    });

    updateColumnCounts();
  }

  // ---------- Recolher / expandir cards ----------

  function readDefaultCollapsed() {
    try {
      return localStorage.getItem(STORAGE_DEFAULT) === "1";
    } catch (error) {
      return false;
    }
  }

  function writeDefaultCollapsed(value) {
    try {
      localStorage.setItem(STORAGE_DEFAULT, value ? "1" : "0");
    } catch (error) {
      /* storage indisponível */
    }
  }

  function readOverrides() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_OVERRIDES) || "{}") || {};
    } catch (error) {
      return {};
    }
  }

  function writeOverrides(map) {
    try {
      // Limpa UUIDs que não estão mais no quadro.
      const alive = new Set(
        Array.from(document.querySelectorAll(".card-os[data-order-uuid]")).map(
          (card) => card.dataset.orderUuid
        )
      );
      const cleaned = {};
      Object.keys(map).forEach((uuid) => {
        if (alive.has(uuid)) cleaned[uuid] = map[uuid];
      });
      localStorage.setItem(STORAGE_OVERRIDES, JSON.stringify(cleaned));
    } catch (error) {
      /* ignore */
    }
  }

  function isCardCollapsed(uuid, defaults, overrides) {
    if (Object.prototype.hasOwnProperty.call(overrides, uuid)) {
      return Boolean(overrides[uuid]);
    }
    return defaults;
  }

  function setCardCollapsed(card, collapsed) {
    card.classList.toggle("card-os--collapsed", collapsed);
    const toggle = card.querySelector("[data-card-toggle]");
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", String(!collapsed));
    const plate = card.querySelector(".plate");
    const label = plate ? plate.textContent.trim() : "card";
    toggle.setAttribute("aria-label", (collapsed ? "Expandir card " : "Recolher card ") + label);
  }

  function syncGlobalButton(defaults) {
    document.querySelectorAll("[data-cards-toggle-all]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(defaults));
      const label = btn.querySelector("[data-cards-toggle-label]");
      if (label) label.textContent = defaults ? "Expandir cards" : "Recolher cards";
    });
  }

  function applyCardCollapseState() {
    const defaults = readDefaultCollapsed();
    const overrides = readOverrides();
    document.querySelectorAll(".card-os[data-order-uuid]").forEach((card) => {
      setCardCollapsed(card, isCardCollapsed(card.dataset.orderUuid, defaults, overrides));
    });
    syncGlobalButton(defaults);
  }

  function toggleOneCard(card) {
    const uuid = card.dataset.orderUuid;
    if (!uuid) return;

    const defaults = readDefaultCollapsed();
    const overrides = readOverrides();
    const next = !isCardCollapsed(uuid, defaults, overrides);

    if (next === defaults) {
      delete overrides[uuid];
    } else {
      overrides[uuid] = next;
    }
    writeOverrides(overrides);
    setCardCollapsed(card, next);
  }

  function toggleAllCards() {
    const next = !readDefaultCollapsed();
    writeDefaultCollapsed(next);
    writeOverrides({});
    document.querySelectorAll(".card-os[data-order-uuid]").forEach((card) => {
      setCardCollapsed(card, next);
    });
    syncGlobalButton(next);
  }

  function initCardCollapse() {
    if (!document.body.dataset.collapseReady) {
      document.body.dataset.collapseReady = "1";
      document.body.addEventListener("click", (event) => {
        const allBtn = event.target.closest("[data-cards-toggle-all]");
        if (allBtn) {
          event.preventDefault();
          toggleAllCards();
          return;
        }

        const oneBtn = event.target.closest("[data-card-toggle]");
        if (!oneBtn) return;
        event.preventDefault();
        event.stopPropagation();
        const card = oneBtn.closest(".card-os");
        if (card) toggleOneCard(card);
      });
    }

    applyCardCollapseState();
  }

  // ---------- Abas do quadro (celular) ----------

  let selectedColumn = "all";

  function applyBoardFilter() {
    document.querySelectorAll("[data-board-tab]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.dataset.boardTab === selectedColumn));
    });
    document.querySelectorAll(".kanban__column").forEach((column) => {
      const show = selectedColumn === "all" || column.dataset.columnSlug === selectedColumn;
      column.classList.toggle("kanban__column--hidden", !show);
    });
  }

  function initBoardTabs() {
    const nav = document.querySelector("[data-board-tabs]");
    if (!nav) return;

    if (!nav.querySelector('[data-board-tab="' + selectedColumn + '"]')) {
      selectedColumn = "all";
    }

    if (nav.dataset.tabsReady !== "1") {
      nav.dataset.tabsReady = "1";
      nav.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-board-tab]");
        if (!btn) return;
        selectedColumn = btn.dataset.boardTab;
        applyBoardFilter();
      });
    }

    applyBoardFilter();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initBoard();
    initBoardTabs();
    initCardCollapse();
  });

  document.body.addEventListener("htmx:beforeRequest", function (event) {
    if (isDragging || isMoving) event.preventDefault();
  });

  // Aplica recolhido antes do paint do swap para não “piscar” expandido.
  document.body.addEventListener("htmx:beforeSwap", function (event) {
    if (!event.detail || !event.detail.serverResponse) return;
    const target = event.target;
    if (!target || (target.id !== "board" && !target.querySelector?.("[data-kanban]"))) return;

    document.documentElement.classList.add("kanban-no-transition");
    const defaults = readDefaultCollapsed();
    const overrides = readOverrides();
    const tmp = document.createElement("div");
    tmp.innerHTML = event.detail.serverResponse;
    tmp.querySelectorAll(".card-os[data-order-uuid]").forEach((card) => {
      if (isCardCollapsed(card.dataset.orderUuid, defaults, overrides)) {
        card.classList.add("card-os--collapsed");
      }
    });
    // Reescreve a resposta já com as classes corretas.
    const boardNode = tmp.querySelector("#board");
    if (boardNode) {
      event.detail.serverResponse = tmp.innerHTML;
    }
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (!event.target) return;
    const swapped = event.target;
    if (swapped.id === "board" || swapped.id === "kanban" || swapped.querySelector("[data-kanban]")) {
      initBoard();
      initBoardTabs();
      initCardCollapse();
      requestAnimationFrame(() => {
        document.documentElement.classList.remove("kanban-no-transition");
      });
    }
  });
})();
