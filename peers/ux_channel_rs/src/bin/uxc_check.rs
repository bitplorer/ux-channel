//! Load conformance vectors, verify JSON round-trip, cap oracle, CXB expected,
//! peer edge cases, and optional HTTP peer.
//!
//! Usage (from peers/ux_channel_rs):
//!   cargo run --bin uxc_check -- ../../conformance
//!   cargo run --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787

use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process;
use std::time::Duration;

use serde_json::{json, Value};
use ux_channel_rs::{
    actions, canonical_json, decode_cxb, decode_intent, decode_result, decode_value, encode_cxb,
    encode_intent, encode_result, is_cxb, CapError, CapService, Peer,
};

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut conf_root = PathBuf::from("../../conformance");
    let mut http_base: Option<String> = None;

    let mut i = 1;
    while i < args.len() {
        if args[i] == "--http" {
            i += 1;
            if i < args.len() {
                http_base = Some(args[i].clone());
            }
        } else if !args[i].starts_with('-') {
            conf_root = PathBuf::from(&args[i]);
        }
        i += 1;
    }

    if !conf_root.exists() {
        eprintln!("conformance root not found: {}", conf_root.display());
        process::exit(2);
    }

    let manifest_path = conf_root.join("manifest.json");
    let manifest: Value = serde_json::from_str(
        &fs::read_to_string(&manifest_path).expect("read manifest"),
    )
    .expect("parse manifest");

    let vectors = conf_root.join("vectors");
    let mut checked = 0usize;
    let mut failures: Vec<String> = Vec::new();

    let cats = manifest["vectors"].as_object().expect("vectors object");
    for (category, entries) in cats {
        let entries = entries.as_array().expect("entries array");
        for entry in entries {
            let file = entry["file"].as_str().unwrap();
            if file.ends_with(".md") {
                continue;
            }
            let path = vectors.join(file);
            if !path.exists() {
                failures.push(format!("missing: {file}"));
                continue;
            }
            let raw = fs::read(&path).expect("read vector");
            match category.as_str() {
                "intent" => match check_intent(&raw, file) {
                    Ok(()) => checked += 1,
                    Err(e) => failures.push(e),
                },
                "result" | "trace" => match check_result(&raw, file) {
                    Ok(()) => checked += 1,
                    Err(e) => failures.push(e),
                },
                "handshake" => match check_value(&raw, file) {
                    Ok(()) => checked += 1,
                    Err(e) => failures.push(e),
                },
                "cap" => match check_cap_oracle(&raw, file) {
                    Ok(n) => checked += n,
                    Err(e) => failures.push(e),
                },
                other => failures.push(format!("unknown category {other} for {file}")),
            }
        }
    }

    match check_cxb_expected(&conf_root) {
        Ok(n) => {
            if n > 0 {
                checked += n;
                println!("CXB expected blobs: ok ({n})");
            }
        }
        Err(e) => failures.push(format!("cxb expected: {e}")),
    }

    match check_peer_inprocess() {
        Ok(n) => {
            checked += n;
            println!("In-process peer checks: ok ({n})");
        }
        Err(e) => failures.push(format!("in-process peer: {e}")),
    }

    match check_peer_edges() {
        Ok(n) => {
            checked += n;
            println!("Peer edge cases: ok ({n})");
        }
        Err(e) => failures.push(format!("peer edges: {e}")),
    }

    if let Some(base) = http_base {
        match check_http_peer(&base) {
            Ok(n) => {
                checked += n;
                println!("HTTP peer checks against {base}: ok ({n})");
            }
            Err(e) => failures.push(format!("http peer: {e}")),
        }
    }

    println!("Checked {checked} vectors/cases via Rust peer");
    if !failures.is_empty() {
        println!("FAILURES:");
        for f in &failures {
            println!(" - {f}");
        }
        process::exit(1);
    }
    println!("All checks passed");
}

