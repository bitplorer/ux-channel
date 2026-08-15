/**
 * ux-channel peer kernel — no DOM.
 * Drivers (web.v1 / agent.v1) hold surface behavior.
 * SPEC: peer-kernel, seq, timer, invoke, queue, safeHref.
 *
 * ─────────────────────────────────────────────────────────────
 * EXTENSION (Wave C+) — perception is NOT in this file.
 *
 * Perception-only IR (coalesce, shadow, pending, filter_cached,
 * toast_fade) lives in **ux-peer-perception.js** and attaches via:
 *
 *   var kernel = uxcPeer.createPeerKernel({ drivers: ... });
 *   var perc   = uxcPerception.attach(kernel, { coalesceMs: 120 });
 *
 * Continuations (slot-fill) live in **ux-peer-continuations.js**:
 *
 *   var cont = uxcContinuations.create({ submitIntent: ... });
 *   cont.armFromResult(result);
 *   cont.handleEvent({ type: "timer.fired", detail: {...} });
 *
 * Do not merge perception into this kernel. Authority apply stays here.
 * ─────────────────────────────────────────────────────────────
 */
(function (global) {
  "use strict";

  function safeHref(href) {
    if (!href || typeof href !== "string") return null;
    var h = href.trim();
    if (!h || h.indexOf("//") === 0) return null;
    var path = h.split("?")[0].split("#")[0];
    if (path.indexOf(":") !== -1) {
      var scheme = path.split(":")[0].toLowerCase();
      if (["javascript", "data", "vbscript", "file"].indexOf(scheme) >= 0) return null;
      if (["http", "https", "mailto", "tel"].indexOf(scheme) < 0 && /^[a-z]+$/i.test(scheme))
        return null;
    }
    return h;
  }

  function createPeerKernel(options) {
    options = options || {};
    var drivers = options.drivers || {};
    var maxNodes = options.maxNodes || 256;
    var maxDepth = options.maxDepth || 16;
    var proofsRequired = !!options.proofsRequired;
    var proofVerify = options.proofVerify || null;
    var sessionId = options.sessionId || "default";
    var stampCheck = options.stampCheck || null;
    var gen = 1;
    var lock = false;
    var queue = [];
    var busy = false;
    var ctx = {
      gen: gen,
      log: [],
      timers: {},
      result_ok: true,
      session_id: sessionId,
      reject: null,
    };
    var hooks = { beforeApply: null, afterApply: null };

    function withinBudget(ops) {
      var count = 0;
      function walk(list, d) {
        if (d > maxDepth) return false;
        for (var i = 0; i < list.length; i++) {
          count++;
          if (count > maxNodes) return false;
          var op = list[i];
          if (op && Array.isArray(op.ops) && !walk(op.ops, d + 1)) return false;
        }
        return true;
      }
      return walk(ops || [], 0);
    }

    function applyOp(op) {
      if (!op || !op.op) return;
      if (op.op === "seq") {
        (op.ops || []).forEach(applyOp);
        return;
      }
      if (op.op === "invoke") {
        if (stampCheck && !stampCheck(op.ref, op.method)) {
          ctx.log.push(["invoke_denied", op.ref, op.method]);
          return;
        }
        var inv = drivers["invoke:" + op.method] || drivers["invoke"];
        if (inv) inv(op, ctx);
        (op.ops || []).forEach(applyOp);
        return;
      }
      var fn = drivers[op.op];
      if (fn) fn(op, ctx);
    }

    ctx.applyOp = applyOp;
    ctx.apply_ops = function (ops) {
      (ops || []).forEach(applyOp);
    };

    function applyResult(result) {
      ctx.reject = null;
      if (hooks.beforeApply) {
        try {
          var maybe = hooks.beforeApply(result);
          if (maybe && typeof maybe === "object") result = maybe;
        } catch (e) {
          ctx.log.push(["hook_before_err", String(e)]);
        }
      }
      if (proofsRequired) {
        if (!proofVerify || !proofVerify(result, sessionId, gen)) {
          ctx.reject = "proof";
          return;
        }
      }
      if (lock) throw new Error("single-flight");
      lock = true;
      try {
        if (!withinBudget(result.ops || [])) {
          ctx.reject = "budget";
          return;
        }
        ctx.result_ok = result.ok;
        (result.ops || []).forEach(applyOp);
      } finally {
        lock = false;
      }
      if (hooks.afterApply) {
        try { hooks.afterApply(result); } catch (e) {
          ctx.log.push(["hook_after_err", String(e)]);
        }
      }
    }

    function onResult(result) {
      queue.push(result);
      if (busy) return;
      busy = true;
      try {
        while (queue.length) applyResult(queue.shift());
      } finally {
        busy = false;
      }
    }

    function bumpGen() {
      gen += 1;
      ctx.gen = gen;
      ctx.timers = {};
      ctx.reject = null;
      queue = [];
    }

    function hello() {
      return {
        profiles: options.profiles || ["web.v1"],
        features: options.features || ["seq", "invoke"],
        ir: "1",
        effect_proof: !!(proofsRequired || proofVerify),
      };
    }

    return {
      applyResult: applyResult,
      onResult: onResult,
      bumpGen: bumpGen,
      hello: hello,
      hooks: hooks,
      get ctx() { return ctx; },
      get gen() { return gen; },
    };
  }

  function makeWebDrivers(applyOps) {
    return {
      toast: function (op, ctx) { ctx.log.push(["toast", op.message, op.level || "info"]); },
      morph: function (op, ctx) { ctx.log.push(["morph", op.target, op.html]); },
      swap: function (op, ctx) { ctx.log.push(["swap", op.target, op.html, op.swap]); },
      navigate: function (op, ctx) {
        if (ctx.result_ok === false) return;
        var h = safeHref(op.href);
        if (!h) return;
        ctx.log.push(["navigate", h]);
      },
      push_url: function (op, ctx) {
        var h = safeHref(op.href);
        if (!h) return;
        ctx.log.push(["push_url", h]);
      },
      reload: function (op, ctx) {
        if (ctx.result_ok === false) return;
        ctx.log.push(["reload"]);
      },
      focus: function (op, ctx) { ctx.log.push(["focus", op.target]); },
      set_text: function (op, ctx) { ctx.log.push(["set_text", op.target, op.text]); },
      set_attr: function (op, ctx) { ctx.log.push(["set_attr", op.target, op.attrs]); },
      remove: function (op, ctx) { ctx.log.push(["remove", op.target]); },
      dispatch: function (op, ctx) { ctx.log.push(["dispatch", op.name]); },
      "signal.set": function (op, ctx) { ctx.log.push(["signal.set", op.path, op.value]); },
      "timer.set": function (op, ctx) {
        var ms = Math.max(0, Math.min(Number(op.ms) || 0, 600000));
        var id = String(op.id || "t");
        var g = ctx.gen;
        var body = op.ops || [];
        var fire = function () {
          if (ctx.gen !== g) return;
          if (applyOps) applyOps(body, ctx);
          else if (typeof ctx.apply_ops === "function") ctx.apply_ops(body, ctx);
          else ctx.log.push(["timer_fire", id, body]);
        };
        ctx.timers[id] = { ms: ms, fire: fire, gen: g };
        if (ms === 0) fire();
      },
      "timer.clear": function (op, ctx) { delete ctx.timers[String(op.id || "")]; },
      "delta.patch": function (op, ctx) { ctx.log.push(["delta.patch", op.target, op.base_hash]); },
      "delta.signal": function (op, ctx) { ctx.log.push(["delta.signal", op.path, op.value]); },
      invoke: function (op, ctx) { ctx.log.push(["invoke", op.ref, op.method, op.args]); },
      noop: function (op, ctx) { ctx.log.push(["noop"]); },
    };
  }

  var api = {
    createPeerKernel: createPeerKernel,
    makeWebDrivers: makeWebDrivers,
    safeHref: safeHref,
    companions: {
      perception: "ux-peer-perception.js",
      continuations: "ux-peer-continuations.js",
    },
  };
  if (typeof global !== "undefined") global.uxcPeer = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
