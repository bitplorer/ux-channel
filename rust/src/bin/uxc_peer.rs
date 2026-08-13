//! HTTP peer: POST /ux-channel/action  Intent → Result
//!
//! Also serves:
//!   GET  /ux-channel/health
//!   POST /ux-channel/mint     (dev: mint cap — same secret as verifier)
//!   GET  /                    interactive demo page
//!
//! Bind: UXC_HOST (default 0.0.0.0) + UXC_PORT (default 8787).
//!
//! **Secrets (see repo OPERATIONAL.md):**
//! - Production: set `UXC_CAP_SECRET` to a private high-entropy value (≥ 16 chars).
//! - Oracle secret is PUBLIC (conformance only). Refused unless `UXC_ALLOW_ORACLE_SECRET=1`.

use std::env;
use std::sync::Arc;

use serde_json::{json, Value};
use tiny_http::{Header, Method, Response, Server, StatusCode};
use ux_channel_rs::cap::{CapService, ORACLE_SECRET};
use ux_channel_rs::Peer;

/// Resolve cap secret. Fail closed: no silent public default in production.
fn resolve_secret() -> Result<(CapService, bool), String> {
    let allow_oracle = env::var("UXC_ALLOW_ORACLE_SECRET")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    match env::var("UXC_CAP_SECRET") {
        Ok(s) if s.is_empty() => {
            if allow_oracle {
                eprintln!(
                    "WARNING: UXC_CAP_SECRET empty; using PUBLIC oracle secret \
                     (UXC_ALLOW_ORACLE_SECRET=1). Demo only — not for production."
                );
                Ok((CapService::oracle(), true))
            } else {
                Err(
                    "UXC_CAP_SECRET is empty. Refusing silent default. \
                     Export a private secret, or set UXC_ALLOW_ORACLE_SECRET=1 for local demo. \
                     See OPERATIONAL.md."
                        .into(),
                )
            }
        }
        Ok(s) if s == ORACLE_SECRET => {
            if allow_oracle {
                eprintln!(
                    "WARNING: UXC_CAP_SECRET equals the PUBLIC conformance oracle secret. \
                     Anyone with the repo can mint caps. Demo only."
                );
                CapService::new(s.as_bytes(), 3600)
                    .map(|c| (c, true))
                    .map_err(|e| e.to_string())
            } else {
                Err(
                    "UXC_CAP_SECRET is the public oracle secret. Refusing to start. \
                     Set a private secret, or set UXC_ALLOW_ORACLE_SECRET=1 for local demo only."
                        .into(),
                )
            }
        }
        Ok(s) if s.len() < 16 => Err("UXC_CAP_SECRET must be at least 16 characters".into()),
        Ok(s) => CapService::new(s.as_bytes(), 3600)
            .map(|c| (c, false))
            .map_err(|e| e.to_string()),
        Err(_) if allow_oracle => {
            eprintln!(
                "WARNING: UXC_CAP_SECRET unset; using PUBLIC oracle secret \
                 (UXC_ALLOW_ORACLE_SECRET=1). Demo only — not for production."
            );
            Ok((CapService::oracle(), true))
        }
        Err(_) => Err(
            "UXC_CAP_SECRET is not set. Refusing silent default. \
             Export a private secret, or set UXC_ALLOW_ORACLE_SECRET=1 for local demo only. \
             See OPERATIONAL.md."
                .into(),
        ),
    }
}

