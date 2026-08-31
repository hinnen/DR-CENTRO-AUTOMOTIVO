/**
 * DR Vistoria — interações do PWA mobile.
 * Checklist, fotos guiadas, OCR de placa (servidor / platerec) e SW.
 */
(function () {
  "use strict";

  function syncConditionSelection(item) {
    item.querySelectorAll(".m-cond").forEach(function (label) {
      var input = label.querySelector('input[type="radio"]');
      label.classList.toggle("is-selected", !!(input && input.checked));
    });

    var checked = item.querySelector('.m-conditions input[type="radio"]:checked');
    var note = item.querySelector("[data-note-for]");
    if (!note || !checked) return;

    var needsNote = checked.value === "ATENCAO" || checked.value === "AVARIA";
    note.classList.toggle("is-collapsed", !needsNote);
  }

  function syncFuelSelection(group) {
    group.querySelectorAll(".m-fuel__opt").forEach(function (label) {
      var input = label.querySelector('input[type="radio"]');
      label.classList.toggle("is-selected", !!(input && input.checked));
    });
  }

  function initChecklist() {
    document.querySelectorAll(".m-item").forEach(function (item) {
      syncConditionSelection(item);
      item.addEventListener("change", function (event) {
        if (event.target.matches('input[type="radio"]')) {
          syncConditionSelection(item);
        }
      });
    });

    document.querySelectorAll(".m-fuel").forEach(function (group) {
      syncFuelSelection(group);
      group.addEventListener("change", function () {
        syncFuelSelection(group);
      });
    });
  }

  function bindAutoSubmit(input) {
    if (input.dataset.ocrBound) return;
    input.dataset.ocrBound = "1";
    input.addEventListener("change", function () {
      if (!input.files || !input.files.length) return;
      var form = input.closest("form");
      if (!form) return;

      var label = form.querySelector(".m-shot__capture span, .m-photo-capture__btn");
      if (label) {
        label.dataset.prevText = label.textContent;
        label.textContent = "Enviando…";
      }

      if (window.htmx) {
        window.htmx.trigger(form, "submit");
      } else if (form.requestSubmit) {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  }

  function initPhotoAutoSubmit(root) {
    (root || document).querySelectorAll("[data-auto-submit]").forEach(bindAutoSubmit);
  }

  function initToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
      var close = toast.querySelector("[data-dismiss-toast]");
      if (close) {
        close.addEventListener("click", function () {
          toast.remove();
        });
      }
      window.setTimeout(function () {
        if (toast.isConnected) toast.remove();
      }, 4500);
    });
  }

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function setPlateStatus(message, isError) {
    var el = document.getElementById("m-plate-ocr-status");
    var btn = document.getElementById("m-plate-ocr-btn");
    if (el) {
      el.hidden = !message;
      el.textContent = message || "";
      el.classList.toggle("is-error", !!isError);
    }
    if (btn) {
      btn.classList.toggle("is-busy", !!message && !isError && /Lendo/i.test(message));
    }
  }

  function applyPlate(plate) {
    var input = document.getElementById("m-plate");
    if (!input) return;
    input.value = plate;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (window.htmx) {
      window.htmx.trigger(input, "input");
    }
  }

  function resizePlatePhoto(file, maxSide) {
    maxSide = maxSide || 1280;
    return new Promise(function (resolve, reject) {
      if (!window.createImageBitmap && !window.FileReader) {
        resolve(file);
        return;
      }

      var url = URL.createObjectURL(file);
      var img = new Image();

      img.onload = function () {
        URL.revokeObjectURL(url);
        var w = img.naturalWidth || img.width;
        var h = img.naturalHeight || img.height;
        var scale = Math.min(1, maxSide / Math.max(w, h));
        var cw = Math.max(1, Math.round(w * scale));
        var ch = Math.max(1, Math.round(h * scale));
        var canvas = document.createElement("canvas");
        canvas.width = cw;
        canvas.height = ch;
        var ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(file);
          return;
        }
        ctx.drawImage(img, 0, 0, cw, ch);
        canvas.toBlob(
          function (blob) {
            if (!blob) {
              resolve(file);
              return;
            }
            resolve(new File([blob], "placa.jpg", { type: "image/jpeg" }));
          },
          "image/jpeg",
          0.88
        );
      };

      img.onerror = function () {
        URL.revokeObjectURL(url);
        resolve(file);
      };

      img.src = url;
    });
  }

  function initPlateOcr() {
    var camera = document.querySelector("[data-plate-ocr]");
    if (!camera) return;

    var endpoint = camera.getAttribute("data-plate-ocr-url");
    if (!endpoint) return;

    camera.addEventListener("change", function () {
      var file = camera.files && camera.files[0];
      camera.value = "";
      if (!file) return;

      setPlateStatus("Lendo placa…");

      resizePlatePhoto(file, 1280)
        .then(function (uploadFile) {
          var body = new FormData();
          body.append("image", uploadFile, uploadFile.name || "placa.jpg");

          return fetch(endpoint, {
            method: "POST",
            body: body,
            headers: {
              "X-CSRFToken": csrfToken(),
              Accept: "application/json",
            },
            credentials: "same-origin",
          });
        })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data || !result.data.ok || !result.data.plate) {
            var error =
              (result.data && result.data.error) ||
              "Não deu para ler. Digite a placa ou tente outra foto.";
            setPlateStatus(error, true);
            return;
          }
          applyPlate(result.data.plate);
          setPlateStatus("Placa lida: " + result.data.plate);
        })
        .catch(function () {
          setPlateStatus("Falha na leitura. Digite a placa.", true);
        });
    });
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/m/sw.js", { scope: "/m/" }).catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    initChecklist();
    initPhotoAutoSubmit();
    initPlateOcr();
    initToasts();
    registerServiceWorker();
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (event.target && event.target.id === "m-photo-gallery") {
      initPhotoAutoSubmit(event.target);
      initToasts();
    }
  });

  document.body.addEventListener("htmx:responseError", function () {
    document.querySelectorAll(".m-shot__capture span, .m-photo-capture__btn").forEach(function (label) {
      if (label.dataset.prevText) label.textContent = label.dataset.prevText;
    });
  });

  document.body.addEventListener("htmx:sendError", function () {
    document.querySelectorAll(".m-shot__capture span, .m-photo-capture__btn").forEach(function (label) {
      if (label.dataset.prevText) label.textContent = label.dataset.prevText;
    });
  });
})();
