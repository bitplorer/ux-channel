//! HTTP peer: POST /ux-channel/action  Intent → Result
//!
//! Also serves:
//!   GET  /ux-channel/health
//!   POST /ux-channel/mint     (dev: mint cap with oracle secret)
//!   GET  /                    interactive demo page
//!
//! Bind: UXC_HOST (default 0.0.0.0) + UXC_PORT (default 8787).

use std::env;
use std::sync::Arc;

use serde_json::{json, Value};
use tiny_http::{Header, Method, Response, Server, StatusCode};
use ux_channel_rs::Peer;

fn main() {
    let host = env::var("UXC_HOST").unwrap_or_else(|_| "0.0.0.0".into());
    let port: u16 = env::var("UXC_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8787);
    let addr = format!("{host}:{port}");

    let peer = Arc::new(Peer::with_oracle());
    let server = Server::http(&addr).unwrap_or_else(|e| {
        eprintln!("failed to bind {addr}: {e}");
        std::process::exit(1);
    });
    eprintln!("uxc_peer listening on http://{addr}");
    eprintln!("  POST /ux-channel/action   Intent → Result");
    eprintln!("  GET  /ux-channel/health");
    eprintln!("  POST /ux-channel/mint     (dev cap mint)");

    for mut request in server.incoming_requests() {
        let method = request.method().clone();
        let url = request.url().to_string();
        let path = url.split('?').next().unwrap_or(&url).to_string();

        let mut body = Vec::new();
        if method == Method::Post {
            let _ = std::io::Read::read_to_end(&mut request.as_reader(), &mut body);
        }

        let response = match (method, path.as_str()) {
            (Method::Get, "/") => Response::from_string(DEMO_HTML)
                .with_header(header("Content-Type", "text/html; charset=utf-8")),
            (Method::Get, "/ux-channel/health") => {
                // Honest advertisement: HTTP action is JSON-only today.
                // Library codecs (JSON + CXB) are listed separately so clients
                // do not assume Accept: +cxb works on /action yet.
                let body = json!({
                    "ok": true,
                    "peer": peer.name,
                    "ir": "1",
                    "actions": ["Cart.add", "Counter.inc", "Counter.get"],
                    "formats": ["application/ux-channel+json"],
                    "codecs": ["json", "cxb"],
                    "http": {
                        "action": {
                            "path": "/ux-channel/action",
                            "content_type": "application/ux-channel+json",
                            "accept_response": ["application/ux-channel+json"],
                        },
                        "mint": {
                            "path": "/ux-channel/mint",
                            "note": "dev-only; uses oracle secret",
                        },
                    },
                    "cap_required": ["Cart.add"],
                    "policy": {
                        "present_cap_must_verify": true,
                    },
                });
                json_response(StatusCode(200), &body)
            }
            (Method::Post, "/ux-channel/action") => handle_action(&peer, &body),
            (Method::Post, "/ux-channel/mint") => handle_mint(&peer, &body),
            (Method::Options, _) => Response::from_data(vec![])
                .with_status_code(StatusCode(204))
                .with_header(header("Access-Control-Allow-Origin", "*"))
                .with_header(header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, Accept",
                ))
                .with_header(header(
                    "Access-Control-Allow-Methods",
                    "GET, POST, OPTIONS",
                )),
            _ => {
                let body = json!({
                    "ok": false,
                    "error": {"code": "not_found", "message": "no such route"}
                });
                json_response(StatusCode(404), &body)
            }
        };

        let _ = request.respond(with_cors(response));
    }
}