fn check_intent(raw: &[u8], name: &str) -> Result<(), String> {
    let intent = decode_intent(raw).map_err(|e| format!("{name}: decode {e}"))?;
    let encoded = encode_intent(&intent).map_err(|e| format!("{name}: encode {e}"))?;
    let again = decode_intent(&encoded).map_err(|e| format!("{name}: re-decode {e}"))?;
    if intent != again {
        return Err(format!("{name}: round-trip mismatch"));
    }
    let v: Value = serde_json::from_slice(raw).unwrap();
    let _ = canonical_json(&v).map_err(|e| format!("{name}: canonical {e}"))?;
    Ok(())
}

fn check_result(raw: &[u8], name: &str) -> Result<(), String> {
    let doc = decode_result(raw).map_err(|e| format!("{name}: decode {e}"))?;
    let encoded = encode_result(&doc).map_err(|e| format!("{name}: encode {e}"))?;
    let again = decode_result(&encoded).map_err(|e| format!("{name}: re-decode {e}"))?;
    if doc != again {
        return Err(format!("{name}: round-trip mismatch"));
    }
    Ok(())
}

fn check_value(raw: &[u8], name: &str) -> Result<(), String> {
    let _ = decode_value(raw).map_err(|e| format!("{name}: {e}"))?;
    Ok(())
}

fn check_cap_oracle(raw: &[u8], name: &str) -> Result<usize, String> {
    let doc: Value = serde_json::from_slice(raw).map_err(|e| format!("{name}: {e}"))?;
    if doc.get("token").is_none() {
        return Ok(1);
    }

    let token = doc["token"].as_str().ok_or_else(|| format!("{name}: token"))?;
    let sealed = doc["sealed_args"].clone();
    let secret = doc["oracle"]["secret"]
        .as_str()
        .unwrap_or(ux_channel_rs::ORACLE_SECRET);
    let salt = doc["oracle"]["salt"].as_str().unwrap_or("ux-channel-cap");
    let action = doc["payload"]["action"].as_str().unwrap_or("Cart.add");
    let expected_hash = doc["payload"]["args_hash"].as_str().unwrap_or("");

    let got_hash = CapService::hash_args(&sealed);
    if got_hash != expected_hash {
        return Err(format!(
            "{name}: args_hash mismatch got={got_hash} want={expected_hash}"
        ));
    }

    let svc = CapService::with_salt(secret, salt, 10_000_000, None)
        .map_err(|e| format!("{name}: svc {e}"))?;

    svc.verify(token, action, &sealed)
        .map_err(|e| format!("{name}: verify_same_args {e}"))?;

    let mut bad = sealed.clone();
    if let Value::Object(ref mut m) = bad {
        m.insert("qty".into(), json!(3));
    }
    match svc.verify(token, action, &bad) {
        Err(CapError::ArgsMismatch) => {}
        other => {
            return Err(format!(
                "{name}: verify_qty_3 expected ArgsMismatch got {other:?}"
            ))
        }
    }

    match svc.verify(token, "Cart.remove", &sealed) {
        Err(CapError::ActionMismatch) => {}
        other => {
            return Err(format!(
                "{name}: verify_wrong_action expected ActionMismatch got {other:?}"
            ))
        }
    }

    let minted = svc
        .mint(action, &sealed, Some("user:42"), Some(&["cart:write".into()]))
        .map_err(|e| format!("{name}: mint {e}"))?;
    svc.verify(&minted, action, &sealed)
        .map_err(|e| format!("{name}: mint-verify {e}"))?;

    println!("{name}: cap oracle + mint/verify ok");
    Ok(5)
}

fn resolve_cxb_blob(conf_root: &Path, file: &str) -> PathBuf {
    let under_conf = conf_root.join(file);
    if under_conf.exists() {
        return under_conf;
    }
    if let Some(pkg) = conf_root.parent() {
        let under_pkg = pkg.join(file);
        if under_pkg.exists() {
            return under_pkg;
        }
        let via_name = conf_root
            .join("expected/cxb")
            .join(Path::new(file).file_name().unwrap_or_default());
        if via_name.exists() {
            return via_name;
        }
        return under_pkg;
    }
    under_conf
}

