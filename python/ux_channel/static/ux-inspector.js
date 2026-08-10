/**
 * ux-inspector — Wireshark-like DX for Channel actions & bridges
 *
 * Touchpoints:
 *  - Intercepts uxChannel.runAction / applyResult / postIntent
 *  - Hooks uxBridge.apply for mount/update/call/destroy
 *  - Timeline UI (bottom dock): conversations + frame list + detail
 *  - Optionally POSTs client frames to /ux-channel/trace/client for unified capture
 *
 * Enable:
 *   <body data-channel-dev data-channel-inspector>
 *   <script src="/ux-channel/static/ux-channel.js"></script>
 *   <script src="/ux-channel/static/ux-bridge.js"></script>
 *   <script src="/ux-channel/static/ux-inspector.js"></script>
 */
(function (global) {
  "use strict";
  if (global.uidInspector && global.uidInspector.version) {
    try { console.warn("[ux-inspector] already loaded — skip"); } catch (e0) {}
    return;
  }

  var VERSION = "0.1.0";
  var frames = [];
  var maxFrames = 400;
  var selectedReq = null;
  var dock = null;
  var flushTimer = null;
  var pendingClient = [];

  function enabled() {
    return !!(document.body && document.body.hasAttribute("data-channel-inspector"));
  }

  function endpoint() {
    var el = document.body && document.body.getAttribute("data-channel-endpoint");
    var base = el || "/ux-channel/action";
    return base.replace(/\/action\/?$/, "");
  }

  function now() {
    return performance.now();
  }

  function pushFrame(f) {
    f.ts = f.ts || Date.now() / 1000;
    f.seq = frames.length + 1;
    frames.push(f);
    if (frames.length > maxFrames) frames.shift();
    pendingClient.push(f);
    scheduleFlush();
    render();
  }

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = setTimeout(function () {
      flushTimer = null;
      flushClient();
    }, 400);
  }

  function flushClient() {
    if (!pendingClient.length) return;
    var batch = pendingClient.splice(0, 100);
    var url = endpoint() + "/trace/client";
    try {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ frames: batch }),
      }).catch(function () {});
    } catch (e) {}
  }

  function conversations() {
    var by = {};
    frames.forEach(function (f) {
      var k = f.request_id || "anon";
      if (!by[k]) by[k] = [];
      by[k].push(f);
    });
    return Object.keys(by)
      .map(function (k) {
        var frs = by[k];
        var action = null;
        var ok = null;
        frs.forEach(function (f) {
          if (f.action) action = f.action;
          if (f.ok != null) ok = f.ok;
        });
        return {
          request_id: k,
          action: action,
          frames: frs.length,
          ok: ok,
          last: frs[frs.length - 1],
        };
      })
      .reverse();
  }

  function ensureDock() {
    if (dock) return dock;
    dock = document.createElement("div");
    dock.id = "ux-inspector-dock";
    dock.innerHTML =
      '<div class="ux-insp-bar">' +
      '<strong>UX Inspector</strong> <span class="ux-insp-sub">actions · bridges · ops</span>' +
      '<span class="ux-insp-spacer"></span>' +
      '<button type="button" data-act="refresh">Refresh server</button>' +
      '<button type="button" data-act="clear">Clear</button>' +
      '<button type="button" data-act="export">Export</button>' +
      '<button type="button" data-act="toggle">_</button>' +
      "</div>" +
      '<div class="ux-insp-body">' +
      '<div class="ux-insp-col ux-insp-streams"></div>' +
      '<div class="ux-insp-col ux-insp-frames"></div>' +
      '<div class="ux-insp-col ux-insp-detail"><pre></pre></div>' +
      "</div>";
    var style = document.createElement("style");
    style.textContent =
      "#ux-inspector-dock{position:fixed;left:0;right:0;bottom:0;z-index:100000;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#e2e8f0;background:#0b1220;border-top:1px solid #334155;max-height:42vh;display:flex;flex-direction:column;box-shadow:0 -8px 24px rgba(0,0,0,.35)}" +
      "#ux-inspector-dock.ux-collapsed .ux-insp-body{display:none}" +
      "#ux-inspector-dock .ux-insp-bar{display:flex;align-items:center;gap:.5rem;padding:.35rem .6rem;background:#111827;border-bottom:1px solid #1f2937}" +
      "#ux-inspector-dock .ux-insp-sub{color:#94a3b8;font-weight:normal}" +
      "#ux-inspector-dock .ux-insp-spacer{flex:1}" +
      "#ux-inspector-dock button{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:.2rem .45rem;cursor:pointer;font:inherit}" +
      "#ux-inspector-dock button:hover{background:#334155}" +
      "#ux-inspector-dock .ux-insp-body{display:grid;grid-template-columns:minmax(10rem,18%) 1fr minmax(12rem,32%);min-height:10rem;overflow:hidden;flex:1}" +
      "#ux-inspector-dock .ux-insp-col{overflow:auto;border-right:1px solid #1f2937}" +
      "#ux-inspector-dock .ux-insp-detail{border-right:none}" +
      "#ux-inspector-dock .ux-insp-detail pre{margin:0;padding:.5rem;white-space:pre-wrap;word-break:break-word;color:#cbd5e1}" +
      "#ux-inspector-dock .row{padding:.3rem .5rem;cursor:pointer;border-bottom:1px solid #1e293b}" +
      "#ux-inspector-dock .row:hover{background:#1e293b}" +
      "#ux-inspector-dock .row.on{background:#1d4ed8}" +
      "#ux-inspector-dock .ok{color:#4ade80}" +
      "#ux-inspector-dock .bad{color:#f87171}" +
      "#ux-inspector-dock .kind{color:#38bdf8}" +
      "#ux-inspector-dock .muted{color:#64748b}";
    document.head.appendChild(style);
    document.body.appendChild(dock);
    dock.addEventListener("click", function (ev) {
      var btn = ev.target.closest("button[data-act]");
      if (btn) {
        var act = btn.getAttribute("data-act");
        if (act === "clear") {
          frames = [];
          selectedReq = null;
          fetch(endpoint() + "/trace", { method: "DELETE", credentials: "same-origin" }).catch(function () {});
          render();
        } else if (act === "export") {
          var blob = new Blob(
            [JSON.stringify({ frames: frames, conversations: conversations() }, null, 2)],
            { type: "application/json" }
          );
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "ux-trace-" + Date.now() + ".json";
          a.click();
        } else if (act === "toggle") {
          dock.classList.toggle("ux-collapsed");
        } else if (act === "refresh") {
          pullServer();
        }
        return;
      }
      var row = ev.target.closest("[data-req]");
      if (row) {
        selectedReq = row.getAttribute("data-req");
        render();
        return;
      }
      var fr = ev.target.closest("[data-seq]");
      if (fr) {
        var seq = parseInt(fr.getAttribute("data-seq"), 10);
        var found = frames.filter(function (x) {
          return x.seq === seq;
        })[0];
        showDetail(found);
      }
    });
    return dock;
  }

  function showDetail(f) {
    var pre = dock.querySelector(".ux-insp-detail pre");
    if (!pre) return;
    pre.textContent = f ? JSON.stringify(f, null, 2) : "";
  }

  function render() {
    if (!enabled()) return;
    ensureDock();
    var streams = dock.querySelector(".ux-insp-streams");
    var fl = dock.querySelector(".ux-insp-frames");
    var conv = conversations();
    streams.innerHTML = conv
      .map(function (c) {
        var cls = "row" + (selectedReq === c.request_id ? " on" : "");
        var badge =
          c.ok === false ? '<span class="bad">FAIL</span>' : c.ok === true ? '<span class="ok">OK</span>' : '<span class="muted">…</span>';
        return (
          '<div class="' +
          cls +
          '" data-req="' +
          c.request_id +
          '">' +
          badge +
          " <span class=\"muted\">" +
          c.frames +
          "</span> " +
          (c.action || "?") +
          '<div class="muted">' +
          c.request_id.slice(0, 18) +
          "</div></div>"
        );
      })
      .join("");
    var list = selectedReq
      ? frames.filter(function (f) {
          return f.request_id === selectedReq;
        })
      : frames.slice(-80);
    fl.innerHTML = list
      .map(function (f) {
        return (
          '<div class="row" data-seq="' +
          f.seq +
          '"><span class="kind">' +
          (f.kind || "") +
          "</span> " +
          (f.summary || "") +
          (f.duration_ms != null ? ' <span class="muted">' + f.duration_ms + "ms</span>" : "") +
          "</div>"
        );
      })
      .join("");
  }

  function pullServer() {
    fetch(endpoint() + "/trace?limit=300", { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.frames) return;
        data.frames.forEach(function (f) {
          // merge by seq+kind+ts heuristic
          frames.push(f);
        });
        if (frames.length > maxFrames) frames = frames.slice(-maxFrames);
        render();
      })
      .catch(function () {});
  }

  function wrapChannel() {
    var uc = global.uxChannel;
    if (!uc) return;
    var origApply = uc.applyResult;
    var origPost = uc.postIntent;
    var origRun = uc.runAction;

    uc.applyResult = function (result) {
      var rid = (result && result.meta && result.meta.request_id) || null;
      var action = (result && result.meta && result.meta.action) || null;
      pushFrame({
        kind: "client.result",
        summary: "apply Result ops=" + ((result && result.ops && result.ops.length) || 0),
        request_id: rid,
        action: action,
        ok: result && result.ok,
        detail: {
          op_kinds: (result && result.ops ? result.ops : []).map(function (o) {
            return o && o.op;
          }),
          error: result && result.error,
        },
      });
      (result && result.ops ? result.ops : []).forEach(function (op, i) {
        if (!op) return;
        var kind = String(op.op || "").indexOf("bridge.") === 0 ? "client.bridge" : "client.op";
        pushFrame({
          kind: kind,
          summary: "apply[" + i + "] " + op.op + (op.target ? " " + op.target : "") + (op.id ? " id=" + op.id : ""),
          request_id: rid,
          action: action,
          detail: { op: op.op, target: op.target, id: op.id, package: op.package },
        });
      });
      return origApply.apply(this, arguments);
    };

    if (origPost) {
      uc.postIntent = function (intent) {
        var t0 = now();
        pushFrame({
          kind: "client.intent",
          summary: "POST " + (intent && intent.action),
          request_id: intent && intent.request_id,
          action: intent && intent.action,
          detail: { args: intent && intent.args, target: intent && intent.target },
        });
        return Promise.resolve(origPost.apply(this, arguments)).then(
          function (body) {
            pushFrame({
              kind: "client.http",
              summary: "response " + (intent && intent.action),
              request_id: intent && intent.request_id,
              action: intent && intent.action,
              duration_ms: Math.round(now() - t0),
              ok: body && body.ok,
            });
            return body;
          },
          function (err) {
            pushFrame({
              kind: "client.error",
              summary: String(err && err.message ? err.message : err),
              request_id: intent && intent.request_id,
              action: intent && intent.action,
              ok: false,
            });
            throw err;
          }
        );
      };
    }
  }

  function wrapBridge() {
    var br = global.uxBridge;
    if (!br || !br.apply) return;
    var orig = br.apply;
    br.apply = function (op) {
      var t0 = now();
      pushFrame({
        kind: "client.bridge",
        summary: "bridge " + (op && op.op) + " id=" + (op && op.id),
        detail: { op: op },
      });
      return Promise.resolve(orig.apply(this, arguments)).then(
        function (v) {
          pushFrame({
            kind: "client.bridge",
            summary: "bridge done " + (op && op.op) + " id=" + (op && op.id),
            duration_ms: Math.round(now() - t0),
            ok: true,
            detail: { id: op && op.id, package: op && op.package },
          });
          return v;
        },
        function (err) {
          pushFrame({
            kind: "client.bridge",
            summary: "bridge error " + (op && op.op) + ": " + err,
            ok: false,
          });
          throw err;
        }
      );
    };
  }

  function boot() {
    if (!enabled()) return;
    ensureDock();
    wrapChannel();
    wrapBridge();
    // re-wrap shortly in case scripts load order differs
    setTimeout(function () {
      wrapChannel();
      wrapBridge();
      pullServer();
    }, 50);
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.uidInspector = {
    version: VERSION,
    frames: function () {
      return frames.slice();
    },
    conversations: conversations,
    push: pushFrame,
    clear: function () {
      frames = [];
      render();
    },
    render: render,
  };
})(typeof window !== "undefined" ? window : globalThis);
