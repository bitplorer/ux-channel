//! Integration tests: Peer dispatch + cap gate (library surface).
//!
//! Run: `cargo test --test integration_peer`

use serde_json::json;
use std::collections::HashMap;
use ux_channel_rs::cap::CapService;
use ux_channel_rs::peer::Peer;
use ux_channel_rs::types::{Intent, IR_VERSION};
use ux_channel_rs::{decode_intent, encode_intent};

fn intent(action: &str, args: serde_json::Value, cap: Option<String>) -> Intent {
    let map = args
        .as_object()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .collect::<HashMap<_, _>>();
    Intent {
        v: IR_VERSION.into(),
        action: action.into(),
        args: Some(map),
        cap,
        target: None,
        request_id: Some("itest".into()),
        form: None,
        idempotency_key: None,
        extra: HashMap::new(),
    }
}

#[test]
fn counter_inc_without_cap_ok() {
    let peer = Peer::with_oracle();
    let i = intent("Counter.inc", json!({"by": 1}), None);
    let r = peer.handle_intent(&i);
    assert!(r.ok, "{:?}", r.error);
}

#[test]
fn cart_add_requires_cap() {
    let peer = Peer::with_oracle();
    let i = intent("Cart.add", json!({"sku": "x", "qty": 1}), None);
    let r = peer.handle_intent(&i);
    assert!(!r.ok);
    assert_eq!(r.error.as_ref().unwrap().code, "unauthorized");
}

#[test]
fn cart_add_with_valid_cap_ok() {
    let peer = Peer::with_oracle();
    let svc = CapService::oracle();
    let args = json!({"sku": "x", "qty": 1});
    let tok = svc.mint("Cart.add", &args, None, None).unwrap();
    let i = intent("Cart.add", args, Some(tok));
    let r = peer.handle_intent(&i);
    assert!(r.ok, "{:?}", r.error);
}

#[test]
fn wire_json_intent_through_peer() {
    let peer = Peer::with_oracle();
    let i = intent("Counter.get", json!({}), None);
    let bytes = encode_intent(&i).unwrap();
    let back = decode_intent(&bytes).unwrap();
    let r = peer.handle_intent(&back);
    assert!(r.ok, "{:?}", r.error);
}

#[test]
fn bogus_cap_on_open_action_fails() {
    let peer = Peer::with_oracle();
    let i = intent("Counter.inc", json!({"by": 1}), Some("not-a-real-cap".into()));
    let r = peer.handle_intent(&i);
    assert!(!r.ok);
    assert_eq!(r.error.as_ref().unwrap().code, "unauthorized");
}

#[test]
fn once_cap_replay_unauthorized() {
    let peer = Peer::with_oracle();
    let args = json!({"sku": "x", "qty": 1});
    let tok = peer
        .caps
        .mint_once("Cart.add", &args, None, None, Some("once-itest"))
        .unwrap();
    let r1 = peer.handle_intent(&intent("Cart.add", args.clone(), Some(tok.clone())));
    assert!(r1.ok, "{:?}", r1.error);
    let r2 = peer.handle_intent(&intent("Cart.add", args, Some(tok)));
    assert!(!r2.ok);
    assert_eq!(r2.error.as_ref().unwrap().code, "unauthorized");
    assert!(r2.error.as_ref().unwrap().message.contains("replay"));
}
