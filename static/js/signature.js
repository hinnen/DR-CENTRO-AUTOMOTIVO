/**
 * Assinatura de quem retirou o veículo.
 *
 * Desenha em um <canvas> e serializa como PNG em um input escondido. O campo é
 * opcional: se ninguém desenhar nada, o input continua vazio e o backend não
 * grava arquivo.
 */
(function () {
  "use strict";

  function setup(root) {
    if (root.dataset.signatureReady === "1") return;
    root.dataset.signatureReady = "1";

    const canvas = root.querySelector("[data-signature-pad]");
    const input = root.querySelector("input[name='signature']");
    const clearButton = root.querySelector("[data-signature-clear]");
    if (!canvas || !input) return;

    const context = canvas.getContext("2d");
    let ratio = 1;
    let drawing = false;
    let hasInk = false;

    /**
     * O canvas precisa de tamanho em pixels reais, senão o traço fica borrado em
     * telas retina. Redimensionar limpa o buffer, então a assinatura em
     * andamento é preservada e redesenhada.
     */
    function resize() {
      const snapshot = hasInk ? canvas.toDataURL("image/png") : null;
      ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth || canvas.parentNode.clientWidth || 300;
      const height = parseInt(canvas.getAttribute("height"), 10) || 180;

      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.height = height + "px";

      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.lineWidth = 2;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.strokeStyle = "#111827";

      if (snapshot) {
        const image = new Image();
        image.onload = function () {
          context.drawImage(image, 0, 0, width, height);
        };
        image.src = snapshot;
      }
    }

    function positionOf(event) {
      const box = canvas.getBoundingClientRect();
      return { x: event.clientX - box.left, y: event.clientY - box.top };
    }

    function start(event) {
      event.preventDefault();
      drawing = true;
      if (canvas.setPointerCapture && event.pointerId !== undefined) {
        canvas.setPointerCapture(event.pointerId);
      }
      const point = positionOf(event);
      context.beginPath();
      context.moveTo(point.x, point.y);
      // Um toque simples, sem arrastar, também vale como assinatura.
      context.lineTo(point.x, point.y);
      context.stroke();
      hasInk = true;
    }

    function move(event) {
      if (!drawing) return;
      event.preventDefault();
      const point = positionOf(event);
      context.lineTo(point.x, point.y);
      context.stroke();
    }

    function end() {
      if (!drawing) return;
      drawing = false;
      commit();
    }

    function commit() {
      input.value = hasInk ? canvas.toDataURL("image/png") : "";
      root.classList.toggle("signature--filled", hasInk);
    }

    function clear() {
      context.clearRect(0, 0, canvas.width, canvas.height);
      hasInk = false;
      commit();
    }

    canvas.addEventListener("pointerdown", start);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    // Não usa pointerleave: com setPointerCapture o traço continua fora do
    // canvas até soltar o botão — leave cortava a assinatura na borda.
    if (clearButton) clearButton.addEventListener("click", clear);

    window.addEventListener("resize", resize);
    resize();
  }

  function init() {
    document.querySelectorAll("[data-signature]").forEach(setup);
  }

  document.addEventListener("DOMContentLoaded", init);
  document.body && init();
  document.addEventListener("htmx:afterSwap", init);
})();