fn handle_action(peer: &Peer, body: &[u8]) -> Response<std::io::Cursor<Vec<u8>>> {
    // Peer::handle_json always returns a ResultDoc-shaped body (wire errors
    // are mapped into ok=false). HTTP status is secondary to Result.ok.
    match peer.handle_json(body) {
        Ok(bytes) => {
            let ok = serde_json::from_slice::<serde_json::Value>(&bytes)
                .ok()
                .and_then(|v| v.get("ok").and_then(|x| x.as_bool()))
                .unwrap_or(false);
            let status = if ok { StatusCode(200) } else { StatusCode(400) };
            Response::from_data(bytes)
                .with_status_code(status)
                .with_header(header(
                    "Content-Type",
                    "application/ux-channel+json",
                ))
        }
        Err(e) => {
            // Only encode failures should land here.
            let doc = json!({
                "ok": false,
                "ops": [],
                "error": {
                    "code": "internal",
                    "message": e.to_string(),
                    "retryable": false,
                },
                "meta": {"action": "unknown", "runtime": "ux_channel_rs"},
            });
            json_response(StatusCode(500), &doc)
        }
    }
}

fn handle_mint(peer: &Peer, body: &[u8]) -> Response<std::io::Cursor<Vec<u8>>> {
    let doc: Value = match serde_json::from_slice(body) {
        Ok(v) => v,
        Err(e) => {
            let err = json!({"ok": false, "error": e.to_string()});
            return json_response(StatusCode(400), &err);
        }
    };
    let action = doc["action"].as_str().unwrap_or("Cart.add");
    let args = doc.get("args").cloned().unwrap_or_else(|| json!({}));
    let sub = doc["sub"].as_str();
    let scopes: Option<Vec<String>> = doc["scopes"].as_array().map(|a| {
        a.iter()
            .filter_map(|v| v.as_str().map(|s| s.to_string()))
            .collect()
    });
    match peer.mint_cap(action, &args, sub, scopes.as_deref()) {
        Ok(token) => {
            let out = json!({
                "ok": true,
                "cap": token,
                "action": action,
                "args": args,
            });
            json_response(StatusCode(200), &out)
        }
        Err(e) => {
            let out = json!({"ok": false, "error": e.to_string()});
            json_response(StatusCode(400), &out)
        }
    }
}

fn json_response(status: StatusCode, value: &Value) -> Response<std::io::Cursor<Vec<u8>>> {
    let bytes = serde_json::to_vec(value).unwrap_or_else(|_| b"{}".to_vec());
    Response::from_data(bytes)
        .with_status_code(status)
        .with_header(header("Content-Type", "application/json"))
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("header")
}

fn with_cors(
    response: Response<std::io::Cursor<Vec<u8>>>,
) -> Response<std::io::Cursor<Vec<u8>>> {
    response.with_header(header("Access-Control-Allow-Origin", "*"))
}

