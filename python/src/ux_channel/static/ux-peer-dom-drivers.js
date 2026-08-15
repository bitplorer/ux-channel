/**
 * ux-peer-dom-drivers.js \u2014 Real DOM bindings for uxcPerception
 *
 * SEPARATE from kernel and perception. Provides:
 *   applyShadow / clearShadowDom / setPending
 *
 * Usage:
 *   <script src="ux-peer-kernel.js"></script>
 *   <script src="ux-peer-perception.js"></script>
 *   <script src="ux-peer-dom-drivers.js"></script>
 *   var kernel = uxcPeer.createPeerKernel({ drivers: uxcPeer.makeWebDrivers() });
 *   var perc = uxcPerception.attach(kernel, uxcPeerDom.perceptionOptions());
 */
(function (global) {
  "use strict";

  function qs(sel) {
    if (!sel) return null;
    try { return document.querySelector(sel); } catch (e) { return null; }
  }

  function applyShadow(target, html) {
    var el = qs(target);
    if (!el) return;
    el.setAttribute("data-uxc-shadow", "1");
    el.style.opacity = "0.55";
    if (html != null) {
      if (!el._uxcRealHtml) el._uxcRealHtml = el.innerHTML;
      el.innerHTML = html;
    }
  }

  function clearShadowDom(target) {
    var el = qs(target);
    if (!el) return;
    el.removeAttribute("data-uxc-shadow");
    el.style.opacity = "";
    if (el._uxcRealHtml != null) {
      delete el._uxcRealHtml;
    }
  }

  function setPending(target, isPending) {
    var el = qs(target);
    if (!el) return;
    if (isPending) {
      el.setAttribute("aria-busy", "true");
      el.classList.add("uxc-pending");
    } else {
      el.removeAttribute("aria-busy");
      el.classList.remove("uxc-pending");
    }
  }

  function perceptionOptions(extra) {
    extra = extra || {};
    return Object.assign({
      coalesceMs: 120,
      applyShadow: applyShadow,
      clearShadowDom: clearShadowDom,
      setPending: setPending,
    }, extra);
  }

  function applyDomOps(ops) {
    if (!ops) return;
    for (var i = 0; i < ops.length; i++) {
      var op = ops[i];
      if (!op || !op.op) continue;
      var el = qs(op.target);
      if (op.op === "morph" || op.op === "swap") {
        if (el && op.html != null) el.innerHTML = op.html;
      } else if (op.op === "set_text") {
        if (el && op.text != null) el.textContent = op.text;
      } else if (op.op === "toast") {
        showToast(op.message, op.level || "info", op.duration_ms);
      } else if (op.op === "remove") {
        if (el && el.parentNode) el.parentNode.removeChild(el);
      }
    }
  }

  function showToast(message, level, durationMs) {
    var host = document.getElementById("uxc-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "uxc-toast-host";
      host.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;";
      document.body.appendChild(host);
    }
    var t = document.createElement("div");
    t.textContent = message || "";
    t.setAttribute("data-level", level || "info");
    t.style.cssText = "padding:10px 14px;border-radius:8px;background:#1e293b;color:#f8fafc;box-shadow:0 4px 12px rgba(0,0,0,.25);font:14px system-ui;";
    if (level === "error") t.style.background = "#7f1d1d";
    if (level === "success") t.style.background = "#14532d";
    host.appendChild(t);
    var ms = durationMs != null ? Number(durationMs) : 2800;
    setTimeout(function () {
      if (t.parentNode) t.parentNode.removeChild(t);
    }, Math.max(0, ms));
  }

  var api = {
    applyShadow: applyShadow,
    clearShadowDom: clearShadowDom,
    setPending: setPending,
    perceptionOptions: perceptionOptions,
    applyDomOps: applyDomOps,
    showToast: showToast,
    version: "dom-drivers.v1",
  };
  if (typeof global !== "undefined") global.uxcPeerDom = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
