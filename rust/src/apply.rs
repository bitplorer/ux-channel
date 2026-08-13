//! Peer kernel — apply Result.ops. No DOM, no transport.
//!
//! SPEC: `SPEC/architecture/peer-kernel.md`
//! Python twin: `ux_channel.arch.peer.PeerApply`

use crate::proof::ProofService;
use crate::types::ResultDoc;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use thiserror::Error;

pub type DriverFn = Box<dyn Fn(&Value, &mut ApplyCtx) + Send + Sync>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ApplyError {
    #[error("single-flight: apply already in progress")]
    SingleFlight,
}

/// Mutable apply context. Drivers write here; kernel never touches a DOM.
#[derive(Debug, Clone)]
pub struct ApplyCtx {
    pub gen: u64,
    pub session_id: String,
    pub log: Vec<Value>,
    pub timers: HashMap<String, TimerEntry>,
    pub result_ok: Option<bool>,
    pub reject: Option<String>,
}

#[derive(Debug, Clone)]
pub struct TimerEntry {
    pub ms: u64,
    pub gen: u64,
    pub body: Vec<Value>,
}

impl ApplyCtx {
    fn new(session_id: String) -> Self {
        Self {
            gen: 1,
            session_id,
            log: Vec::new(),
            timers: HashMap::new(),
            result_ok: None,
            reject: None,
        }
    }
}

/// Generic apply machine for every peer surface.
pub struct PeerApply {
    drivers: HashMap<String, DriverFn>,
    max_nodes: usize,
    max_depth: usize,
    proof: Option<ProofService>,
    proofs_required: bool,
    session_id: String,
    stamp_check: Option<Box<dyn Fn(&str, &str) -> bool + Send + Sync>>,
    in_flight: AtomicBool,
    pub ctx: ApplyCtx,
}

impl PeerApply {
    pub fn new(drivers: HashMap<String, DriverFn>) -> Self {
        Self::with_session(drivers, "default")
    }

    pub fn with_session(drivers: HashMap<String, DriverFn>, session_id: impl Into<String>) -> Self {
        let session_id = session_id.into();
        Self {
            drivers,
            max_nodes: 256,
            max_depth: 16,
            proof: None,
            proofs_required: false,
            session_id: session_id.clone(),
            stamp_check: None,
            in_flight: AtomicBool::new(false),
            ctx: ApplyCtx::new(session_id),
        }
    }

    pub fn with_limits(mut self, max_nodes: usize, max_depth: usize) -> Self {
        self.max_nodes = max_nodes;
        self.max_depth = max_depth;
        self
    }

    pub fn with_proof(mut self, proof: ProofService, required: bool) -> Self {
        self.proof = Some(proof);
        self.proofs_required = required;
        self
    }

    pub fn proofs_required(&self) -> bool {
        self.proofs_required
    }

    pub fn has_proof(&self) -> bool {
        self.proof.is_some()
    }

    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    pub fn with_stamp_check<F>(mut self, check: F) -> Self
    where
        F: Fn(&str, &str) -> bool + Send + Sync + 'static,
    {
        self.stamp_check = Some(Box::new(check));
        self
    }

    pub fn bump_gen(&mut self) {
        self.ctx.gen += 1;
        self.ctx.timers.clear();
        self.ctx.reject = None;
    }

    pub fn apply_doc(&mut self, doc: &ResultDoc) -> Result<(), ApplyError> {
        let value = serde_json::to_value(doc).unwrap_or_else(|_| json!({"ok": doc.ok, "ops": []}));
        self.apply_result(&value)
    }

