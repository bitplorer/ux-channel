//! Built-in action handlers for the Rust peer demo.
//!
//! One IR: handlers consume a verified Intent and return Result { ok, ops[] }.
//! Morph HTML is escaped so free-form args cannot inject markup into ops.

use crate::types::{ErrorObject, Op, ResultDoc};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicI64, Ordering};

static COUNTER: AtomicI64 = AtomicI64::new(0);

/// Dispatch a single action after caps (if any) have been checked by the peer.
pub fn dispatch(action: &str, args: Option<&HashMap<String, Value>>) -> ResultDoc {
    match action {
        "Cart.add" => cart_add(args),
        "Counter.inc" => counter_inc(args),
        "Counter.get" => counter_get(),
        other => ResultDoc {
            ok: false,
            ops: vec![],
            error: Some(ErrorObject {
                code: "not_found".into(),
                message: format!("unknown action: {other}"),
                fields: None,
                retryable: Some(false),
                details: None,
            }),
            meta: Some(meta(action)),
            trace: None,
        },
    }
}

fn cart_add(args: Option<&HashMap<String, Value>>) -> ResultDoc {
    let sku_raw = args
        .and_then(|a| a.get("sku"))
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    // qty: only integer JSON numbers are accepted (no silent string->1 coercion).
    let qty = match args.and_then(|a| a.get("qty")) {
        None => 1i64,
        Some(Value::Number(n)) => match n.as_i64() {
            Some(i) => i,
            None => return validation_cart("qty", "qty must be an integer"),
        },
        Some(_) => return validation_cart("qty", "qty must be an integer"),
    };

    if qty < 1 {
        return validation_cart("qty", "qty must be >= 1");
    }

    let sku = escape_html(sku_raw);
    let html = format!(
        "<div class=\"cart-line\" data-sku=\"{sku}\">Added <strong>{qty}</strong> x {sku}</div>"
    );

    ResultDoc {
        ok: true,
        ops: vec![
            Op {
                op: "toast".into(),
                fields: HashMap::from([
                    (
                        "message".into(),
                        json!(format!("Added {qty} x {sku_raw}")),
                    ),
                    ("level".into(), json!("success")),
                ]),
            },
            Op {
                op: "morph".into(),
                fields: HashMap::from([
                    ("target".into(), json!("#cart")),
                    ("html".into(), json!(html)),
                ]),
            },
            Op {
                op: "signal_set".into(),
                fields: HashMap::from([
                    ("name".into(), json!("cart.last_sku")),
                    ("value".into(), json!(sku_raw)),
                ]),
            },
        ],
        error: None,
        meta: Some(meta("Cart.add")),
        trace: None,
    }
}

fn validation_cart(field: &str, message: &str) -> ResultDoc {
    ResultDoc {
        ok: false,
        ops: vec![],
        error: Some(ErrorObject {
            code: "validation".into(),
            message: message.into(),
            fields: Some(HashMap::from([(field.into(), vec![message.into()])])),
            retryable: Some(false),
            details: None,
        }),
        meta: Some(meta("Cart.add")),
        trace: None,
    }
}

fn counter_inc(args: Option<&HashMap<String, Value>>) -> ResultDoc {
    let by = match args.and_then(|a| a.get("by")) {
        None => 1i64,
        Some(Value::Number(n)) => match n.as_i64() {
            Some(i) => i,
            None => return validation_counter("by", "by must be an integer"),
        },
        Some(_) => return validation_counter("by", "by must be an integer"),
    };

    let n = COUNTER.fetch_add(by, Ordering::SeqCst) + by;
    ResultDoc {
        ok: true,
        ops: vec![
            Op {
                op: "signal_set".into(),
                fields: HashMap::from([
                    ("name".into(), json!("counter")),
                    ("value".into(), json!(n)),
                ]),
            },
            Op {
                op: "toast".into(),
                fields: HashMap::from([
                    ("message".into(), json!(format!("counter = {n}"))),
                    ("level".into(), json!("info")),
                ]),
            },
        ],
        error: None,
        meta: Some(meta("Counter.inc")),
        trace: None,
    }
}

fn validation_counter(field: &str, message: &str) -> ResultDoc {
    ResultDoc {
        ok: false,
        ops: vec![],
        error: Some(ErrorObject {
            code: "validation".into(),
            message: message.into(),
            fields: Some(HashMap::from([(field.into(), vec![message.into()])])),
            retryable: Some(false),
            details: None,
        }),
        meta: Some(meta("Counter.inc")),
        trace: None,
    }
}

fn counter_get() -> ResultDoc {
    let n = COUNTER.load(Ordering::SeqCst);
    ResultDoc {
        ok: true,
        ops: vec![Op {
            op: "signal_set".into(),
            fields: HashMap::from([
                ("name".into(), json!("counter")),
                ("value".into(), json!(n)),
            ]),
        }],
        error: None,
        meta: Some(meta("Counter.get")),
        trace: None,
    }
}

fn meta(action: &str) -> HashMap<String, Value> {
    HashMap::from([
        ("action".into(), json!(action)),
        ("runtime".into(), json!("ux_channel_rs")),
    ])
}

/// Escape text for embedding in HTML text/attributes produced by ops.
fn escape_html(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str(concat!("&", "amp;")),
            '<' => out.push_str(concat!("&", "lt;")),
            '>' => out.push_str(concat!("&", "gt;")),
            '"' => out.push_str(concat!("&", "quot;")),
            '\'' => out.push_str(concat!("&#", "39;")),
            _ => out.push(c),
        }
    }
    out
}

/// Reset counter (tests only).
pub fn reset_counter() {
    COUNTER.store(0, Ordering::SeqCst);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;

    #[test]
    fn cart_escapes_html_in_sku() {
        let mut args = HashMap::new();
        let evil = format!("{}{}", '"', "><img src=x onerror=1>");
        args.insert("sku".into(), Value::String(evil));
        args.insert("qty".into(), json!(1));
        let r = cart_add(Some(&args));
        assert!(r.ok);
        let html = r.ops.iter().find(|o| o.op == "morph").unwrap();
        let h = html.fields.get("html").unwrap().as_str().unwrap();
        assert!(!h.contains("<img"));
        assert!(h.contains(concat!("&", "quot;")));
    }

    #[test]
    fn cart_rejects_non_integer_qty() {
        let mut args = HashMap::new();
        args.insert("sku".into(), json!("a"));
        args.insert("qty".into(), json!("2"));
        let r = cart_add(Some(&args));
        assert!(!r.ok);
        assert_eq!(r.error.as_ref().unwrap().code, "validation");
    }
}