const DEMO_HTML: &str = r#"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ux-channel · Rust peer</title>
  <style>
    :root {
      --bg: #0c0e14;
      --panel: #141822;
      --panel-2: #1a1f2c;
      --border: #2a3142;
      --text: #e8e6e3;
      --muted: #8b93a7;
      --accent: #7aa2ff;
      --accent-2: #5eead4;
      --ok: #6ee7a8;
      --err: #f87171;
      --radius: 14px;
      font-family: "Segoe UI", ui-sans-serif, system-ui, -apple-system, sans-serif;
      color: var(--text);
      background: var(--bg);
      line-height: 1.5;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100dvh;
      background:
        radial-gradient(900px 420px at 10% -10%, rgba(122,162,255,.18), transparent 55%),
        radial-gradient(700px 360px at 100% 0%, rgba(94,234,212,.10), transparent 50%),
        var(--bg);
    }
    .wrap { max-width: 44rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
    header { margin-bottom: 1.25rem; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: .45rem;
      font-size: .72rem; letter-spacing: .08em; text-transform: uppercase;
      color: var(--accent-2); font-weight: 650;
      background: rgba(94,234,212,.08); border: 1px solid rgba(94,234,212,.22);
      border-radius: 999px; padding: .28rem .65rem; margin-bottom: .75rem;
    }
    h1 {
      font-size: clamp(1.35rem, 3.5vw, 1.75rem);
      font-weight: 700; letter-spacing: -0.03em; margin: 0 0 .35rem;
    }
    .lede { color: var(--muted); margin: 0; font-size: .98rem; max-width: 36rem; }
    .grid { display: grid; gap: 1rem; }
    @media (min-width: 640px) {
      .grid-2 { grid-template-columns: 1fr 1fr; }
    }
    .card {
      background: linear-gradient(180deg, var(--panel-2), var(--panel));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1rem 1.1rem 1.1rem;
      box-shadow: 0 12px 40px rgba(0,0,0,.28);
    }
    .card h2 {
      font-size: .78rem; text-transform: uppercase; letter-spacing: .07em;
      color: var(--muted); margin: 0 0 .65rem; font-weight: 650;
    }
    .row { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
    button {
      appearance: none; border: 0; cursor: pointer;
      border-radius: 10px; padding: .62rem 1rem;
      font-weight: 650; font-size: .92rem;
      background: var(--accent); color: #0b0d12;
      transition: transform .12s ease, filter .12s ease, box-shadow .12s ease;
      box-shadow: 0 6px 18px rgba(122,162,255,.25);
    }
    button:hover { filter: brightness(1.06); transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    button.secondary {
      background: transparent; color: var(--text);
      border: 1px solid var(--border); box-shadow: none;
    }
    button:disabled { opacity: .55; cursor: wait; transform: none; }
    #cart {
      min-height: 2.4rem; margin-top: .85rem; padding: .7rem .8rem;
      border-radius: 10px; background: rgba(110,231,168,.06);
      border: 1px dashed rgba(110,231,168,.28); color: var(--ok);
      font-size: .95rem;
    }
    #cart:empty::before { content: "No cart ops applied yet."; color: var(--muted); }
    .stat {
      display: flex; justify-content: space-between; gap: 1rem;
      padding: .45rem 0; border-bottom: 1px solid rgba(42,49,66,.7);
      font-size: .9rem;
    }
    .stat:last-child { border-bottom: 0; }
    .stat span { color: var(--muted); }
    .stat strong { font-variant-numeric: tabular-nums; color: var(--text); word-break: break-all; text-align: right; }
    pre {
      margin: 0; background: #080a10; border: 1px solid var(--border);
      border-radius: 10px; padding: .8rem .9rem; overflow: auto;
      font-size: .78rem; line-height: 1.45; max-height: 22rem;
      color: #c8d0e0;
    }
    .toast-host {
      position: fixed; right: 1rem; bottom: 1rem; display: flex;
      flex-direction: column; gap: .5rem; z-index: 20;
      max-width: min(22rem, calc(100vw - 2rem));
    }
    .toast {
      padding: .7rem .9rem; border-radius: 10px; font-size: .88rem; font-weight: 600;
      background: var(--panel-2); border: 1px solid var(--border);
      box-shadow: 0 10px 30px rgba(0,0,0,.35);
      animation: in .18s ease-out;
    }
    .toast.success { border-color: rgba(110,231,168,.45); color: var(--ok); }
    .toast.info { border-color: rgba(122,162,255,.45); color: var(--accent); }
    .toast.error { border-color: rgba(248,113,113,.45); color: var(--err); }
    @keyframes in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    footer { margin-top: 1.25rem; color: var(--muted); font-size: .82rem; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86em; }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="eyebrow">IR v1 · wire-native peer</div>
      <h1>ux-channel Rust peer</h1>
      <p class="lede">
        Any peer sends <code>Intent { action, args, cap }</code> and gets
        <code>Result { ok, ops[] }</code>. Caps authorize; HTTP only delivers.
      </p>
    </header>

    <div class="grid">
      <div class="card">
        <h2>Hot actions</h2>
        <div class="row">
          <button id="btn-cart" type="button">Cart.add (capped)</button>
          <button class="secondary" id="btn-counter" type="button">Counter.inc</button>
          <button class="secondary" id="btn-get" type="button">Counter.get</button>
        </div>
        <div id="cart" aria-live="polite"></div>
      </div>

      <div class="grid grid-2">
        <div class="card">
          <h2>Peer health</h2>
          <div id="health">
            <div class="stat"><span>status</span><strong>…</strong></div>
          </div>
        </div>
        <div class="card">
          <h2>Signals</h2>
          <div class="stat"><span>counter</span><strong id="sig-counter">—</strong></div>
          <div class="stat"><span>cart.last_sku</span><strong id="sig-sku">—</strong></div>
        </div>
      </div>

      <div class="card">
        <h2>Last Result</h2>
        <pre id="out">{}</pre>
      </div>
    </div>

    <footer>
      JSON floor always works. CXB is opt-in density.
      Try Python forward: <code>peers/python_forward/forward_to_rust.py</code>
    </footer>
  </div>
  <div class="toast-host" id="toasts" aria-live="polite"></div>
<script>
const $ = (id) => document.getElementById(id);

async function mint(action, args) {
  const r = await fetch('/ux-channel/mint', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, args, sub: 'user:42', scopes: ['cart:write']}),
  });
  return r.json();
}