    /// applyResult: proof → single-flight → budget → applyOps.
    pub fn apply_result(&mut self, result: &Value) -> Result<(), ApplyError> {
        self.ctx.reject = None;
        if self.proofs_required {
            match &self.proof {
                None => {
                    self.ctx.reject = Some("proof_unavailable".into());
                    return Ok(());
                }
                Some(p) => {
                    if !p.verify_value(result, &self.session_id, self.ctx.gen as i64) {
                        self.ctx.reject = Some("proof".into());
                        return Ok(());
                    }
                }
            }
        }
        if self
            .in_flight
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err(ApplyError::SingleFlight);
        }
        let outcome = (|| {
            let ops = match result.get("ops") {
                Some(Value::Array(a)) => a.clone(),
                _ => Vec::new(),
            };
            if !self.within_budget(&ops) {
                self.ctx.reject = Some("budget".into());
                return Ok(());
            }
            self.ctx.result_ok = result.get("ok").and_then(|v| v.as_bool());
            self.apply_ops_inner(&ops, 0);
            Ok(())
        })();
        self.in_flight.store(false, Ordering::SeqCst);
        outcome
    }

    /// Driver-facing apply of a child list (timer / invoke body). No extra lock.
    pub fn apply_ops(&mut self, ops: &[Value]) {
        self.apply_ops_inner(ops, 0);
    }

    fn within_budget(&self, ops: &[Value]) -> bool {
        fn walk(list: &[Value], d: usize, max_depth: usize, max_nodes: usize, count: &mut usize) -> bool {
            if d > max_depth {
                return false;
            }
            for op in list {
                *count += 1;
                if *count > max_nodes {
                    return false;
                }
                if let Some(Value::Array(kids)) = op.get("ops") {
                    if !walk(kids, d + 1, max_depth, max_nodes, count) {
                        return false;
                    }
                }
            }
            true
        }
        let mut count = 0;
        walk(ops, 0, self.max_depth, self.max_nodes, &mut count)
    }

    fn apply_ops_inner(&mut self, ops: &[Value], depth: usize) {
        if depth > self.max_depth {
            return;
        }
        for op in ops {
            self.apply_op(op, depth);
        }
    }

    fn apply_op(&mut self, op: &Value, depth: usize) {
        let Some(name) = op.get("op").and_then(|v| v.as_str()) else {
            return;
        };
        if name == "seq" {
            if let Some(Value::Array(kids)) = op.get("ops") {
                let kids = kids.clone();
                self.apply_ops_inner(&kids, depth + 1);
            }
            return;
        }
        if name == "invoke" {
            let r#ref = op.get("ref").and_then(|v| v.as_str()).unwrap_or("");
            let method = op.get("method").and_then(|v| v.as_str()).unwrap_or("");
            if let Some(check) = &self.stamp_check {
                if !check(r#ref, method) {
                    self.ctx
                        .log
                        .push(json!(["invoke_denied", r#ref, method]));
                    return;
                }
            }
            let key = format!("invoke:{method}");
            if self.drivers.contains_key(&key) || self.drivers.contains_key("invoke") {
                let name = if self.drivers.contains_key(&key) {
                    key
                } else {
                    "invoke".into()
                };
                let op = op.clone();
                if let Some(fn_) = self.drivers.get(&name) {
                    fn_(&op, &mut self.ctx);
                }
            }
            if let Some(Value::Array(kids)) = op.get("ops") {
                let kids = kids.clone();
                self.apply_ops_inner(&kids, depth + 1);
            }
            return;
        }
        if name == "timer.set" {
            self.apply_timer_set(op);
            return;
        }
        if name == "timer.clear" {
            if let Some(id) = op.get("id").map(value_as_string) {
                self.ctx.timers.remove(&id);
            }
            return;
        }
        if let Some(fn_) = self.drivers.get(name) {
            fn_(op, &mut self.ctx);
        }
    }

    fn apply_timer_set(&mut self, op: &Value) {
        let ms = op
            .get("ms")
            .and_then(|v| v.as_u64().or_else(|| v.as_i64().map(|i| i.max(0) as u64)))
            .unwrap_or(0)
            .min(600_000);
        let id = op
            .get("id")
            .map(value_as_string)
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "t".into());
        let gen = self.ctx.gen;
        let body = match op.get("ops") {
            Some(Value::Array(a)) => a.clone(),
            _ => Vec::new(),
        };
        self.ctx.timers.insert(
            id.clone(),
            TimerEntry {
                ms,
                gen,
                body: body.clone(),
            },
        );
        if ms == 0 {
            self.fire_timer(&id);
        }
    }

    /// Fire a stored timer if gen still matches (tests / event loop).
    pub fn fire_timer(&mut self, id: &str) {
        let Some(t) = self.ctx.timers.get(id).cloned() else {
            return;
        };
        if self.ctx.gen != t.gen {
            return;
        }
        let body = t.body;
        self.apply_ops_inner(&body, 0);
    }
}

fn value_as_string(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::drivers::make_web_drivers;

    fn toast(msg: &str) -> Value {
        json!({"op": "toast", "message": msg, "level": "info"})
    }

    #[test]
    fn seq_applies_children() {
        let mut apply = PeerApply::new(make_web_drivers());
        apply
            .apply_result(&json!({
                "ok": true,
                "ops": [{"op": "seq", "ops": [toast("a"), toast("b")]}]
            }))
            .unwrap();
        let msgs: Vec<_> = apply
            .ctx
            .log
            .iter()
            .filter_map(|e| e.get(1).and_then(|v| v.as_str()).map(|s| s.to_string()))
            .collect();
        assert_eq!(msgs, ["a", "b"]);
    }

    #[test]
    fn budget_rejects() {
        let mut apply = PeerApply::new(make_web_drivers()).with_limits(2, 16);
        apply
            .apply_result(&json!({
                "ok": true,
                "ops": [toast("a"), toast("b"), toast("c")]
            }))
            .unwrap();
        assert_eq!(apply.ctx.reject.as_deref(), Some("budget"));
        assert!(apply.ctx.log.is_empty());
    }

    #[test]
    fn unknown_ops_ignored() {
        let mut apply = PeerApply::new(make_web_drivers());
        apply
            .apply_result(&json!({
                "ok": true,
                "ops": [{"op": "not-a-real-op"}, toast("ok")]
            }))
            .unwrap();
        assert_eq!(apply.ctx.log.len(), 1);
    }

    #[test]
    fn timer_zero_fires() {
        let mut apply = PeerApply::new(make_web_drivers());
        apply
            .apply_result(&json!({
                "ok": true,
                "ops": [{
                    "op": "timer.set",
                    "id": "t0",
                    "ms": 0,
                    "ops": [toast("later")]
                }]
            }))
            .unwrap();
        assert!(apply
            .ctx
            .log
            .iter()
            .any(|e| e.get(1) == Some(&json!("later"))));
    }

    #[test]
    fn invoke_denied_by_stamp() {
        let mut apply = PeerApply::new(make_web_drivers())
            .with_stamp_check(|_r, _m| false);
        apply
            .apply_result(&json!({
                "ok": true,
                "ops": [{"op": "invoke", "ref": "s1", "method": "ping", "ops": [toast("no")]}]
            }))
            .unwrap();
        assert!(apply
            .ctx
            .log
            .iter()
            .any(|e| e.get(0) == Some(&json!("invoke_denied"))));
        assert!(!apply
            .ctx
            .log
            .iter()
            .any(|e| e.get(1) == Some(&json!("no"))));
    }

    #[test]
    fn proof_required_rejects_unsigned() {
        let proof = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut apply = PeerApply::new(make_web_drivers()).with_proof(proof, true);
        apply
            .apply_result(&json!({"ok": true, "ops": [toast("x")]}))
            .unwrap();
        assert_eq!(apply.ctx.reject.as_deref(), Some("proof"));
        assert!(apply.ctx.log.is_empty());
    }

    #[test]
    fn proof_required_accepts_signed() {
        let proof = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut result = json!({"ok": true, "ops": [toast("x")], "error": null});
        proof.sign_value(&mut result, "default", 1).unwrap();
        let mut apply = PeerApply::new(make_web_drivers()).with_proof(proof, true);
        apply.apply_result(&result).unwrap();
        assert_eq!(apply.ctx.reject, None);
        assert_eq!(apply.ctx.log.len(), 1);
    }

    #[test]
    fn single_flight() {
        let mut apply = PeerApply::new(make_web_drivers());
        apply
            .in_flight
            .store(true, std::sync::atomic::Ordering::SeqCst);
        let err = apply
            .apply_result(&json!({"ok": true, "ops": [toast("x")]}))
            .unwrap_err();
        assert_eq!(err, ApplyError::SingleFlight);
    }
}

#[cfg(test)]
mod prop_tests {
    use super::*;
    use crate::drivers::make_web_drivers;
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn budget_rejects_over_limit(n in 1usize..16) {
            let mut apply = PeerApply::new(make_web_drivers()).with_limits(n, 16);
            let ops: Vec<Value> = (0..=n)
                .map(|i| json!({"op": "toast", "message": i.to_string()}))
                .collect();
            apply.apply_result(&json!({"ok": true, "ops": ops})).unwrap();
            prop_assert_eq!(apply.ctx.reject.as_deref(), Some("budget"));
            prop_assert!(apply.ctx.log.is_empty());
        }

        #[test]
        fn flow_meta_never_blocks(msg in ".{1,16}") {
            let mut apply = PeerApply::new(make_web_drivers());
            apply
                .apply_result(&json!({
                    "ok": true,
                    "ops": [{"op": "toast", "message": msg}],
                    "meta": {"flow_id": "flow_x", "not_a_cap": true}
                }))
                .unwrap();
            prop_assert!(apply.ctx.reject.is_none());
            prop_assert!(!apply.ctx.log.is_empty());
        }
    }
}
