//! Peer runtime — hello, submit_intent, on_result queue, revoke.
//!
//! SPEC: `SPEC/architecture/runtime-peer.md`
//! Python twin: `ux_channel.arch.peer.PeerRuntime`
//!
//! Transport is an adapter (HTTP, loopback, outbox). The kernel never
//! speaks X-Channel headers or DOM.

use crate::apply::{ApplyError, PeerApply};
use crate::peer::Peer;
use crate::types::{Intent, ResultDoc, IR_VERSION};
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::sync::Arc;

/// Adapter that delivers an Intent and optionally returns a Result.
pub trait Transport: Send + Sync {
    fn send_intent(&self, intent: &Value) -> Result<Option<Value>, String>;
}

/// Explicit opt-in outbox (SPEC: optional). Records intents; returns no Result.
#[derive(Default)]
pub struct Outbox {
    pub intents: std::sync::Mutex<Vec<Value>>,
}

impl Outbox {
    pub fn take(&self) -> Vec<Value> {
        std::mem::take(&mut *self.intents.lock().expect("outbox"))
    }
}

impl Transport for Outbox {
    fn send_intent(&self, intent: &Value) -> Result<Option<Value>, String> {
        self.intents.lock().expect("outbox").push(intent.clone());
        Ok(None)
    }
}

/// In-process loopback: the Rust `Peer` gate is the host.
/// This is the production join of peer gate + peer runtime (no HTTP).
pub struct Loopback {
    pub peer: Peer,
}

impl Transport for Loopback {
    fn send_intent(&self, intent: &Value) -> Result<Option<Value>, String> {
        let parsed: Intent =
            serde_json::from_value(intent.clone()).map_err(|e| e.to_string())?;
        let doc = self.peer.handle_intent(&parsed);
        serde_json::to_value(doc)
            .map(Some)
            .map_err(|e| e.to_string())
    }
}

/// Peer runtime: profiles + drivers already on `apply`; this layer is
/// hello / submit / queue / revoke.
pub struct PeerRuntime {
    pub apply: PeerApply,
    pub profiles: Vec<String>,
    pub features: Vec<String>,
    queue: VecDeque<Value>,
    busy: bool,
    outbox: bool,
    recorded: Vec<Value>,
    transport: Option<Arc<dyn Transport>>,
}

impl PeerRuntime {
    pub fn new(apply: PeerApply) -> Self {
        Self {
            apply,
            profiles: Vec::new(),
            features: Vec::new(),
            queue: VecDeque::new(),
            busy: false,
            outbox: false,
            recorded: Vec::new(),
            transport: None,
        }
    }

    pub fn with_profiles(mut self, profiles: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.profiles = profiles.into_iter().map(Into::into).collect();
        self
    }

    pub fn with_features(mut self, features: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.features = features.into_iter().map(Into::into).collect();
        self
    }

    /// SPEC: outbox is explicit opt-in.
    pub fn with_outbox(mut self) -> Self {
        self.outbox = true;
        self
    }

    pub fn with_transport(mut self, t: Arc<dyn Transport>) -> Self {
        self.transport = Some(t);
        self
    }

    pub fn hello(&self) -> Value {
        json!({
            "profiles": self.profiles,
            "features": self.features,
            "ir": IR_VERSION,
            "effect_proof": self.apply.proofs_required() || self.apply.has_proof(),
        })
    }

    pub fn on_result(&mut self, result: Value) -> Result<(), ApplyError> {
        self.queue.push_back(result);
        self.drain()
    }

    pub fn on_result_doc(&mut self, doc: &ResultDoc) -> Result<(), ApplyError> {
        let v = serde_json::to_value(doc).unwrap_or_else(|_| json!({"ok": doc.ok, "ops": []}));
        self.on_result(v)
    }

    fn drain(&mut self) -> Result<(), ApplyError> {
        if self.busy {
            return Ok(());
        }
        self.busy = true;
        let mut err = None;
        while let Some(next) = self.queue.pop_front() {
            if let Err(e) = self.apply.apply_result(&next) {
                err = Some(e);
                break;
            }
        }
        self.busy = false;
        match err {
            Some(e) => Err(e),
            None => Ok(()),
        }
    }

