/**
 * uxchannel client runtime v0.1.0
 * Intent → POST/SSE → apply Result.ops
 * - focus/scroll restore, concurrency, version check
 * - bridge orphan reaper, optimistic hooks, SSE apply
 * - EventSource push: data-channel-push-topic / subscribePush
 */
(function (global) {
  "use strict";

  // Idempotent: a second <script src=ux-channel.js> must not double-bind clicks.
  if (global.__UX_CHANNEL_RUNTIME_LOADED__) {
    try {
      console.warn("[ux-channel] runtime already loaded — skipping re-init");
    } catch (e0) {}
    return;
  }
  global.__UX_CHANNEL_RUNTIME_LOADED__ = true;

  var ENDPOINT_ATTR = "data-channel-endpoint";
  var DEFAULT_ENDPOINT = "/ux-channel/action";
  var VERSION = "0.1.0";
  var active = 0;
  var maxConcurrent = 3;
  var queue = [];
  var signals = Object.create(null);
  var optimisticStack = [];
  var effectTimers = Object.create(null);
  var effectTimerGen = 1;

  // ── Client error plane ─────────────────────────────────────────────
  // Body attrs / uxChannel.configure({ ... }):
  //   data-channel-auto-toast="0"
  //   data-channel-toast-refresh-errors
  //   data-channel-field-errors="0"
  //   data-channel-error-log="32"
  var errorLog = [];
  var errorConfig = {
    autoToast: true,
    toastRefreshErrors: false,
    fieldErrors: true,
    logSize: 40,
    dedupeMs: 2500,
  };
  var recentToasts = Object.create(null);
  var proofConfig = { required: false, secret: null, sessionId: "default", gen: 1 };


  function hydrateSignalsFromStorage() {
    try {
      if (typeof localStorage === "undefined") return;
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (!k || k.indexOf("channel:sig:") !== 0) continue;
        var path = k.slice(8);
        try {
          var raw = localStorage.getItem(k);
          if (raw == null) continue;
          setByPath(signals, path, JSON.parse(raw));
        } catch (e1) {}
      }
    } catch (e0) {}
  }

  function emitChannel(name, detail) {
    try { document.dispatchEvent(new CustomEvent(name, { detail: detail })); }
    catch (e) {}
  }

  function readErrorConfigFromDom() {
    var b = document.body;
    if (!b) return;
    if (b.getAttribute("data-channel-auto-toast") === "0") errorConfig.autoToast = false;
    if (b.hasAttribute("data-channel-toast-refresh-errors")) errorConfig.toastRefreshErrors = true;
    if (b.getAttribute("data-channel-field-errors") === "0") errorConfig.fieldErrors = false;
    var n = parseInt(b.getAttribute("data-channel-error-log") || "", 10);
    if (isFinite(n) && n > 0) errorConfig.logSize = n;
  }

  function configureErrors(opts) {
    if (!opts) return Object.assign({}, errorConfig);
    if (typeof opts.autoToast === "boolean") errorConfig.autoToast = opts.autoToast;
    if (typeof opts.toastRefreshErrors === "boolean") errorConfig.toastRefreshErrors = opts.toastRefreshErrors;
    if (typeof opts.fieldErrors === "boolean") errorConfig.fieldErrors = opts.fieldErrors;
    if (typeof opts.logSize === "number" && opts.logSize > 0) errorConfig.logSize = opts.logSize;
    if (typeof opts.dedupeMs === "number" && opts.dedupeMs >= 0) errorConfig.dedupeMs = opts.dedupeMs;
    if (opts.proofsRequired != null) proofConfig.required = !!opts.proofsRequired;
    if (opts.proofSecret !== undefined) proofConfig.secret = opts.proofSecret ? String(opts.proofSecret) : null;
    if (opts.sessionId != null) proofConfig.sessionId = String(opts.sessionId);
    if (opts.gen != null) proofConfig.gen = Number(opts.gen) || 1;
    return Object.assign({}, errorConfig, { proofsRequired: proofConfig.required });
  }

  function pushErrorLog(entry) {
    entry.ts = entry.ts || Date.now();
    errorLog.push(entry);
    while (errorLog.length > errorConfig.logSize) errorLog.shift();
    return entry;
  }

  function lastErrors(n) {
    return errorLog.slice(-(n || 10));
  }

  function clearErrorLog() { errorLog = []; }

  function safeToast(message, level, durationMs) {
    message = String(message || "");
    if (!message) return;
    if (level === "error" && !errorConfig.autoToast) return;
    var now = Date.now();
    if (recentToasts[message] && now - recentToasts[message] < errorConfig.dedupeMs) return;
    recentToasts[message] = now;
    Object.keys(recentToasts).forEach(function (k) {
      if (now - recentToasts[k] > errorConfig.dedupeMs * 4) delete recentToasts[k];
    });
    toast(message, level || "info", durationMs);
  }

  /** Central error bus: log + channel:error + optional toast. */
  function reportError(kind, payload) {
    payload = payload || {};
    var errObj = payload.error || null;
    var entry = {
      kind: kind || "unknown",
      message: payload.message || (errObj && (errObj.message || errObj.code)) || "Error",
      code: payload.code || (errObj && errObj.code) || null,
      error: errObj,
      result: payload.result || null,
      source: payload.source || null,
      op: payload.op || null,
      status: payload.status || null,
      retryable: payload.retryable != null
        ? payload.retryable
        : !!(errObj && errObj.retryable),
      ts: Date.now(),
    };
    pushErrorLog(entry);
    emitChannel("channel:error", {
      result: entry.result,
      error: entry.error || { code: entry.code || kind, message: entry.message },
      kind: entry.kind,
      source: entry.source,
      status: entry.status,
      op: entry.op,
      entry: entry,
    });
    if (payload.toast !== false && errorConfig.autoToast) {
      safeToast(entry.message, payload.level || "error", payload.durationMs);
    }
    return entry;
  }

  function applyFieldErrors(fields, root) {
    if (!errorConfig.fieldErrors || !fields) return;
    root = root || document;
    Object.keys(fields).forEach(function (name) {
      var msgs = fields[name];
      var text = Array.isArray(msgs) ? msgs.join(" ") : String(msgs || "");
      var nodes = qsa('[data-channel-error="' + name.replace(/"/g, "") + '"]', root);
      if (!nodes.length) {
        var input = qs('[name="' + name.replace(/"/g, "") + '"]', root);
        if (input && input.parentNode) {
          var sib = input.parentNode.querySelector("[data-channel-error]");
          if (sib) nodes = [sib];
        }
      }
      nodes.forEach(function (n) {
        n.textContent = text;
        n.hidden = !text;
        n.setAttribute("role", "alert");
      });
      var field = qs('[name="' + name.replace(/"/g, "") + '"]', root);
      if (field) {
        field.setAttribute("aria-invalid", text ? "true" : "false");
        if (text) field.classList.add("ux-field-error");
        else field.classList.remove("ux-field-error");
      }
    });
    emitChannel("channel:fieldErrors", { fields: fields });
  }

  function clearFieldErrors(root) {
    root = root || document;
    qsa("[data-channel-error]", root).forEach(function (n) {
      n.textContent = "";
      n.hidden = true;
    });
    qsa(".ux-field-error", root).forEach(function (n) {
      n.classList.remove("ux-field-error");
      n.removeAttribute("aria-invalid");
    });
  }

  function endpoint() {
    var el = document.body && document.body.getAttribute(ENDPOINT_ATTR);
    return el || DEFAULT_ENDPOINT;
  }

  function concurrency() {
    var raw = document.body && document.body.getAttribute("data-channel-concurrency");
    var n = raw ? parseInt(raw, 10) : maxConcurrent;
    return isFinite(n) && n > 0 ? n : maxConcurrent;
  }

  function isDev() {
    return !!(document.body && document.body.hasAttribute("data-channel-dev"));
  }

  function parseJSON(raw, fallback) {
    if (raw == null || raw === "") return fallback;
    try { return JSON.parse(raw); } catch (e) { return fallback; }
  }

  function qs(sel, root) {
    try { return (root || document).querySelector(sel); } catch (e) { return null; }
  }

  function qsa(sel, root) {
    try { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
    catch (e) { return []; }
  }

  function toast(message, level, durationMs) {
    var host = document.getElementById("ux-channel-toasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "ux-channel-toasts";
      host.setAttribute("aria-live", level === "error" ? "assertive" : "polite");
      host.setAttribute("style", "position:fixed;z-index:99999;right:1rem;bottom:1rem;display:flex;flex-direction:column;gap:.5rem;max-width:22rem;font:14px/1.4 system-ui,sans-serif;pointer-events:none;");
      document.body.appendChild(host);
    }
    var colors = { info: "#1e293b", success: "#166534", warning: "#854d0e", error: "#991b1b" };
    var el = document.createElement("div");
    el.setAttribute("role", "status");
    el.textContent = message;
    el.setAttribute("style", "pointer-events:auto;background:" + (colors[level] || colors.info) + ";color:#fff;padding:.75rem 1rem;border-radius:.5rem;box-shadow:0 4px 12px rgba(0,0,0,.15);");
    host.appendChild(el);
    setTimeout(function () { if (el.parentNode) el.remove(); }, durationMs || 4000);
  }

  function snapshotFocus() {
    var ae = document.activeElement;
    if (!ae || ae === document.body) return null;
    var selStart = null, selEnd = null;
    try {
      if (typeof ae.selectionStart === "number") {
        selStart = ae.selectionStart;
        selEnd = ae.selectionEnd;
      }
    } catch (e) {}
    return {
      id: ae.id || null,
      name: ae.getAttribute && ae.getAttribute("name"),
      tag: ae.tagName,
      selStart: selStart,
      selEnd: selEnd,
    };
  }

  function restoreFocus(snap) {
    if (!snap) return;
    var el = null;
    if (snap.id) el = document.getElementById(snap.id);
    if (!el && snap.name) el = document.querySelector('[name="' + snap.name + '"]');
    if (el && el.focus) {
      el.focus();
      try {
        if (snap.selStart != null && typeof el.setSelectionRange === "function") {
          el.setSelectionRange(snap.selStart, snap.selEnd);
        }
      } catch (e) {}
    }
  }

  function snapshotScroll(targetSel) {
    var map = {};
    if (targetSel) {
      var t = qs(targetSel);
      if (t) map[targetSel] = t.scrollTop;
    }
    map["__window"] = window.scrollY || 0;
    return map;
  }

  function restoreScroll(map) {
    if (!map) return;
    Object.keys(map).forEach(function (k) {
      if (k === "__window") {
        window.scrollTo(0, map[k]);
        return;
      }
      var el = qs(k);
      if (el) el.scrollTop = map[k];
    });
  }

  function applyMorph(targetSel, html) {
    var target = qs(targetSel);
    if (!target) {
      console.warn("[ux-channel] morph target not found:", targetSel);
      return null;
    }
    var focusSnap = snapshotFocus();
    var scrollSnap = snapshotScroll(targetSel);
    var tpl = document.createElement("template");
    tpl.innerHTML = String(html).trim();
    var next = tpl.content.firstElementChild;
    if (!next) {
      target.innerHTML = html;
      restoreFocus(focusSnap);
      restoreScroll(scrollSnap);
      return target;
    }
    // CRITICAL: ch.refresh morphs often omit data-channel-id on the fragment root.
    // Without Idiomorph we replaceWith(next), which would drop the stable id and
    // every later morph would warn "target not found". Copy id / other uid attrs.
    if (target.hasAttribute("data-channel-id") && !next.hasAttribute("data-channel-id")) {
      next.setAttribute("data-channel-id", target.getAttribute("data-channel-id"));
    }
    if (global.Idiomorph && typeof global.Idiomorph.morph === "function") {
      global.Idiomorph.morph(target, next);
    } else {
      target.replaceWith(next);
    }
    restoreFocus(focusSnap);
    restoreScroll(scrollSnap);
    reaperBridges();
    return qs(targetSel) || next;
  }

  function applySwap(targetSel, html, mode) {
    var target = qs(targetSel);
    if (!target) return;
    mode = mode || "outerHTML";
    if (mode === "innerHTML") { target.innerHTML = html; reaperBridges(); return; }
    if (mode === "outerHTML") { applyMorph(targetSel, html); return; }
    if (mode === "delete") { target.remove(); reaperBridges(); return; }
    if (mode === "none") return;
    target.insertAdjacentHTML(mode, html);
    reaperBridges();
  }

  function reaperBridges() {
    if (!global.uxBridge || !global.uxBridge.instances) return;
    var inst = global.uxBridge.instances;
    Object.keys(inst).forEach(function (id) {
      var host = document.querySelector('[data-channel-bridge-id="' + id + '"]');
      if (!host) {
        if (global.uxBridge.apply) {
          global.uxBridge.apply({ op: "bridge.destroy", id: id });
        }
      }
    });
  }

  function setByPath(obj, path, value) {
    var parts = String(path).split(".");
    var cur = obj;
    for (var i = 0; i < parts.length - 1; i++) {
      if (!cur[parts[i]] || typeof cur[parts[i]] !== "object") cur[parts[i]] = {};
      cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
  }

  function safeHref(href) {
    if (!href || typeof href !== "string") return null;
    var h = href.trim();
    if (!h || h.indexOf("//") === 0) return null;
    var lower = h.toLowerCase();
    var path = h.split("?")[0].split("#")[0];
    if (path.indexOf(":") !== -1) {
      var scheme = lower.split(":")[0];
      if (scheme === "javascript" || scheme === "data" || scheme === "vbscript" || scheme === "file") return null;
      if (scheme !== "http" && scheme !== "https" && scheme !== "mailto" && scheme !== "tel") {
        if (/^[a-z][a-z0-9+.-]*:/.test(lower)) return null;
      }
    }
    return h;
  }

  function applyOp(op) {
    if (!op || !op.op) return;
    switch (op.op) {
      case "morph": applyMorph(op.target, op.html); break;
      case "swap": applySwap(op.target, op.html, op.swap); break;
      case "remove":
        var rm = qs(op.target); if (rm) { rm.remove(); reaperBridges(); }
        break;
      case "set_text":
        var te = qs(op.target); if (te) te.textContent = op.text; break;
      case "set_attr":
        var ae = qs(op.target);
        if (ae && op.attrs) {
          Object.keys(op.attrs).forEach(function (k) {
            var v = op.attrs[k];
            if (v === null || v === undefined) ae.removeAttribute(k);
            else ae.setAttribute(k, v);
          });
        }
        break;
      case "clear_errors":
        var root = op.target ? qs(op.target) : document;
        if (root) {
          qsa("[data-channel-error]", root).forEach(function (n) { n.textContent = ""; n.hidden = true; });
        }
        break;
      case "toast": toast(op.message || "", op.level || "info", op.duration_ms); break;
      case "navigate":
        var nh = safeHref(op.href);
        if (!nh) { console.warn("[ux-channel] blocked unsafe navigate", op.href); break; }
        if (op.replace) location.replace(nh); else location.href = nh;
        break;
      case "reload": location.reload(); break;
      case "push_url":
        var ph = safeHref(op.href);
        if (!ph) { console.warn("[ux-channel] blocked unsafe push_url", op.href); break; }
        if (op.replace) history.replaceState(null, "", ph);
        else history.pushState(null, "", ph);
        break;
      case "focus":
        var fe = qs(op.target);
        if (fe && fe.focus) { fe.focus(); if (op.select && fe.select) fe.select(); }
        break;
      case "scroll":
        if (op.target) {
          var se = qs(op.target);
          if (se && se.scrollIntoView) se.scrollIntoView({ behavior: op.behavior || "auto", block: "nearest" });
        } else {
          window.scrollTo({ top: op.top || 0, left: op.left || 0, behavior: op.behavior || "auto" });
        }
        break;
      case "dispatch":
        var de = op.target ? qs(op.target) : document.body;
        if (de) de.dispatchEvent(new CustomEvent(op.name, { detail: op.detail, bubbles: op.bubbles !== false }));
        break;
      case "signal.set":
        setByPath(signals, op.path, op.value);
        // Optional chrome persist (server allowlisted only — never money/secrets)
        var doPersist = op.persist === true || (op.meta && op.meta.persist === true);
        if (doPersist && op.path && typeof localStorage !== "undefined") {
          try {
            localStorage.setItem("channel:sig:" + String(op.path), JSON.stringify(op.value));
          } catch (e) {}
        }
        document.dispatchEvent(new CustomEvent("channel:signal", {
          detail: { path: op.path, value: op.value, persist: !!doPersist }
        }));
        break;
      case "noop": break;
      case "bridge.mount":
      case "bridge.update":
      case "bridge.call":
      case "bridge.destroy":
        if (global.uxBridge && typeof global.uxBridge.apply === "function") {
          return global.uxBridge.apply(op);
        }
        console.warn("[ux-channel] bridge op without uxBridge:", op.op);
        break;
      case "seq":
        (op.ops || []).forEach(applyOp);
        break;
      case "timer.set":
        (function (top) {
          var tid = String(top.id || "t");
          var ms = Math.max(0, Math.min(Number(top.ms) || 0, 600000));
          var body = top.ops || [];
          var gen = effectTimerGen;
          if (effectTimers[tid] && effectTimers[tid].handle) {
            try { clearTimeout(effectTimers[tid].handle); } catch (eT) {}
          }
          var handle = setTimeout(function () {
            if (gen !== effectTimerGen) return;
            delete effectTimers[tid];
            body.forEach(applyOp);
          }, ms);
          effectTimers[tid] = { handle: handle, gen: gen };
        })(op);
        break;
      case "timer.clear":
        (function (cid) {
          if (effectTimers[cid] && effectTimers[cid].handle) {
            try { clearTimeout(effectTimers[cid].handle); } catch (eC) {}
          }
          delete effectTimers[cid];
        })(String(op.id || ""));
        break;
      case "invoke":
        document.dispatchEvent(new CustomEvent("channel:invoke", {
          detail: { ref: op.ref, method: op.method, args: op.args || {} }
        }));
        (op.ops || []).forEach(applyOp);
        break;
      default:
        console.warn("[ux-channel] unknown op:", op.op);
    }
  }

  function checkRuntime(result) {
    var rt = result && result.meta && result.meta.runtime;
    if (rt && rt.split(".")[0] !== VERSION.split(".")[0] && isDev()) {
      console.warn("[ux-channel] server runtime", rt, "client", VERSION);
    }
  }

  /** Normalize WS envelope {type:"result", ok, ops, ...} or bare Result. */
  function normalizeResult(raw) {
    if (!raw || typeof raw !== "object") return raw;
    // Already a Result shape
    if ("ok" in raw || "ops" in raw || raw.error) return raw;
    return raw;
  }

  /**
   * Client hooks — document CustomEvents + uxChannel.on / reportError.
   *   channel:beforeApply   { result, preventApply, source } — set preventApply to cancel
   *   channel:error         all reported failures (kind, entry, ...)
   *   channel:fieldErrors   validation fields painted
   *   channel:refreshErrors meta.refresh_errors
   *   channel:opError       single op threw
   *   channel:networkError  fetch/timeout
   *   channel:afterApply / channel:applied
   *   channel:push / channel:pushError / channel:wsError
   */
  function canonicalJson(v) {
    if (v === null || typeof v !== "object") return JSON.stringify(v);
    if (Array.isArray(v)) return "[" + v.map(canonicalJson).join(",") + "]";
    var keys = Object.keys(v).sort();
    return "{" + keys.map(function (k) { return JSON.stringify(k) + ":" + canonicalJson(v[k]); }).join(",") + "}";
  }

  function b64urlEncode(buf) {
    var bin = "";
    var bytes = new Uint8Array(buf);
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function verifyEffectProof(result) {
    if (!proofConfig.required) return Promise.resolve(true);
    var eff = result && result.meta && result.meta.effect;
    if (!eff || !proofConfig.secret || !global.crypto || !crypto.subtle) return Promise.resolve(false);
    var core = { error: result.error == null ? null : result.error, ok: result.ok, ops: result.ops || [] };
    var enc = new TextEncoder();
    return crypto.subtle.digest("SHA-256", enc.encode(canonicalJson(core))).then(function (dig) {
      var bh = Array.from(new Uint8Array(dig)).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
      if (eff.body_hash !== bh) return false;
      if (String(eff.session_id) !== String(proofConfig.sessionId)) return false;
      if (Number(eff.gen) !== Number(proofConfig.gen)) return false;
      if ((Date.now() / 1000) > Number(eff.exp)) return false;
      var payload = {
        body_hash: eff.body_hash,
        exp: Number(eff.exp),
        gen: Number(eff.gen),
        jti: eff.jti,
        kid: eff.kid,
        session_id: eff.session_id
      };
      return crypto.subtle.importKey(
        "raw",
        enc.encode(String(proofConfig.secret)),
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
      ).then(function (key) {
        return crypto.subtle.sign("HMAC", key, enc.encode(canonicalJson(payload)));
      }).then(function (sig) {
        return b64urlEncode(sig) === String(eff.sig || "");
      });
    }).catch(function () { return false; });
  }

  function applyResult(result, applyOpts) {
    applyOpts = applyOpts || {};
    if (!result) return Promise.resolve(result);
    result = normalizeResult(result);
    checkRuntime(result);

    var cancelBox = { result: result, preventApply: false, source: applyOpts.source || null };
    emitChannel("channel:beforeApply", cancelBox);
    if (cancelBox.preventApply) {
      emitChannel("channel:applyCancelled", cancelBox);
      return Promise.resolve(result);
    }

    return verifyEffectProof(result).then(function (okp) {
      if (!okp) {
        emitChannel("channel:proofRejected", { result: result });
        return result;
      }
      return applyResultOps(result, applyOpts);
    });
  }

  function applyResultOps(result, applyOpts) {

    var errs = (result.meta && result.meta.refresh_errors) || null;
    if (errs && errs.length) {
      emitChannel("channel:refreshErrors", { result: result, errors: errs, source: applyOpts.source });
      if (isDev()) console.warn("[ux-channel] refresh_errors", errs);
      if (errorConfig.toastRefreshErrors && result.ok !== false) {
        safeToast("Some regions failed to refresh", "warning", 3500);
      }
    }

    if (result.ok === false && result.error) {
      var err = result.error;
      var kind = (result.meta && result.meta.error_kind)
        || (err.code === "validation" ? "validation"
        : err.code === "render_error" ? "refresh"
        : err.code === "unauthorized" || err.code === "forbidden" ? "auth"
        : err.code === "network" || err.code === "timeout" || err.code === "rate_limited" ? "network"
        : "protocol");
      var ops0 = result.ops || [];
      var hasErrToast = ops0.some(function (o) {
        return o && o.op === "toast" && (o.level === "error" || o.level === "danger");
      });
      reportError(kind, {
        message: err.message || err.code || "Error",
        code: err.code,
        error: err,
        result: result,
        source: applyOpts.source || "apply",
        toast: !hasErrToast,
        retryable: err.retryable,
      });
      if (err.fields) applyFieldErrors(err.fields, document);
    }

    if (result.ok === false && optimisticStack.length) {
      var rb = optimisticStack.pop();
      if (rb && rb.html && rb.target) applyMorph(rb.target, rb.html);
    }
    if (result.ok && optimisticStack.length) optimisticStack.pop();

    var ops = result.ops || [];
    var chain = Promise.resolve();
    for (var i = 0; i < ops.length; i++) {
      (function (op, idx) {
        chain = chain.then(function () {
          try {
            if (result.ok === false && (op.op === "navigate" || op.op === "reload")) {
              if (isDev()) console.warn("[ux-channel] skip navigate on failed result");
              return;
            }
            var r = applyOp(op);
            if (r && typeof r.then === "function") {
              return Promise.resolve(r).catch(function (e) {
                reportError("op", {
                  message: "Op failed: " + (op.op || "?") + " — " + ((e && e.message) || e),
                  op: op,
                  source: applyOpts.source || "apply",
                  toast: isDev(),
                  level: "warning",
                });
                emitChannel("channel:opError", { op: op, index: idx, error: e, result: result });
              });
            }
            if (op.op === "navigate" || op.op === "reload") return new Promise(function () {});
          } catch (e) {
            reportError("op", {
              message: "Op failed: " + (op.op || "?") + " — " + ((e && e.message) || e),
              op: op,
              source: applyOpts.source || "apply",
              toast: isDev(),
              level: "warning",
            });
            emitChannel("channel:opError", { op: op, index: idx, error: e, result: result });
          }
        });
      })(ops[i], i);
    }
    return chain.then(function () {
      emitChannel("channel:afterApply", result);
      emitChannel("channel:applied", result);
      if (global.uxBridge && typeof global.uxBridge.scan === "function") {
        global.uxBridge.scan(document);
      }
      reaperBridges();
      return result;
    });
  }

  function requestId() {
    return "req_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function fetchTimeoutMs() {
    var raw = document.body && document.body.getAttribute("data-channel-timeout");
    var n = raw ? parseInt(raw, 10) : 30000;
    return isFinite(n) && n > 0 ? n : 30000;
  }

  function parseSSE(text) {
    var results = [];
    var blocks = text.split("\n\n");
    blocks.forEach(function (b) {
      var lines = b.split("\n");
      var data = [];
      lines.forEach(function (ln) {
        if (ln.indexOf("data:") === 0) data.push(ln.slice(5).trim());
      });
      if (data.length) {
        try {
          var env = JSON.parse(data.join("\n"));
          if (env && env.result) results.push(env.result);
          else if (env && env.ops) results.push(env);
        } catch (e) {}
      }
    });
    return results;
  }

  function parseRetryAfter(h) {
    if (h == null || h === "") return null;
    var s = String(h).trim();
    if (/^\d+(\.\d+)?$/.test(s)) return Math.max(0, parseFloat(s));
    // HTTP-date
    var t = Date.parse(s);
    if (!isNaN(t)) return Math.max(0, (t - Date.now()) / 1000);
    return null;
  }

  function mergeRetryAfter(body, res) {
    if (!body || typeof body !== "object") return body;
    var ra = null;
    try { ra = parseRetryAfter(res.headers.get("Retry-After")); } catch (e) {}
    if (ra == null && body.meta && body.meta.retry_after != null) {
      ra = parseRetryAfter(body.meta.retry_after);
    }
    if (ra == null) return body;
    body.meta = body.meta || {};
    if (body.meta.retry_after == null) body.meta.retry_after = ra;
    if (body.error && body.error.retryable == null && (body.error.code === "rate_limited" || res.status === 429)) {
      body.error.retryable = true;
    }
    return body;
  }

  function syntheticFailure(code, message, status, retryable) {
    return {
      ok: false,
      v: "1",
      ops: [],
      error: { code: code, message: message, retryable: !!retryable },
      meta: { http_status: status || null, client: true },
    };
  }


  /**
   * Build Intent headers: optional host CSRF + stable X-Channel: 1.
   *
   * Host token (optional):
   *   window.__UX_CHANNEL_CSRF__ = { token: "…", headers?: ["X-App-CSRF"] }
   *   or meta/input whose name matches /csrf|xsrf|authenticity/i
   *   or window.__UX_CHANNEL_HEADERS
   * Channel CSRF is always set last and never read from the host token.
   */
  function buildIntentHeaders(base) {
    var headers = base || {};
    var token = "";
    var forwardAs = ["X-CSRFToken", "X-CSRF-Token"];

    function isHostCsrfName(n) {
      if (!n) return false;
      n = String(n).toLowerCase();
      return n !== "x-channel" && /csrf|xsrf|authenticity[_-]?token/.test(n);
    }

    try {
      var cfg = typeof window !== "undefined" ? window.__UX_CHANNEL_CSRF__ : null;
      if (cfg && typeof cfg === "object") {
        if (cfg.token) token = String(cfg.token);
        if (cfg.headers && cfg.headers.length) {
          forwardAs = [];
          for (var i = 0; i < cfg.headers.length; i++) {
            var h = String(cfg.headers[i] || "");
            if (h && h.toLowerCase() !== "x-channel") forwardAs.push(h);
          }
          if (!forwardAs.length) forwardAs = ["X-CSRFToken", "X-CSRF-Token"];
        }
      }
      if (!token && typeof window !== "undefined") {
        token = String(window.__UX_CHANNEL_CSRF_TOKEN__ || "");
      }
    } catch (e0) {}

    try {
      if (!token && typeof document !== "undefined" && document.querySelectorAll) {
        var nodes = document.querySelectorAll("meta[name], input[name]");
        for (var j = 0; j < nodes.length; j++) {
          var nm = (nodes[j].getAttribute("name") || "").trim();
          if (!isHostCsrfName(nm)) continue;
          var val = nodes[j].tagName === "META"
            ? (nodes[j].getAttribute("content") || "")
            : (nodes[j].value || "");
          val = String(val).trim();
          if (val) { token = val; break; }
        }
      }
    } catch (e1) {}

    if (token) {
      for (var k = 0; k < forwardAs.length; k++) headers[forwardAs[k]] = token;
    }

    try {
      var extra = (typeof window !== "undefined" && window.__UX_CHANNEL_HEADERS) || {};
      if (extra && typeof extra === "object") {
        Object.keys(extra).forEach(function (key) {
          if (extra[key] != null && extra[key] !== "") headers[key] = String(extra[key]);
        });
      }
    } catch (e2) {}

    headers["X-Channel"] = "1";
    return headers;
  }


  function postIntent(intent, attempt) {
    attempt = attempt || 0;
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = null;
    var ms = fetchTimeoutMs();
    if (ctrl) timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, ms);
    var accept = intent.accept_stream ? "text/event-stream, application/ux-channel+json" : "application/ux-channel+json";
    var headers = buildIntentHeaders({
      "Content-Type": "application/ux-channel+json",
      Accept: accept,
      "X-Channel-Client-Version": VERSION,
    });
    return fetch(endpoint(), {
      method: "POST",
      headers: headers,
      body: JSON.stringify(intent),
      credentials: "same-origin",
      signal: ctrl ? ctrl.signal : undefined,
    })
      .then(function (res) {
        if (timer) clearTimeout(timer);
        if ((res.status === 502 || res.status === 503 || res.status === 504) && attempt < 1) {
          return new Promise(function (r) { setTimeout(r, 400); }).then(function () {
            return postIntent(intent, attempt + 1);
          });
        }
        var ct = res.headers.get("content-type") || "";
        if (ct.indexOf("event-stream") !== -1) {
          return res.text().then(function (text) {
            var parts = parseSSE(text);
            var chain = Promise.resolve();
            parts.forEach(function (body) {
              chain = chain.then(function () { return applyResult(body, { source: "sse-response" }); });
            });
            return chain.then(function () { return parts[parts.length - 1] || { ok: true, ops: [] }; });
          });
        }
        if (ct.indexOf("json") === -1) {
          return res.text().then(function (t) {
            var body = syntheticFailure(
              res.status === 429 ? "rate_limited" : "http_error",
              "non-JSON response (" + res.status + "): " + String(t).slice(0, 120),
              res.status,
              res.status >= 500 || res.status === 429
            );
            return applyResult(body, { source: "http" }).then(function () { return body; });
          });
        }
        return res.json().then(function (body) {
          if (body && body.ok === undefined && res.status >= 400) {
            body = syntheticFailure(
              (body.error && body.error.code) || ("http_" + res.status),
              (body.error && body.error.message) || body.detail || ("HTTP " + res.status),
              res.status,
              res.status === 429 || res.status >= 500
            );
          }
          body = mergeRetryAfter(body, res);
          if (res.status === 429) {
            var ra = body && body.meta && body.meta.retry_after;
            var msg = (body.error && body.error.message) || "Too many requests";
            if (ra != null && Number(ra) > 0) msg = msg + " — retry after " + Math.ceil(Number(ra)) + "s";
            if (body && body.ok !== false) safeToast(msg, "warning");
            else if (errorConfig.autoToast) { /* applyResult will toast error */ }
            emitChannel("channel:retryAfter", { seconds: ra, result: body, status: res.status });
          }
          return applyResult(body, { source: "http" }).then(function () { return body; });
        });
      })
      .catch(function (err) {
        if (timer) clearTimeout(timer);
        var msg = err && err.name === "AbortError"
          ? ("Request timed out after " + ms + "ms")
          : String((err && err.message) || err || "Network error");
        var body = syntheticFailure(
          err && err.name === "AbortError" ? "timeout" : "network",
          msg,
          null,
          true
        );
        // applyResult reports protocol-style error once (avoid double toast)
        emitChannel("channel:networkError", { error: err, message: msg, result: body });
        emitChannel("channel:applyError", err);
        return applyResult(body, { source: "network" }).then(function () {
          var e = new Error(msg);
          e.result = body;
          e.handled = true;
          throw e;
        });
      });
  }

  function enqueue(fn) {
    return new Promise(function (resolve, reject) {
      queue.push({ fn: fn, resolve: resolve, reject: reject });
      pump();
    });
  }

  function pump() {
    while (active < concurrency() && queue.length) {
      (function (item) {
        active++;
        Promise.resolve()
          .then(item.fn)
          .then(item.resolve, item.reject)
          .then(function () {
            active--;
            pump();
          });
      })(queue.shift());
    }
  }

  function peerHello() {
    return {
      profiles: ["web.v1"],
      features: ["seq", "invoke"],
      ir: "1",
      effect_proof: !!proofConfig.required,
    };
  }

  function attachHello(intent) {
    if (!intent || typeof intent !== "object") return intent;
    var meta = intent.meta && typeof intent.meta === "object" ? intent.meta : {};
    if (!meta.hello) meta.hello = peerHello();
    intent.meta = meta;
    return intent;
  }

  function runAction(action, args, cap, target, opts) {
    opts = opts || {};
    var intent = {
      v: "1",
      action: action,
      args: args || {},
      form: opts.form,
      cap: cap || undefined,
      target: target || undefined,
      request_id: requestId(),
      idempotency_key: opts.idempotency_key,
      accept_stream: !!opts.stream,
    };
    attachHello(intent);
    if (opts.optimistic && target) {
      var el = qs(target);
      if (el) optimisticStack.push({ target: target, html: el.outerHTML });
      if (opts.optimisticHtml) applyMorph(target, opts.optimisticHtml);
    }
    return enqueue(function () { return postIntent(intent); });
  }

  // --- Signal → Intent ----------------------------------------------------
  // Triad: data-channel-action (WHAT) · data-channel-on (WHEN) · data-channel-target (WHERE)
  // Grammar: "signal [mod:value]…"  e.g. "input delay:200" · "swipe.horizontal threshold:48"
  // Values: closest form → Intent.form; named control value → form too.
  // Cap hashes data-channel-args only. Live field values must not join args.
  var signalState = null;
  var signalSuppressClick = false;
  var signalInFlight = Object.create(null);
  var signalDebounceTimers = Object.create(null);
  var signalThrottleAt = Object.create(null);
  var SIGNAL_SWIPE_THRESHOLD = 48;
  var SIGNAL_AXIS_LOCK = 10;
  var SIGNAL_MIN_VELOCITY = 0.35;
  var SIGNAL_COOLDOWN_MS = 280;
  var SIGNAL_LONGPRESS_MS = 520;
  var SIGNAL_DEBOUNCE_MS = 180;
  var SIGNAL_LEAF = {
    "click": 1, "change": 1, "input": 1, "blur": 1, "longpress": 1,
    "swipe.left": 1, "swipe.right": 1, "swipe.up": 1, "swipe.down": 1
  };

  function parseDuration(v) {
    if (v == null || v === "") return null;
    var s = String(v).toLowerCase().replace(/\s+/g, "");
    var m = s.match(/^(\d+(?:\.\d+)?)(ms|s)?$/);
    if (!m) {
      var n0 = parseInt(s, 10);
      return isFinite(n0) ? n0 : null;
    }
    var num = parseFloat(m[1]);
    if (m[2] === "s") num *= 1000;
    return isFinite(num) ? Math.round(num) : null;
  }

  function parseOnSpec(raw) {
    var spec = { signals: {}, order: [], off: false };
    if (raw == null || raw === "") return null;
    var parts = String(raw).split(/\s+/);
    var current = null;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].replace(/^\s+|\s+$/g, "").toLowerCase();
      if (!p) continue;
      if (p === "none" || p === "off") { spec.off = true; continue; }
      var colon = p.indexOf(":");
      if (colon > 0) {
        var key = p.slice(0, colon);
        var val = p.slice(colon + 1);
        if (!current) continue;
        if (!spec.signals[current]) { spec.signals[current] = {}; spec.order.push(current); }
        if (key === "delay" || key === "debounce") {
          var d = parseDuration(val);
          if (d != null) spec.signals[current].delay = d;
        } else if (key === "threshold") {
          var th = parseDuration(val);
          if (th != null) spec.signals[current].threshold = th;
        } else if (key === "throttle") {
          var th2 = parseDuration(val);
          if (th2 != null) spec.signals[current].throttle = th2;
        } else if (key === "once" && (val === "1" || val === "true" || val === "yes")) {
          spec.signals[current].once = true;
        }
        continue;
      }
      if (p === "once" && current) {
        if (!spec.signals[current]) { spec.signals[current] = {}; spec.order.push(current); }
        spec.signals[current].once = true;
        continue;
      }
      current = p;
      if (!spec.signals[current]) { spec.signals[current] = {}; spec.order.push(current); }
    }
    return spec;
  }

  function ownOnSpec(el) {
    return el && el.getAttribute ? parseOnSpec(el.getAttribute("data-channel-on")) : null;
  }

  function effectiveOnSpec(el) {
    var own = ownOnSpec(el);
    if (own && own.off) return { signals: {}, order: [], off: true };
    var inherited = null;
    var a = el.parentElement;
    while (a && a !== document.body && a !== document.documentElement) {
      var s = ownOnSpec(a);
      if (s) {
        if (s.off) break;
        var leafOnly = { signals: {}, order: [], off: false };
        for (var i = 0; i < s.order.length; i++) {
          var n = s.order[i];
          if (SIGNAL_LEAF[n]) {
            leafOnly.signals[n] = Object.assign({}, s.signals[n]);
            leafOnly.order.push(n);
          }
        }
        if (leafOnly.order.length) { inherited = leafOnly; break; }
      }
      a = a.parentElement;
    }
    var merged = own || inherited;
    if (own && inherited) {
      merged = { signals: {}, order: own.order.slice(), off: own.off };
      var k;
      for (k in own.signals) merged.signals[k] = Object.assign({}, own.signals[k]);
      if (!own.off) {
        for (k in inherited.signals) {
          if (!merged.signals[k]) {
            merged.signals[k] = Object.assign({}, inherited.signals[k]);
            merged.order.push(k);
          }
        }
      }
    }
    if (!merged || (!merged.order.length && !merged.off)) {
      return { signals: { click: {} }, order: ["click"], off: false };
    }
    if (own && el.getAttribute && el.getAttribute("data-channel-action")) {
      var onlySynth = true;
      for (var j = 0; j < own.order.length; j++) {
        if (SIGNAL_LEAF[own.order[j]]) { onlySynth = false; break; }
      }
      if (onlySynth && !merged.signals.click) {
        merged.signals.click = {};
        merged.order.push("click");
      }
    }
    return merged;
  }

  function acceptsSignal(el, signal) {
    if (!el) return false;
    var spec = effectiveOnSpec(el);
    if (spec.off) return false;
    return !!spec.signals[signal];
  }

  function signalOpts(el, signal) {
    var spec = effectiveOnSpec(el);
    return (spec.signals && spec.signals[signal]) || {};
  }

  function effectiveTarget(el) {
    var a = el, t;
    while (a && a !== document.documentElement) {
      if (a.getAttribute) {
        t = a.getAttribute("data-channel-target");
        if (t) return t;
      }
      a = a.parentElement;
    }
    return undefined;
  }

  function isTypingSurface(el) {
    if (!el || el === document.body) return false;
    var tag = (el.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    return !!el.isContentEditable;
  }

  function isControlDisabled(el) {
    if (!el) return true;
    if (el.disabled) return true;
    if (el.getAttribute && el.getAttribute("aria-disabled") === "true") return true;
    if (el.closest) {
      var fs = el.closest("fieldset");
      if (fs && fs.disabled) return true;
    }
    return false;
  }

  function hostKey(el) {
    if (!el) return "anon";
    if (el.id) return "#" + el.id;
    return "el:" + (el.getAttribute && el.getAttribute("data-channel-id") || "");
  }

  function controlFromEl(el) {
    if (!el) return null;
    if (el.getAttribute && el.getAttribute("data-channel-action")) return el;
    if (el.querySelector) {
      var inner = el.querySelector("[data-channel-action]");
      if (inner) return inner;
    }
    return null;
  }

  function collectForm(el) {
    if (!el || !el.closest) return undefined;
    var form = el.tagName === "FORM" ? el : el.closest("form");
    if (!form) return undefined;
    try {
      var fd = new FormData(form);
      var formObj = {};
      fd.forEach(function (v, k) {
        if (Object.prototype.hasOwnProperty.call(formObj, k)) {
          if (!Array.isArray(formObj[k])) formObj[k] = [formObj[k]];
          formObj[k].push(v);
        } else formObj[k] = v;
      });
      return formObj;
    } catch (eF) {
      return undefined;
    }
  }

  function fireControl(el, signal) {
    var ctrl = controlFromEl(el);
    if (!ctrl || isControlDisabled(ctrl)) return Promise.resolve();
    var action = ctrl.getAttribute("data-channel-action");
    if (!action) return Promise.resolve();
    var opts = signalOpts(ctrl, signal);
    var key = hostKey(ctrl) + "|" + action + "|" + (signal || "");
    if (opts.once && signalThrottleAt[key + "|once"]) return Promise.resolve();
    if (signalInFlight[key]) return Promise.resolve();
    var args = parseJSON(ctrl.getAttribute("data-channel-args"), {});
    var cap = ctrl.getAttribute("data-channel-cap") || undefined;
    var target = ctrl.getAttribute("data-channel-target") || effectiveTarget(ctrl) || undefined;
    var idem = ctrl.getAttribute("data-channel-idempotency") || undefined;
    var formObj = collectForm(ctrl);
    var tag = (ctrl.tagName || "").toLowerCase();
    if ((tag === "input" || tag === "textarea" || tag === "select") && ctrl.name) {
      formObj = Object.assign({}, formObj || {});
      if (formObj[ctrl.name] == null) formObj[ctrl.name] = ctrl.value;
    }
    signalInFlight[key] = true;
    if (opts.once) signalThrottleAt[key + "|once"] = 1;
    ctrl.setAttribute("aria-busy", "true");
    ctrl.classList.add("ux-busy");
    return runAction(action, args, cap, target, {
      idempotency_key: idem,
      form: formObj,
    })
      .catch(function (err) {
        console.error("[ux-channel] signal", signal, err);
        if (!err || !err.handled) safeToast(String(err.message || err), "error");
      })
      .finally(function () {
        ctrl.removeAttribute("aria-busy");
        ctrl.classList.remove("ux-busy");
        setTimeout(function () { delete signalInFlight[key]; }, SIGNAL_COOLDOWN_MS);
      });
  }

  function scheduleSignal(el, signal) {
    var ctrl = controlFromEl(el);
    if (!ctrl) return;
    var opts = signalOpts(ctrl, signal);
    var key = hostKey(ctrl) + "|" + signal;
    var now = typeof performance !== "undefined" ? performance.now() : Date.now();
    if (opts.throttle != null) {
      var last = signalThrottleAt[key] || 0;
      if (now - last < opts.throttle) return;
      signalThrottleAt[key] = now;
      fireControl(ctrl, signal);
      return;
    }
    var delay = opts.delay;
    if (delay == null && (signal === "input" || signal === "change")) delay = SIGNAL_DEBOUNCE_MS;
    if (delay == null || delay <= 0) {
      fireControl(ctrl, signal);
      return;
    }
    if (signalDebounceTimers[key]) clearTimeout(signalDebounceTimers[key]);
    signalDebounceTimers[key] = setTimeout(function () {
      delete signalDebounceTimers[key];
      fireControl(ctrl, signal);
    }, delay);
  }

  function conventionSuffix(signal) {
    if (signal === "swipe.left" || signal === "swipe.up") return "next";
    if (signal === "swipe.right" || signal === "swipe.down") return "prev";
    return null;
  }

  function matchConvention(root, signal) {
    var suffix = conventionSuffix(signal);
    if (!suffix || !root || !root.querySelectorAll) return null;
    var nodes = root.querySelectorAll("[data-channel-action]");
    var end = "." + suffix;
    for (var i = 0; i < nodes.length; i++) {
      if (isControlDisabled(nodes[i])) continue;
      var a = nodes[i].getAttribute("data-channel-action") || "";
      if (a === suffix || a.slice(-end.length) === end) return nodes[i];
    }
    return null;
  }

  function resolveSignalTarget(host, signal, clientX, clientY) {
    var i, el, ctrl, stack = [];
    if (typeof document.elementsFromPoint === "function" && clientX != null && clientY != null) {
      try { stack = document.elementsFromPoint(clientX, clientY) || []; }
      catch (ePt) { stack = []; }
    }
    for (i = 0; i < stack.length; i++) {
      el = stack[i];
      ctrl = el.closest ? el.closest("[data-channel-action]") : null;
      if (ctrl && !isControlDisabled(ctrl) && acceptsSignal(ctrl, signal)) return ctrl;
    }
    if (host && host.querySelectorAll) {
      var nodes = host.querySelectorAll("[data-channel-action]");
      for (i = 0; i < nodes.length; i++) {
        if (isControlDisabled(nodes[i])) continue;
        var own = ownOnSpec(nodes[i]);
        if (own && own.signals[signal] && SIGNAL_LEAF[signal]) return nodes[i];
      }
      for (i = 0; i < nodes.length; i++) {
        if (!isControlDisabled(nodes[i]) && acceptsSignal(nodes[i], signal)) return nodes[i];
      }
      ctrl = matchConvention(host, signal);
      if (ctrl) return ctrl;
      var root = host.id ? host : (host.closest && host.closest("[id]"));
      if (root && root !== host) {
        ctrl = matchConvention(root, signal);
        if (ctrl) return ctrl;
      }
    }
    return null;
  }

  function emitSignal(host, signal, clientX, clientY) {
    var target = resolveSignalTarget(host, signal, clientX, clientY);
    if (!target) return Promise.resolve();
    return fireControl(target, signal);
  }

  function synthThreshold(host, axisToken) {
    var a = host;
    while (a && a !== document.documentElement) {
      var spec = ownOnSpec(a);
      if (spec) {
        for (var i = 0; i < spec.order.length; i++) {
          var n = spec.order[i];
          if (axisToken === "horizontal" && (n === "swipe.horizontal" || n === "swipe.x") &&
              spec.signals[n] && spec.signals[n].threshold != null)
            return spec.signals[n].threshold;
          if (axisToken === "vertical" && (n === "swipe.vertical" || n === "swipe.y") &&
              spec.signals[n] && spec.signals[n].threshold != null)
            return spec.signals[n].threshold;
        }
      }
      a = a.parentElement;
    }
    return SIGNAL_SWIPE_THRESHOLD;
  }

  function findSwipeHost(start) {
    var el = start;
    while (el && el !== document.body && el !== document.documentElement) {
      var spec = ownOnSpec(el);
      if (spec) {
        for (var i = 0; i < spec.order.length; i++) {
          var n = spec.order[i];
          if (n === "swipe.horizontal" || n === "swipe.x")
            return { host: el, axis: "horizontal" };
          if (n === "swipe.vertical" || n === "swipe.y")
            return { host: el, axis: "vertical" };
        }
      }
      el = el.parentElement;
    }
    return null;
  }

  function clearLongTimer(st) {
    if (st && st.longTimer) { clearTimeout(st.longTimer); st.longTimer = null; }
  }

  function onPointerDown(ev) {
    if (ev.isPrimary === false) return;
    if (ev.pointerType === "mouse" && ev.button !== 0) return;
    if (isTypingSurface(ev.target)) return;
    var found = findSwipeHost(ev.target);
    var longEl = ev.target.closest && ev.target.closest("[data-channel-action]");
    if (longEl && (isControlDisabled(longEl) || !acceptsSignal(longEl, "longpress"))) longEl = null;
    if (!found && !longEl) return;
    var axis = found ? found.axis : null;
    var host = found ? found.host : longEl;
    if (axis) {
      try {
        if (host.style && !host.style.touchAction)
          host.style.touchAction = axis === "vertical" ? "pan-x" : "pan-y";
      } catch (eTA) {}
    }
    signalState = {
      host: host, axis: axis, id: ev.pointerId,
      x0: ev.clientX, y0: ev.clientY,
      t0: typeof performance !== "undefined" ? performance.now() : Date.now(),
      thr: found ? synthThreshold(host, axis) : SIGNAL_SWIPE_THRESHOLD,
      locked: null, dead: false, longEl: longEl, longTimer: null
    };
    if (longEl) {
      var lp = signalOpts(longEl, "longpress").delay;
      if (lp == null) lp = SIGNAL_LONGPRESS_MS;
      signalState.longTimer = setTimeout(function () {
        if (!signalState || signalState.id !== ev.pointerId || signalState.dead) return;
        signalState.dead = true;
        signalSuppressClick = true;
        setTimeout(function () { signalSuppressClick = false; }, 360);
        var el = signalState.longEl;
        signalState = null;
        fireControl(el, "longpress");
      }, lp);
    }
    try { if (host && host.setPointerCapture) host.setPointerCapture(ev.pointerId); } catch (eCap) {}
  }

  function onPointerMove(ev) {
    if (!signalState || signalState.id !== ev.pointerId || signalState.dead) return;
    var st = signalState;
    var dx = ev.clientX - st.x0, dy = ev.clientY - st.y0;
    if (Math.abs(dx) > 6 || Math.abs(dy) > 6) clearLongTimer(st);
    if (!st.axis) return;
    if (!st.locked) {
      if (Math.abs(dx) < SIGNAL_AXIS_LOCK && Math.abs(dy) < SIGNAL_AXIS_LOCK) return;
      st.locked = Math.abs(dx) >= Math.abs(dy) ? "horizontal" : "vertical";
      if (st.locked !== st.axis) {
        st.dead = true;
        clearLongTimer(st);
        try { st.host && st.host.releasePointerCapture && st.host.releasePointerCapture(ev.pointerId); } catch (eRel) {}
        if (st.host && st.host.classList) st.host.classList.remove("ux-signal-active");
        signalState = null;
        return;
      }
      if (st.host && st.host.classList) st.host.classList.add("ux-signal-active");
    }
  }

  function commitSwipeSignal(st, dx, dy, dt) {
    var primary = st.axis === "vertical" ? dy : dx;
    var abs = Math.abs(primary);
    var velocity = dt > 0 ? abs / dt : 0;
    if (abs < st.thr && velocity < SIGNAL_MIN_VELOCITY) return null;
    if (st.axis === "vertical") return primary < 0 ? "swipe.up" : "swipe.down";
    return primary < 0 ? "swipe.left" : "swipe.right";
  }

  function onPointerUp(ev) {
    if (!signalState || signalState.id !== ev.pointerId) return;
    var st = signalState;
    signalState = null;
    clearLongTimer(st);
    if (st.host && st.host.classList) st.host.classList.remove("ux-signal-active");
    if (st.dead || !st.axis) return;
    var dx = ev.clientX - st.x0, dy = ev.clientY - st.y0;
    if (!st.locked) {
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
      st.locked = Math.abs(dx) >= Math.abs(dy) ? "horizontal" : "vertical";
      if (st.locked !== st.axis) return;
    }
    var t1 = typeof performance !== "undefined" ? performance.now() : Date.now();
    var signal = commitSwipeSignal(st, dx, dy, Math.max(1, t1 - st.t0));
    if (!signal) return;
    signalSuppressClick = true;
    setTimeout(function () { signalSuppressClick = false; }, 360);
    emitSignal(st.host, signal, ev.clientX, ev.clientY);
  }

  function onPointerCancel(ev) {
    if (!signalState || signalState.id !== ev.pointerId) return;
    clearLongTimer(signalState);
    if (signalState.host && signalState.host.classList)
      signalState.host.classList.remove("ux-signal-active");
    signalState = null;
  }

  function onFieldSignal(ev, signal) {
    var el = ev.target;
    if (!el || !el.closest) return;
    var ctrl = el.closest("[data-channel-action]");
    if (!ctrl || isControlDisabled(ctrl)) return;
    if (!acceptsSignal(ctrl, signal)) return;
    scheduleSignal(ctrl, signal);
  }
  function onInput(ev) { onFieldSignal(ev, "input"); }
  function onChange(ev) { onFieldSignal(ev, "change"); }
  function onBlur(ev) { onFieldSignal(ev, "blur"); }

  function onClick(ev) {
    if (signalSuppressClick) {
      ev.preventDefault();
      ev.stopPropagation();
      return;
    }
    var el = ev.target.closest("[data-channel-action]");
    if (!el || el.tagName === "FORM") return;
    if (isControlDisabled(el)) return;
    if (!acceptsSignal(el, "click")) return;
    ev.preventDefault();
    fireControl(el, "click");
  }

  function onSubmit(ev) {
    var form = ev.target;
    if (!form || form.tagName !== "FORM") return;
    var action = form.getAttribute("data-channel-action");
    if (!action) return;
    ev.preventDefault();
    var args = parseJSON(form.getAttribute("data-channel-args"), {});
    var cap = form.getAttribute("data-channel-cap") || undefined;
    var target = form.getAttribute("data-channel-target") || effectiveTarget(form) || undefined;
    var fd = new FormData(form);
    var formObj = {};
    fd.forEach(function (v, k) {
      if (Object.prototype.hasOwnProperty.call(formObj, k)) {
        if (!Array.isArray(formObj[k])) formObj[k] = [formObj[k]];
        formObj[k].push(v);
      } else formObj[k] = v;
    });
    var intent = {
      v: "1",
      action: action,
      args: args,
      form: formObj,
      cap: cap,
      target: target,
      request_id: requestId(),
      idempotency_key: form.getAttribute("data-channel-idempotency") || undefined,
    };
    attachHello(intent);
    form.setAttribute("aria-busy", "true");
    enqueue(function () { return postIntent(intent); })
      .catch(function (err) {
        console.error("[ux-channel]", err);
        if (!err || !err.handled) safeToast(String(err.message || err), "error");
      })
      .finally(function () { form.removeAttribute("aria-busy"); });
  }


  // --- Server push (SSE) -------------------------------------------------
  // Server: GET {path}/push/{topic}  →  Result JSON lines
  // Browser default: EventSource → applyResult (same ops as POST /action)
  //
  // Declarative (preferred):
  //   <body data-channel-endpoint="/ux-channel/action"
  //         data-channel-push-topic="live.board"
  //         data-channel-push-token="…">   <!-- optional -->
  //
  // Programmatic:
  //   uxChannel.subscribePush("live.board")
  //   uxChannel.subscribePush({ topic: "t", token: "…", onEvent: fn })
  //   uxChannel.unsubscribePush("live.board")

  var PUSH_TOPIC_ATTR = "data-channel-push-topic";
  var PUSH_URL_ATTR = "data-channel-push";
  var PUSH_TOKEN_ATTR = "data-channel-push-token";
  var PUSH_TICKET_ATTR = "data-channel-push-ticket";
  var pushSubs = Object.create(null); // key → { es, topic, url }

  function channelBasePath() {
    // Derive /ux-channel from endpoint /ux-channel/action
    var ep = endpoint();
    if (ep.indexOf("/action") !== -1) {
      return ep.replace(/\/?action\/?$/, "") || "/ux-channel";
    }
    // fallback: strip last segment
    var i = ep.lastIndexOf("/");
    return i > 0 ? ep.slice(0, i) : "/ux-channel";
  }

  function pushUrlFor(topic, token, ticket) {
    var base = channelBasePath().replace(/\/$/, "");
    var url = base + "/push/" + encodeURIComponent(topic);
    var q = [];
    if (token) q.push("token=" + encodeURIComponent(token));
    if (ticket) q.push("ticket=" + encodeURIComponent(ticket));
    if (q.length) url += "?" + q.join("&");
    return url;
  }

  function subscribePush(topicOrOpts, maybeOpts) {
    if (typeof EventSource === "undefined") {
      if (isDev()) console.warn("[ux-channel] EventSource missing — push disabled");
      return null;
    }
    var opts = {};
    var topic = null;
    var url = null;
    if (typeof topicOrOpts === "string") {
      // topic or absolute/relative URL
      if (topicOrOpts.indexOf("/push/") !== -1 || topicOrOpts.indexOf("://") !== -1) {
        url = topicOrOpts;
        var m = topicOrOpts.match(/\/push\/([^/?#]+)/);
        topic = m ? decodeURIComponent(m[1]) : topicOrOpts;
      } else {
        topic = topicOrOpts;
      }
      opts = maybeOpts || {};
    } else if (topicOrOpts && typeof topicOrOpts === "object") {
      opts = topicOrOpts;
      topic = opts.topic || null;
      url = opts.url || null;
    }
    if (!topic && !url) {
      if (isDev()) console.warn("[ux-channel] subscribePush requires topic or url");
      return null;
    }
    var token = opts.token || (document.body && document.body.getAttribute(PUSH_TOKEN_ATTR)) || null;
    var ticket = opts.ticket || (document.body && document.body.getAttribute(PUSH_TICKET_ATTR)) || null;
    if (!url) url = pushUrlFor(topic, token, ticket);
    else {
      if (token && url.indexOf("token=") === -1) {
        url += (url.indexOf("?") >= 0 ? "&" : "?") + "token=" + encodeURIComponent(token);
      }
      if (ticket && url.indexOf("ticket=") === -1) {
        url += (url.indexOf("?") >= 0 ? "&" : "?") + "ticket=" + encodeURIComponent(ticket);
      }
    }
    var key = topic || url;
    // replace existing
    if (pushSubs[key] && pushSubs[key].es) {
      try { pushSubs[key].es.close(); } catch (e) {}
    }
    var es = new EventSource(url);
    var sub = { es: es, topic: topic, url: url };
    pushSubs[key] = sub;

    es.onmessage = function (ev) {
      if (!ev.data) return;
      // ignore SSE comment keepalives (browser usually doesn't fire these)
      var result;
      try { result = JSON.parse(ev.data); }
      catch (e) {
        if (isDev()) console.warn("[ux-channel] push bad JSON", e);
        emitChannel("channel:pushError", { topic: topic, url: url, reason: "bad_json", error: e });
        return;
      }
      // Reject non-Result payloads (avoid applying garbage)
      if (!result || (typeof result.ok === "undefined" && !result.ops && !result.error)) {
        if (isDev()) console.warn("[ux-channel] push non-result payload", result);
        return;
      }
      if (typeof opts.onEvent === "function") {
        try { opts.onEvent(result, ev); } catch (e2) { console.error(e2); }
      }
      applyResult(result, { source: "sse" }).then(function () {
        if (typeof opts.onApplied === "function") {
          try { opts.onApplied(result); } catch (e3) { console.error(e3); }
        }
        emitChannel("channel:push", { topic: topic, result: result });
      }).catch(function (err) {
        emitChannel("channel:pushError", { topic: topic, url: url, reason: "apply", error: err });
      });
    };
    es.onerror = function () {
      // EventSource auto-reconnects; surface for app health UIs
      if (isDev()) console.warn("[ux-channel] push SSE error (will reconnect)", url, es.readyState);
      emitChannel("channel:pushError", {
        topic: topic,
        url: url,
        reason: "transport",
        readyState: es.readyState,
      });
      if (typeof opts.onError === "function") {
        try { opts.onError(es); } catch (e) {}
      }
    };
    if (isDev()) console.info("[ux-channel] push subscribed", url);
    return sub;
  }

  function unsubscribePush(topicOrKey) {
    var key = topicOrKey || "";
    var sub = pushSubs[key];
    if (!sub) {
      // try match by topic
      for (var k in pushSubs) {
        if (pushSubs[k] && pushSubs[k].topic === topicOrKey) { sub = pushSubs[k]; key = k; break; }
      }
    }
    if (sub && sub.es) {
      try { sub.es.close(); } catch (e) {}
      delete pushSubs[key];
      return true;
    }
    return false;
  }


  // --- WebSocket (optional duplex) ---------------------------------------
  var WS_ATTR = "data-channel-ws";
  var wsHandle = null;
  var lastWsBaseUrl = null;       // URL without query (reconnect rebuild)
  var lastWsCreds = { token: null, ticket: null };
  var wsTopics = {};              // topic -> true (dynamic + body topics)
  var wsMessageHooks = [];
  var wsReconnectAttempt = 0;
  var wsReconnectTimer = null;
  var wsShouldReconnect = true;
  var wsManualClose = false;

  function _wsTopicList() {
    var out = [];
    for (var k in wsTopics) {
      if (Object.prototype.hasOwnProperty.call(wsTopics, k) && wsTopics[k]) out.push(k);
    }
    return out;
  }

  function _rememberTopics(topics) {
    if (!topics) return;
    var parts = Array.isArray(topics) ? topics : String(topics).split(",");
    for (var i = 0; i < parts.length; i++) {
      var t = String(parts[i]).replace(/^\s+|\s+$/g, "");
      if (t) wsTopics[t] = true;
    }
  }

  function _buildWsUrl(base, creds, topicsCsv) {
    var url = base;
    var q = [];
    if (creds && creds.token) q.push("token=" + encodeURIComponent(creds.token));
    if (creds && creds.ticket) q.push("ticket=" + encodeURIComponent(creds.ticket));
    if (topicsCsv) q.push("topics=" + encodeURIComponent(topicsCsv));
    if (q.length) url += (url.indexOf("?") >= 0 ? "&" : "?") + q.join("&");
    return url;
  }

  function subscribeWs(urlOrOpts, maybeOpts) {
    if (typeof WebSocket === "undefined") {
      if (isDev()) console.warn("[ux-channel] WebSocket missing");
      return null;
    }
    var opts = {};
    var url = null;
    if (typeof urlOrOpts === "string") {
      // If full URL with query is passed (reconnect with query), strip query for base
      url = urlOrOpts;
      opts = maybeOpts || {};
      if (url.indexOf("?") >= 0 && !opts._reconnect) {
        // treat as base if no opts.topics — keep query as-is only when reconnecting
      }
    } else if (urlOrOpts && typeof urlOrOpts === "object") {
      opts = urlOrOpts;
      url = opts.url;
    }
    if (!url && document.body) url = document.body.getAttribute(WS_ATTR);
    if (!url) {
      var base = channelBasePath().replace(/\/$/, "");
      url = (location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + base + "/ws";
    }
    // relative /ux-channel/ws → absolute
    if (url.charAt(0) === "/") {
      url = (location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + url;
    }
    // Strip existing query into base (avoid double-append on reconnect)
    var baseUrl = url;
    var qi = baseUrl.indexOf("?");
    if (qi >= 0) baseUrl = baseUrl.slice(0, qi);

    var token = opts.token != null ? opts.token : (document.body && document.body.getAttribute(PUSH_TOKEN_ATTR)) || null;
    var ticket = opts.ticket != null ? opts.ticket : (document.body && document.body.getAttribute(PUSH_TICKET_ATTR)) || null;
    var topics = opts.topics || (document.body && document.body.getAttribute(PUSH_TOPIC_ATTR)) || null;
    _rememberTopics(topics);
    // also remember any topics already tracked for reconnect
    lastWsBaseUrl = baseUrl;
    lastWsCreds = { token: token, ticket: ticket };
    var topicsCsv = _wsTopicList().join(",");
    var fullUrl = _buildWsUrl(baseUrl, lastWsCreds, topicsCsv || null);

    if (wsHandle && lastWsBaseUrl === baseUrl && (wsHandle.readyState === 0 || wsHandle.readyState === 1)) {
      return {
        ws: wsHandle,
        send: function (obj) { if (wsHandle.readyState === 1) wsHandle.send(JSON.stringify(obj)); },
        subscribe: function (topic) {
          _rememberTopics(topic);
          if (wsHandle.readyState === 1) wsHandle.send(JSON.stringify({ type: "subscribe", topic: topic }));
        },
        close: function () { wsManualClose = true; wsShouldReconnect = false; wsHandle.close(); },
      };
    }
    if (wsHandle) {
      try { wsManualClose = true; wsHandle.close(); } catch (e) {}
      wsManualClose = false;
    }
    wsShouldReconnect = true;
    var ws = new WebSocket(fullUrl);
    wsHandle = ws;
    ws.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (!msg || !msg.type) return;
      if (msg.type === "result") {
        applyResult(msg, { source: "ws" }).catch(function (err) {
          emitChannel("channel:wsError", { reason: "apply", error: err });
        });
      } else if (msg.type === "error") {
        reportError("transport", {
          message: msg.message || msg.code || "WebSocket error",
          code: msg.code || "ws_error",
          error: { code: msg.code, message: msg.message },
          result: { ok: false, ops: [], error: { code: msg.code, message: msg.message } },
          source: "ws",
          toast: true,
        });
        emitChannel("channel:wsError", { reason: "protocol", code: msg.code, message: msg.message });
        if (isDev()) console.warn("[ux-channel] ws error", msg.code, msg.message);
      } else if (msg.type === "ping") {
        try { ws.send(JSON.stringify({ type: "pong" })); } catch (e2) {}
      } else if (msg.type === "subscribed" && msg.topic) {
        _rememberTopics(msg.topic);
      }
      if (typeof opts.onMessage === "function") {
        try { opts.onMessage(msg); } catch (e3) {}
      }
      for (var hi = 0; hi < wsMessageHooks.length; hi++) {
        try { wsMessageHooks[hi](msg); } catch (e4) {}
      }
    };
    ws.onerror = function () {
      if (isDev()) console.warn("[ux-channel] websocket error");
      emitChannel("channel:wsError", { reason: "transport" });
    };
    ws.onclose = function () {
      wsHandle = null;
      if (wsManualClose || !wsShouldReconnect || !lastWsBaseUrl) return;
      var delay = Math.min(30000, 500 * Math.pow(2, wsReconnectAttempt++));
      if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
      wsReconnectTimer = setTimeout(function () {
        try {
          subscribeWs({
            url: lastWsBaseUrl,
            token: lastWsCreds.token,
            ticket: lastWsCreds.ticket,
            topics: _wsTopicList().join(","),
            _reconnect: true,
          });
        } catch (e) {}
      }, delay);
    };
    ws.onopen = function () {
      wsReconnectAttempt = 0;
      // Re-subscribe every tracked topic via protocol (covers dynamic subs after connect)
      var list = _wsTopicList();
      for (var i = 0; i < list.length; i++) {
        try { ws.send(JSON.stringify({ type: "subscribe", topic: list[i] })); } catch (e) {}
      }
    };
    return {
      ws: ws,
      send: function (obj) { if (ws.readyState === 1) ws.send(JSON.stringify(obj)); },
      subscribe: function (topic) {
        _rememberTopics(topic);
        if (ws.readyState === 1) ws.send(JSON.stringify({ type: "subscribe", topic: topic }));
      },
      close: function () { wsManualClose = true; wsShouldReconnect = false; ws.close(); },
    };
  }

  /** Register a listener without opening a second socket (autoSubscribeWs owns connect). */
  function onWsMessage(fn) {
    if (typeof fn === "function") wsMessageHooks.push(fn);
    return function off() {
      wsMessageHooks = wsMessageHooks.filter(function (f) { return f !== fn; });
    };
  }

  function autoSubscribeWs() {
    if (!document.body || !document.body.hasAttribute(WS_ATTR)) return;
    subscribeWs();
  }

  function autoSubscribePush() {
    var body = document.body;
    if (!body) return;
    // Prefer a single live transport: when data-channel-ws is set, WS owns Results.
    // (SSE + WS both applying the same morphs races and doubles traffic.)
    if (body.hasAttribute(WS_ATTR)) return;
    // multi: data-channel-push-topic="a,b" or single
    var topics = body.getAttribute(PUSH_TOPIC_ATTR);
    var explicitUrl = body.getAttribute(PUSH_URL_ATTR);
    var token = body.getAttribute(PUSH_TOKEN_ATTR) || undefined;
    var ticket = body.getAttribute(PUSH_TICKET_ATTR) || undefined;
    if (explicitUrl) {
      subscribePush(explicitUrl, { token: token, ticket: ticket });
    }
    if (topics) {
      topics.split(",").forEach(function (t) {
        t = t.replace(/^\s+|\s+$/g, "");
        if (t) subscribePush(t, { token: token, ticket: ticket });
      });
    }
  }

  function scanBridges() {
    if (global.uxBridge && typeof global.uxBridge.scan === "function") {
      try { global.uxBridge.scan(document); } catch (eS) {}
    }
  }

  function init() {
    document.addEventListener("click", onClick);
    document.addEventListener("submit", onSubmit);
    document.addEventListener("pointerdown", onPointerDown, { passive: true });
    document.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerup", onPointerUp, { passive: true });
    document.addEventListener("pointercancel", onPointerCancel, { passive: true });
    document.addEventListener("input", onInput, true);
    document.addEventListener("change", onChange, true);
    document.addEventListener("blur", onBlur, true);
    // Adapters (ux-fx / ux-ui) often load *after* this file (defer order).
    // Scan now + after microtasks/ticks so late register() still mounts hosts.
    scanBridges();
    try {
      if (typeof queueMicrotask === "function") queueMicrotask(scanBridges);
    } catch (eM) {}
    setTimeout(scanBridges, 0);
    setTimeout(scanBridges, 50);
    autoSubscribePush();
    autoSubscribeWs();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  /** Subscribe to document-level channel events (returns off()). */
  function on(eventName, fn) {
    if (typeof fn !== "function") return function () {};
    var h = function (ev) { fn(ev.detail, ev); };
    document.addEventListener(eventName, h);
    return function off() { document.removeEventListener(eventName, h); };
  }

  global.uxChannel = {
    runAction: runAction,
    applyResult: applyResult,
    postIntent: postIntent,
    peerHello: peerHello,
    subscribePush: subscribePush,
    unsubscribePush: unsubscribePush,
    subscribeWs: subscribeWs,
    onWsMessage: onWsMessage,
    on: on,
    reportError: reportError,
    configure: configureErrors,
    lastErrors: lastErrors,
    clearErrorLog: clearErrorLog,
    applyFieldErrors: applyFieldErrors,
    clearFieldErrors: clearFieldErrors,
    getWs: function () { return wsHandle; },
    signals: signals,
    version: VERSION,
    reaperBridges: reaperBridges,
    optimisticMorph: function (uid, html) {
      var sel = '[data-channel-id="' + uid + '"]';
      var el = document.querySelector(sel);
      if (!el) return null;
      var prev = el.outerHTML;
      applyMorph(sel, html);
      return function rollback() { applyMorph(sel, prev); };
    },
  };

  function bootClient() {
    readErrorConfigFromDom();
    try { hydrateSignalsFromStorage(); } catch (eH) {}
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", bootClient);
    } else {
      bootClient();
    }
  }

})(typeof window !== "undefined" ? window : globalThis);
