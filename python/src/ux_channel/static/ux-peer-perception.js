/**
 * ux-peer-perception.js — Peer IR: perception-only layer (Wave C)
 *
 * SEPARATE from ux-peer-kernel.js on purpose.
 * Authority apply stays in the kernel. This module only does:
 *   coalesce · shadow morph · pending/busy · filter_cached · toast_fade
 *
 * Hard rules:
 *   - Never mint Caps
 *   - Never enlarge authority state the next Cap would reject
 *   - On real Result: clearShadows() then kernel.applyResult()
 *
 * Usage:
 *   <script src="ux-peer-kernel.js"></script>
 *   <script src="ux-peer-perception.js"></script>
 *   var kernel = uxcPeer.createPeerKernel({ drivers: uxcPeer.makeWebDrivers() });
 *   var perc = uxcPerception.attach(kernel, { coalesceMs: 120 });
 */
(function (global) {
  "use strict";

  function attach(kernel, options) {
    options = options || {};
    var coalesceMs = options.coalesceMs == null ? 120 : Math.max(0, Number(options.coalesceMs));
    var applyShadow = options.applyShadow || function () {};
    var clearShadowDom = options.clearShadowDom || function () {};
    var setPending = options.setPending || function () {};
    var onCoalescedIntent = options.onCoalescedIntent || null;

    var shadows = Object.create(null);
    var pending = Object.create(null);
    var lastAppliedHash = Object.create(null);
    var coalesceTimers = Object.create(null);
    var coalesceBuckets = Object.create(null);
    var toastTimers = Object.create(null);
    var log = [];

    function hash(s) {
      var h = 2166136261;
      var str = String(s == null ? "" : s);
      for (var i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return (h >>> 0).toString(16);
    }

    function shadowMorph(target, html) {
      if (!target) return;
      shadows[target] = { html: html, at: Date.now() };
      try { applyShadow(target, html); } catch (e) { log.push(["shadow_err", target, String(e)]); }
      log.push(["shadow", target]);
    }

    function clearShadows(targets) {
      var keys = targets || Object.keys(shadows);
      for (var i = 0; i < keys.length; i++) {
        var t = keys[i];
        if (shadows[t]) {
          try { clearShadowDom(t); } catch (e) {}
          delete shadows[t];
          log.push(["shadow_clear", t]);
        }
      }
    }

    function setPendingState(target, isPending) {
      if (!target) return;
      if (isPending) pending[target] = true;
      else delete pending[target];
      try { setPending(target, !!isPending); } catch (e) {}
      log.push(["pending", target, !!isPending]);
    }

    function filterCached(ops) {
      if (!ops || !ops.length) return ops || [];
      var out = [];
      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        if (!op || !op.op) continue;
        if (op.op === "morph" || op.op === "swap" || op.op === "set_text") {
          var t = op.target;
          var body = op.html != null ? op.html : op.text;
          var h = hash(body);
          if (t && lastAppliedHash[t] === h) {
            log.push(["filter_cached", t, op.op]);
            continue;
          }
          if (t) lastAppliedHash[t] = h;
        }
        out.push(op);
      }
      return out;
    }

    function coalesceIntent(key, intent, submitFn) {
      if (!key) {
        if (submitFn) submitFn(intent);
        return;
      }
      coalesceBuckets[key] = intent;
      if (coalesceTimers[key]) clearTimeout(coalesceTimers[key]);
      coalesceTimers[key] = setTimeout(function () {
        var latest = coalesceBuckets[key];
        delete coalesceBuckets[key];
        delete coalesceTimers[key];
        log.push(["coalesce_flush", key]);
        var fn = submitFn || onCoalescedIntent;
        if (fn && latest) fn(latest);
      }, coalesceMs);
      log.push(["coalesce_arm", key, coalesceMs]);
    }

    function cancelCoalesce(key) {
      if (coalesceTimers[key]) {
        clearTimeout(coalesceTimers[key]);
        delete coalesceTimers[key];
      }
      delete coalesceBuckets[key];
    }

    function toastFade(id, ms, removeFn) {
      ms = Math.max(0, Number(ms) || 3000);
      if (toastTimers[id]) clearTimeout(toastTimers[id]);
      toastTimers[id] = setTimeout(function () {
        delete toastTimers[id];
        if (removeFn) {
          try { removeFn(id); } catch (e) {}
        }
        log.push(["toast_fade", id]);
      }, ms);
    }

    var rawApplyResult = kernel.applyResult.bind(kernel);
    var rawOnResult = kernel.onResult ? kernel.onResult.bind(kernel) : null;

    function applyAuthorityResult(result) {
      clearShadows();
      var pendKeys = Object.keys(pending);
      for (var i = 0; i < pendKeys.length; i++) setPendingState(pendKeys[i], false);
      var filtered = result;
      if (result && Array.isArray(result.ops)) {
        filtered = Object.assign({}, result, { ops: filterCached(result.ops) });
      }
      return rawApplyResult(filtered);
    }

    kernel.applyResult = applyAuthorityResult;
    if (rawOnResult) {
      kernel.onResult = function (result) {
        return applyAuthorityResult(result);
      };
    }

    var rawBump = kernel.bumpGen ? kernel.bumpGen.bind(kernel) : null;
    if (rawBump) {
      kernel.bumpGen = function () {
        clearShadows();
        pending = Object.create(null);
        lastAppliedHash = Object.create(null);
        Object.keys(coalesceTimers).forEach(cancelCoalesce);
        return rawBump();
      };
    }

    var rawHello = kernel.hello ? kernel.hello.bind(kernel) : null;
    if (rawHello) {
      kernel.hello = function () {
        var h = rawHello() || {};
        var feats = (h.features || []).slice();
        if (feats.indexOf("perception.v1") < 0) feats.push("perception.v1");
        if (feats.indexOf("continuations") < 0) feats.push("continuations");
        h.features = feats;
        h.surfaces = h.surfaces || [
          "dom.morph", "dom.toast", "dom.swap", "dom.set_text",
          "nav.navigate", "signal.set", "timer.set", "delta.patch", "delta.signal"
        ];
        return h;
      };
    }

    return {
      shadowMorph: shadowMorph,
      clearShadows: clearShadows,
      setPending: setPendingState,
      filterCached: filterCached,
      coalesceIntent: coalesceIntent,
      cancelCoalesce: cancelCoalesce,
      toastFade: toastFade,
      get shadows() { return Object.assign({}, shadows); },
      get pending() { return Object.assign({}, pending); },
      get log() { return log.slice(); },
      applyAuthorityResult: applyAuthorityResult,
      detach: function () {
        kernel.applyResult = rawApplyResult;
        if (rawOnResult) kernel.onResult = rawOnResult;
        if (rawBump) kernel.bumpGen = rawBump;
        if (rawHello) kernel.hello = rawHello;
        clearShadows();
        Object.keys(coalesceTimers).forEach(cancelCoalesce);
      },
    };
  }

  var api = { attach: attach, version: "perception.v1" };
  if (typeof global !== "undefined") global.uxcPerception = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