    /// Build + send an Intent. Cap travels on the Intent (never inferred).
    pub fn submit_intent(
        &mut self,
        action: &str,
        args: Value,
        cap: Option<&str>,
        request_id: Option<&str>,
    ) -> Result<Value, String> {
        let mut intent = json!({
            "v": IR_VERSION,
            "action": action,
            "args": args,
            "meta": {"hello": self.hello()},
        });
        if let Some(c) = cap {
            intent
                .as_object_mut()
                .expect("intent")
                .insert("cap".into(), json!(c));
        }
        if let Some(rid) = request_id {
            intent
                .as_object_mut()
                .expect("intent")
                .insert("request_id".into(), json!(rid));
        }
        if self.outbox {
            self.recorded.push(intent.clone());
        }
        if let Some(t) = &self.transport {
            match t.send_intent(&intent) {
                Ok(Some(result)) => {
                    self.on_result(result).map_err(|e| e.to_string())?;
                }
                Ok(None) => {}
                Err(e) => return Err(e),
            }
        }
        Ok(intent)
    }

    pub fn recorded(&self) -> &[Value] {
        &self.recorded
    }

    /// Local revoke: gen++, drop queued Results, cancel timers.
    pub fn revoke_local(&mut self) {
        self.apply.bump_gen();
        self.queue.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::apply::PeerApply;
    use crate::drivers::make_web_drivers;
    use crate::peer::Peer;

    #[test]
    fn hello_shape() {
        let apply = PeerApply::new(make_web_drivers());
        let rt = PeerRuntime::new(apply)
            .with_profiles(["web.v1"])
            .with_features(["seq", "invoke"]);
        let h = rt.hello();
        assert_eq!(h["profiles"], json!(["web.v1"]));
        assert_eq!(h["ir"], "1");
        assert_eq!(h["effect_proof"], false);
    }

    #[test]
    fn on_result_applies() {
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply).with_profiles(["web.v1"]);
        rt.on_result(json!({
            "ok": true,
            "ops": [{"op": "toast", "message": "hi"}]
        }))
        .unwrap();
        assert_eq!(rt.apply.ctx.log.len(), 1);
    }

    #[test]
    fn revoke_bumps_gen_and_drops_queue() {
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply);
        let g0 = rt.apply.ctx.gen;
        rt.revoke_local();
        assert_eq!(rt.apply.ctx.gen, g0 + 1);
        assert!(rt.queue.is_empty());
    }

    #[test]
    fn submit_records_when_outbox() {
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply).with_outbox();
        rt.submit_intent("Counter.inc", json!({"by": 1}), None, Some("r1"))
            .unwrap();
        assert_eq!(rt.recorded().len(), 1);
        assert_eq!(rt.recorded()[0]["action"], "Counter.inc");
        assert_eq!(rt.recorded()[0]["meta"]["hello"]["ir"], "1");
    }

    #[test]
    fn loopback_peer_plus_runtime() {
        let gate = Peer::with_oracle();
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply)
            .with_profiles(["web.v1"])
            .with_features(["seq"])
            .with_transport(Arc::new(Loopback { peer: gate }));
        rt.submit_intent("Counter.inc", json!({"by": 1}), None, None)
            .unwrap();
        // Counter.inc returns toast + signal_set; toast driver logs.
        assert!(
            rt.apply
                .ctx
                .log
                .iter()
                .any(|e| e.get(0) == Some(&json!("toast"))),
            "expected toast apply from loopback Result: {:?}",
            rt.apply.ctx.log
        );
    }

    #[test]
    fn loopback_cart_requires_cap() {
        let gate = Peer::with_oracle();
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply).with_transport(Arc::new(Loopback { peer: gate }));
        rt.submit_intent("Cart.add", json!({"sku": "a", "qty": 1}), None, None)
            .unwrap();
        // unauthorized Result: no toast applied (handler never ran)
        assert!(rt.apply.ctx.log.is_empty());
    }

    #[test]
    fn loopback_cart_with_cap_applies_ops() {
        let gate = Peer::with_oracle();
        let args = json!({"sku": "a", "qty": 1});
        let tok = gate.mint_cap("Cart.add", &args, None, None).unwrap();
        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply).with_transport(Arc::new(Loopback { peer: gate }));
        rt.submit_intent("Cart.add", args, Some(&tok), None).unwrap();
        assert!(
            rt.apply
                .ctx
                .log
                .iter()
                .any(|e| e.get(0) == Some(&json!("toast"))),
            "{:?}",
            rt.apply.ctx.log
        );
        assert!(rt
            .apply
            .ctx
            .log
            .iter()
            .any(|e| e.get(0) == Some(&json!("morph"))));
    }
}