fn main() {
    let host = env::var("UXC_HOST").unwrap_or_else(|_| "0.0.0.0".into());
    let port: u16 = env::var("UXC_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8787);
    let addr = format!("{host}:{port}");

    let (caps, demo_mode) = match resolve_secret() {
        Ok(v) => v,
        Err(msg) => {
            eprintln!("uxc_peer: {msg}");
            std::process::exit(2);
        }
    };
    let peer = Arc::new(Peer::new(caps));
    let server = Server::http(&addr).unwrap_or_else(|e| {
        eprintln!("failed to bind {addr}: {e}");
        std::process::exit(1);
    });
    eprintln!("uxc_peer listening on http://{addr}");
    eprintln!("  POST /ux-channel/action   Intent → Result");
    eprintln!("  GET  /ux-channel/health");
    eprintln!("  POST /ux-channel/mint     (cap mint; same secret as verifier)");
    if demo_mode {
        eprintln!("  mode: DEMO (public oracle-capable secret) — not for production");
    } else {
        eprintln!("  mode: secret from UXC_CAP_SECRET");
    }

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
                    "demo_mode": demo_mode,
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
                            "note": if demo_mode {
                                "dev/demo; oracle or allow-listed secret"
                            } else {
                                "uses UXC_CAP_SECRET; protect this endpoint in production"
                            },
                        },
                    },
                    "cap_required": ["Cart.add"],
                    "policy": {
                        "present_cap_must_verify": true,
                        "once_jti_enforced": true,
                    },
                    "notes": if demo_mode {
                        "DEMO: capability secret is public oracle or explicitly allowed. JSON only on HTTP."
                    } else {
                        "HTTP surface speaks JSON only; CXB is library-side optional"
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
                    "ops": [],
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
            let parsed = serde_json::from_slice::<serde_json::Value>(&bytes).ok();
            let ok = parsed
                .as_ref()
                .and_then(|v| v.get("ok").and_then(|x| x.as_bool()))
                .unwrap_or(false);
            let code = parsed
                .as_ref()
                .and_then(|v| v.get("error"))
                .and_then(|e| e.get("code"))
                .and_then(|c| c.as_str())
                .unwrap_or("");
            let status = if ok {
                StatusCode(200)
            } else if code == "unauthorized" {
                StatusCode(401)
            } else {
                StatusCode(400)
            };
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
    label { font-size: .85rem; color: var(--muted); display: block; margin-bottom: .25rem; }
    input {
      width: 100%; background: #0e121b; border: 1px solid var(--border);
      border-radius: 10px; color: var(--text); padding: .55rem .7rem; font: inherit;
    }
    button {
      appearance: none; border: 0; border-radius: 10px; padding: .55rem .9rem;
      font: inherit; font-weight: 650; cursor: pointer;
      background: linear-gradient(180deg, #8eb0ff, var(--accent)); color: #0b1020;
    }
    button.secondary { background: #222836; color: var(--text); border: 1px solid var(--border); }
    #cart, #log {
      min-height: 2.5rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: .82rem; white-space: pre-wrap; word-break: break-word;
      background: #0a0d14; border: 1px solid var(--border); border-radius: 10px;
      padding: .75rem; color: var(--muted);
    }
    .ok { color: var(--ok); }
    .err { color: var(--err); }
    .hint { font-size: .8rem; color: var(--muted); margin-top: .5rem; }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="eyebrow">ux-channel · wire-native peer</div>
      <h1>Intent → Result · demo</h1>
      <p class="lede">Mint a cap, run Cart.add / Counter.inc. Caps authorize; this transport only delivers.</p>
    </header>
    <div class="grid">
      <div class="card">
        <h2>Cart.add (cap required)</h2>
        <div class="grid grid-2" style="margin-bottom:.65rem">
          <div>
            <label for="sku">sku</label>
            <input id="sku" value="abc-123"/>
          </div>
          <div>
            <label for="qty">qty</label>
            <input id="qty" type="number" value="2" min="1"/>
          </div>
        </div>
        <div class="row">
          <button type="button" id="btn-cart">Mint + Cart.add</button>
          <button type="button" class="secondary" id="btn-cart-no-cap">Cart without cap</button>
        </div>
        <p class="hint">Missing cap → unauthorized. Present bogus cap also fails (present-cap-must-verify).</p>
      </div>
      <div class="card">
        <h2>Counter (open)</h2>
        <div class="row">
          <button type="button" id="btn-inc">Counter.inc</button>
          <button type="button" class="secondary" id="btn-get">Counter.get</button>
        </div>
      </div>
      <div class="card">
        <h2>#cart morph target</h2>
        <div id="cart">(empty)</div>
      </div>
      <div class="card">
        <h2>last Result</h2>
        <div id="log">(none yet)</div>
      </div>
    </div>
  </div>
  <script>
    const logEl = document.getElementById('log');
    const cartEl = document.getElementById('cart');

    async function postAction(intent) {
      const res = await fetch('/ux-channel/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/ux-channel+json', 'Accept': 'application/ux-channel+json' },
        body: JSON.stringify(intent),
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = { ok: false, error: { message: text } }; }
      logEl.className = data.ok ? 'ok' : 'err';
      logEl.textContent = JSON.stringify({ http: res.status, ...data }, null, 2);
      if (data.ops) {
        for (const op of data.ops) {
          if (op.op === 'morph' && op.target === '#cart' && op.html) {
            cartEl.innerHTML = op.html;
          }
        }
      }
      return data;
    }

    async function mint(action, args) {
      const res = await fetch('/ux-channel/mint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, args }),
      });
      return res.json();
    }

    document.getElementById('btn-cart').onclick = async () => {
      const sku = document.getElementById('sku').value;
      const qty = Number(document.getElementById('qty').value);
      const m = await mint('Cart.add', { sku, qty });
      if (!m.ok) { logEl.className = 'err'; logEl.textContent = JSON.stringify(m, null, 2); return; }
      await postAction({ v: '1', action: 'Cart.add', args: { sku, qty }, cap: m.cap, request_id: 'demo-' + Date.now() });
    };
    document.getElementById('btn-cart-no-cap').onclick = async () => {
      const sku = document.getElementById('sku').value;
      const qty = Number(document.getElementById('qty').value);
      await postAction({ v: '1', action: 'Cart.add', args: { sku, qty } });
    };
    document.getElementById('btn-inc').onclick = () =>
      postAction({ v: '1', action: 'Counter.inc', args: { by: 1 } });
    document.getElementById('btn-get').onclick = () =>
      postAction({ v: '1', action: 'Counter.get', args: {} });
  </script>
</body>
</html>
"#;