fn check_cxb_expected(conf_root: &Path) -> Result<usize, String> {
    let index_path = conf_root.join("expected/cxb/index.json");
    if !index_path.exists() {
        return Ok(0);
    }
    let index: Value = serde_json::from_str(
        &fs::read_to_string(&index_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    let vectors = index["vectors"].as_array().ok_or("cxb index vectors")?;
    let mut n = 0usize;
    for entry in vectors {
        let file = entry["file"].as_str().ok_or("file")?;
        let blob_path = resolve_cxb_blob(conf_root, file);
        let blob = fs::read(&blob_path).map_err(|e| {
            format!("{file}: {} (tried {})", e, blob_path.display())
        })?;
        if !is_cxb(&blob) {
            return Err(format!("{file}: not CXB magic"));
        }
        let want_len = entry["len"].as_u64().unwrap_or(0) as usize;
        if blob.len() != want_len {
            return Err(format!("{file}: len {} != {}", blob.len(), want_len));
        }
        let decoded = decode_cxb(&blob).map_err(|e| format!("{file}: decode {e}"))?;

        if let Some(src) = entry["source"].as_str() {
            let src_path = conf_root.join(src);
            if src_path.exists() {
                let src_doc: Value = serde_json::from_str(
                    &fs::read_to_string(&src_path).map_err(|e| e.to_string())?,
                )
                .map_err(|e| e.to_string())?;
                if let Some(a) = src_doc.get("action") {
                    if decoded.get("action") != Some(a) {
                        return Err(format!("{file}: action mismatch after decode"));
                    }
                }
                if let Some(ok) = src_doc.get("ok") {
                    if decoded.get("ok") != Some(ok) {
                        return Err(format!("{file}: ok mismatch after decode"));
                    }
                }
                let re = encode_cxb(&src_doc).map_err(|e| format!("{file}: encode {e}"))?;
                if !is_cxb(&re) {
                    return Err(format!("{file}: re-encode not CXB"));
                }
                let re_dec = decode_cxb(&re).map_err(|e| format!("{file}: re-decode {e}"))?;
                if let Some(a) = src_doc.get("action") {
                    if re_dec.get("action") != Some(a) {
                        return Err(format!("{file}: re-encode action lost"));
                    }
                }
                if let Some(ok) = src_doc.get("ok") {
                    if re_dec.get("ok") != Some(ok) {
                        return Err(format!("{file}: re-encode ok lost"));
                    }
                }
            }
        }
        n += 1;
    }
    Ok(n)
}

fn check_peer_inprocess() -> Result<usize, String> {
    actions::reset_counter();
    let peer = Peer::with_oracle();
    let args = json!({"sku": "abc-123", "qty": 2});
    let cap = peer
        .mint_cap(
            "Cart.add",
            &args,
            Some("user:42"),
            Some(&["cart:write".into()]),
        )
        .map_err(|e| e.to_string())?;

    let body = serde_json::to_vec(&json!({
        "v": "1",
        "action": "Cart.add",
        "args": args,
        "cap": cap,
        "request_id": "check-1",
    }))
    .unwrap();
    let out = peer.handle_json(&body).map_err(|e| e.to_string())?;
    let result: Value = serde_json::from_slice(&out).unwrap();
    if result["ok"] != true {
        return Err(format!("Cart.add expected ok, got {result}"));
    }
    let ops = result["ops"].as_array().ok_or("ops array")?;
    if ops.is_empty() {
        return Err("Cart.add expected non-empty ops".into());
    }

    let body2 = serde_json::to_vec(&json!({
        "v": "1",
        "action": "Cart.add",
        "args": args,
    }))
    .unwrap();
    let out2 = peer.handle_json(&body2).map_err(|e| e.to_string())?;
    let r2: Value = serde_json::from_slice(&out2).unwrap();
    if r2["ok"] != false || r2["error"]["code"] != "unauthorized" {
        return Err(format!("missing cap expected unauthorized, got {r2}"));
    }
    let msg = r2["error"]["message"].as_str().unwrap_or("");
    if !msg.contains("required") {
        return Err(format!("missing cap message should say required, got {msg}"));
    }

    let body3 = serde_json::to_vec(&json!({
        "v": "1",
        "action": "Counter.inc",
        "args": {"by": 2},
    }))
    .unwrap();
    let out3 = peer.handle_json(&body3).map_err(|e| e.to_string())?;
    let r3: Value = serde_json::from_slice(&out3).unwrap();
    if r3["ok"] != true {
        return Err(format!("Counter.inc expected ok, got {r3}"));
    }

    Ok(3)
}

/// Edge cases that must not silently succeed or mis-label.
fn check_peer_edges() -> Result<usize, String> {
    actions::reset_counter();
    let peer = Peer::with_oracle();
    let mut n = 0;

    let out = peer
        .handle_json(
            &serde_json::to_vec(&json!({"v":"2","action":"Counter.inc","args":{}})).unwrap(),
        )
        .map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["ok"] != false || v["meta"]["action"] != "Counter.inc" {
        return Err(format!("wrong IR: {v}"));
    }
    n += 1;

    let out = peer
        .handle_json(
            &serde_json::to_vec(&json!({"v":"1","action":"No.Such","args":{}})).unwrap(),
        )
        .map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["error"]["code"] != "not_found" {
        return Err(format!("unknown action: {v}"));
    }
    n += 1;

    let out = peer
        .handle_json(
            &serde_json::to_vec(&json!({
                "v":"1","action":"Counter.inc","args":{"by":1},"cap":"x.y.z"
            }))
            .unwrap(),
        )
        .map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["error"]["code"] != "unauthorized" {
        return Err(format!("spurious cap: {v}"));
    }
    n += 1;

    let args = json!({"sku":"a","qty":"2"});
    let cap = peer.mint_cap("Cart.add", &args, None, None).map_err(|e| e.to_string())?;
    let out = peer
        .handle_json(
            &serde_json::to_vec(&json!({
                "v":"1","action":"Cart.add","args":args,"cap":cap
            }))
            .unwrap(),
        )
        .map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["ok"] != false || v["error"]["code"] != "validation" {
        return Err(format!("string qty: {v}"));
    }
    n += 1;

    // XSS: sku contains HTML break-out; morph html must escape.
    let mut map = serde_json::Map::new();
    map.insert(
        "sku".into(),
        Value::String(String::from("\"><img src=x>")),
    );
    map.insert("qty".into(), json!(1));
    let args = Value::Object(map);
    let cap = peer.mint_cap("Cart.add", &args, None, None).map_err(|e| e.to_string())?;
    let out = peer
        .handle_json(
            &serde_json::to_vec(&json!({
                "v":"1","action":"Cart.add","args":args,"cap":cap
            }))
            .unwrap(),
        )
        .map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["ok"] != true {
        return Err(format!("xss cart: {v}"));
    }
    let html = v["ops"]
        .as_array()
        .unwrap()
        .iter()
        .find(|o| o["op"] == "morph")
        .and_then(|o| o["html"].as_str())
        .unwrap_or("");
    if html.contains("<img") {
        return Err(format!("sku not escaped: {html}"));
    }
    n += 1;

    let out = peer.handle_json(b"").map_err(|e| e.to_string())?;
    let v: Value = serde_json::from_slice(&out).unwrap();
    if v["ok"] != false || v["error"]["code"] != "validation" {
        return Err(format!("empty body: {v}"));
    }
    n += 1;

    Ok(n)
}

fn check_http_peer(base: &str) -> Result<usize, String> {
    let base = base.trim_end_matches('/');
    let peer = Peer::with_oracle();
    let args = json!({"sku": "abc-123", "qty": 2});
    let cap = peer
        .mint_cap(
            "Cart.add",
            &args,
            Some("user:42"),
            Some(&["cart:write".into()]),
        )
        .map_err(|e| e.to_string())?;

    let health = http_get(&format!("{base}/ux-channel/health"))?;
    let hv: Value = serde_json::from_str(&health).map_err(|e| e.to_string())?;
    if hv["ok"] != true {
        return Err(format!("health not ok: {hv}"));
    }
    let formats = hv["formats"].as_array().ok_or("health.formats")?;
    let has_json = formats
        .iter()
        .any(|f| f.as_str() == Some("application/ux-channel+json"));
    if !has_json {
        return Err(format!("health missing json format: {hv}"));
    }
    let claims_cxb_http = formats
        .iter()
        .any(|f| f.as_str() == Some("application/ux-channel+cxb"));
    if claims_cxb_http {
        return Err("health.formats must not advertise +cxb until HTTP serves it".into());
    }
    if hv["codecs"].as_array().map(|a| a.is_empty()).unwrap_or(true) {
        return Err(format!("health.codecs missing (library capability): {hv}"));
    }

    let intent = json!({
        "v": "1",
        "action": "Cart.add",
        "args": args,
        "cap": cap,
        "request_id": "http-check-1",
    });
    let body = serde_json::to_vec(&intent).unwrap();
    let resp = http_post(
        &format!("{base}/ux-channel/action"),
        &body,
        "application/ux-channel+json",
    )?;
    let result: Value = serde_json::from_str(&resp).map_err(|e| e.to_string())?;
    if result["ok"] != true {
        return Err(format!("HTTP Cart.add not ok: {result}"));
    }
    if result["ops"].as_array().map(|a| a.is_empty()).unwrap_or(true) {
        return Err("HTTP Cart.add empty ops".into());
    }

    let body2 = serde_json::to_vec(&json!({
        "v":"1","action":"Cart.add","args":args
    }))
    .unwrap();
    let resp2 = http_post(
        &format!("{base}/ux-channel/action"),
        &body2,
        "application/ux-channel+json",
    )?;
    let r2: Value = serde_json::from_str(&resp2).map_err(|e| e.to_string())?;
    if r2["ok"] != false || r2["error"]["code"] != "unauthorized" {
        return Err(format!("HTTP missing cap: {r2}"));
    }

    Ok(3)
}

fn http_get(url: &str) -> Result<String, String> {
    let (host, port, path) = parse_http_url(url)?;
    let mut stream = TcpStream::connect((host.as_str(), port))
        .map_err(|e| format!("connect {host}:{port}: {e}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .ok();
    let req = format!("GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n");
    stream.write_all(req.as_bytes()).map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    stream.read_to_end(&mut buf).map_err(|e| e.to_string())?;
    split_http_body(&buf)
}

fn http_post(url: &str, body: &[u8], content_type: &str) -> Result<String, String> {
    let (host, port, path) = parse_http_url(url)?;
    let mut stream = TcpStream::connect((host.as_str(), port))
        .map_err(|e| format!("connect {host}:{port}: {e}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .ok();
    let req = format!(
        "POST {path} HTTP/1.1\r\nHost: {host}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    stream.write_all(req.as_bytes()).map_err(|e| e.to_string())?;
    stream.write_all(body).map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    stream.read_to_end(&mut buf).map_err(|e| e.to_string())?;
    split_http_body(&buf)
}

fn parse_http_url(url: &str) -> Result<(String, u16, String), String> {
    let rest = url
        .strip_prefix("http://")
        .ok_or_else(|| format!("only http:// supported: {url}"))?;
    let (hostport, path) = match rest.split_once('/') {
        Some((hp, p)) => (hp, format!("/{p}")),
        None => (rest, "/".into()),
    };
    let (host, port) = if let Some((h, p)) = hostport.split_once(':') {
        (h.to_string(), p.parse().map_err(|e| format!("port: {e}"))?)
    } else {
        (hostport.to_string(), 80u16)
    };
    Ok((host, port, path))
}

fn split_http_body(buf: &[u8]) -> Result<String, String> {
    let text = String::from_utf8_lossy(buf);
    if let Some(idx) = text.find("\r\n\r\n") {
        Ok(text[idx + 4..].to_string())
    } else if let Some(idx) = text.find("\n\n") {
        Ok(text[idx + 2..].to_string())
    } else {
        Err(format!(
            "no HTTP body in response: {}",
            &text[..text.len().min(200)]
        ))
    }
}