async function postIntent(intent) {
  const r = await fetch('/ux-channel/action', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/ux-channel+json',
      'Accept': 'application/ux-channel+json',
    },
    body: JSON.stringify(intent),
  });
  return r.json();
}

function toast(message, level) {
  const el = document.createElement('div');
  el.className = 'toast ' + (level || 'info');
  el.textContent = message;
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

function applyOps(result) {
  if (!result.ops) return;
  for (const op of result.ops) {
    if (op.op === 'morph' && op.target === '#cart') {
      $('cart').innerHTML = op.html || '';
    }
    if (op.op === 'toast') {
      toast(op.message || '', op.level || 'info');
    }
    if (op.op === 'signal_set') {
      if (op.name === 'counter') $('sig-counter').textContent = String(op.value);
      if (op.name === 'cart.last_sku') $('sig-sku').textContent = String(op.value);
    }
  }
}

function show(result) {
  $('out').textContent = JSON.stringify(result, null, 2);
  applyOps(result);
  if (result.ok === false && result.error) {
    toast(result.error.message || result.error.code, 'error');
  }
}

async function withBusy(btn, fn) {
  btn.disabled = true;
  try { await fn(); }
  catch (e) { toast(String(e), 'error'); $('out').textContent = String(e); }
  finally { btn.disabled = false; }
}

$('btn-cart').onclick = () => withBusy($('btn-cart'), async () => {
  const args = {sku: 'abc-123', qty: 2};
  const m = await mint('Cart.add', args);
  if (!m.ok) throw new Error(m.error || 'mint failed');
  const result = await postIntent({
    v: '1', action: 'Cart.add', args, cap: m.cap,
    request_id: 'demo-' + Date.now(),
  });
  show(result);
});

$('btn-counter').onclick = () => withBusy($('btn-counter'), async () => {
  show(await postIntent({v:'1', action:'Counter.inc', args:{by:1}}));
});

$('btn-get').onclick = () => withBusy($('btn-get'), async () => {
  show(await postIntent({v:'1', action:'Counter.get', args:{}}));
});

(async () => {
  try {
    const r = await fetch('/ux-channel/health');
    const h = await r.json();
    $('health').innerHTML = [
      ['peer', h.peer],
      ['ir', h.ir],
      ['actions', (h.actions || []).join(', ')],
      ['formats', (h.formats || []).join(', ')],
    ].map(([k,v]) => `<div class="stat"><span>${k}</span><strong>${v}</strong></div>`).join('');
  } catch (e) {
    $('health').innerHTML = `<div class="stat"><span>error</span><strong>${e}</strong></div>`;
  }
})();
</script>
</body>
</html>
"#;
