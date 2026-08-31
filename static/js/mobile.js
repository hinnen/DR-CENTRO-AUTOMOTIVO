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

  function hidePlateConfirm() {
    var box = document.getElementById("m-plate-confirm");
    if (box) box.hidden = true;
  }

  function showPlateConfirm(plate, alternatives) {
    var box = document.getElementById("m-plate-confirm");
    var msg = document.getElementById("m-plate-confirm-msg");
    var okBtn = document.getElementById("m-plate-confirm-ok");
    var editBtn = document.getElementById("m-plate-confirm-edit");
    var input = document.getElementById("m-plate");
    if (!box || !msg || !okBtn || !editBtn || !input) {
      applyPlate(plate);
      setPlateStatus("Confira a placa: " + plate);
      return;
    }

    var altText = "";
    if (alternatives && alternatives.length) {
      altText = " Outra leitura possível: " + alternatives.join(", ") + ".";
    }
    msg.textContent =
      "Li a placa como " +
      plate +
      ". Confirme se está correta antes de seguir." +
      altText;
    box.hidden = false;
    input.value = plate;

    okBtn.onclick = function () {
      hidePlateConfirm();
      applyPlate(plate);
      setPlateStatus("Placa confirmada: " + plate);
    };
    editBtn.onclick = function () {
      hidePlateConfirm();
      setPlateStatus("Corrija a placa e continue.");
      input.focus();
      try {
        input.select();
      } catch (_) {}
    };
  }

  function resizePlatePhoto(file, maxSide) {
    maxSide = maxSide || 800;
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
          0.8
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

    var warmupUrl = camera.getAttribute("data-plate-ocr-warmup-url");
    var warmReady = !warmupUrl;
    var warmPromise = null;

    function warmEngine() {
      if (!warmupUrl || warmPromise) return warmPromise;
      warmPromise = fetch(warmupUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken(),
          Accept: "application/json",
        },
        credentials: "same-origin",
      })
        .then(function (response) {
          warmReady = response.ok;
          return response;
        })
        .catch(function () {
          warmReady = false;
        });
      return warmPromise;
    }

    // Aquecer em background ao abrir a tela — 1ª foto não paga o load do modelo.
    window.setTimeout(function () {
      warmEngine();
    }, 120);

    camera.addEventListener("change", function () {
      var file = camera.files && camera.files[0];
      camera.value = "";
      if (!file) return;

      setPlateStatus(warmReady ? "Lendo placa…" : "Preparando leitor…");

      var ready = warmEngine() || Promise.resolve();

      ready
        .catch(function () {
          /* segue mesmo sem warm */
        })
        .then(function () {
          setPlateStatus("Lendo placa…");
          // 800px + JPEG 0.8: menos upload e inferência mais rápida no Starter.
          return resizePlatePhoto(file, 800);
        })
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
            hidePlateConfirm();
            setPlateStatus(error, true);
            return;
          }
          hidePlateConfirm();
          if (result.data.needs_confirmation) {
            setPlateStatus("Confirme a placa lida.");
            showPlateConfirm(result.data.plate, result.data.alternatives || []);
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

  function isStandalone() {
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
      return true;
    }
    return window.navigator.standalone === true;
  }

  function isIos() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent || "");
  }

  function isLikelyDesktop() {
    if (window.matchMedia && window.matchMedia("(pointer: fine) and (min-width: 900px)").matches) {
      return true;
    }
    return !/android|iphone|ipad|ipod|mobile/i.test(navigator.userAgent || "");
  }

  function initPwaInstall() {
    var root = document.querySelector("[data-m-install]");
    if (!root) return;

    var continueUrl = root.getAttribute("data-continue-url") || "/m/";
    var loginUrl = root.getAttribute("data-login-url") || "/conta/entrar/?next=/m/";
    var btn = document.getElementById("m-install-btn");
    var iosBox = document.getElementById("m-install-ios");
    var hint = document.getElementById("m-install-hint");
    var desk = document.getElementById("m-install-desk");
    var continueLink = document.getElementById("m-install-continue");
    var deferred = null;

    registerServiceWorker();

    if (isStandalone()) {
      window.location.replace(continueUrl);
      return;
    }

    if (continueLink) {
      continueLink.setAttribute("href", loginUrl);
    }

    if (isLikelyDesktop() && desk) {
      desk.hidden = false;
    }

    if (isIos()) {
      if (iosBox) iosBox.hidden = false;
      return;
    }

    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferred = event;
      if (btn) btn.hidden = false;
      if (hint) hint.hidden = true;
    });

    window.addEventListener("appinstalled", function () {
      deferred = null;
      if (btn) btn.hidden = true;
      window.location.replace(loginUrl);
    });

    if (btn) {
      btn.addEventListener("click", function () {
        if (!deferred) return;
        deferred.prompt();
        deferred.userChoice.finally(function () {
          deferred = null;
          btn.hidden = true;
          if (hint) hint.hidden = false;
        });
      });
    }

    // Chrome às vezes só libera o evento após interação; mostra dica após 1,2s.
    window.setTimeout(function () {
      if (!deferred && hint && !isIos()) hint.hidden = false;
    }, 1200);
  }

  function syncPrioritySelection(group) {
    group.querySelectorAll(".m-priority__opt").forEach(function (label) {
      var input = label.querySelector('input[type="radio"]');
      label.classList.toggle("is-selected", !!(input && input.checked));
    });
  }

  function initPriority() {
    document.querySelectorAll(".m-priority").forEach(function (group) {
      syncPrioritySelection(group);
      group.addEventListener("change", function () {
        syncPrioritySelection(group);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initChecklist();
    initPriority();
    initPhotoAutoSubmit();
    initPlateOcr();
    initToasts();
    registerServiceWorker();
    initPwaInstall();
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
