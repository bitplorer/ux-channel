//! Host kernel + host runtime.
//!
//! Kernel: Cap + nonce + registry + project + proof (this crate's modules).
//! Runtime: sessions, hello, handle_intent, revoke, health.
//! SPEC: `host-kernel.md` · `runtime-host.md`

use crate::cap::{CapError, CapService};
use crate::effects::EffectGraph;
use crate::flow::{attach_flow_meta, FlowStore};
use crate::nonce::{MemoryNonceStore, NonceStore};
use crate::project::project;
use crate::proof::ProofService;
use crate::registry::{dispatch_typed, ActionOut, Registry};
use crate::stamps::StampTable;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum HostError {
    #[error("prod refuse: oracle/demo secret")]
    OracleInProd,
    #[error("Cap secret must differ from proof secret")]
    SharedSecrets,
    #[error("proofs=require needs a proof_secret")]
    ProofRequired,
    #[error("{0}")]
    Config(String),
    #[error("{0}")]
    Cap(#[from] CapError),
    #[error("{0}")]
    Proof(String),
}

#[derive(Debug, Clone)]
pub struct HostConfig {
    pub effects: String,
    pub proofs: String,
    pub flow: String,
    pub demo_mode: bool,
    pub require_cap: bool,
}

impl Default for HostConfig {
    fn default() -> Self {
        Self {
            effects: "auto".into(),
            proofs: "auto".into(),
            flow: "auto".into(),
            demo_mode: false,
            require_cap: true,
        }
    }
}

impl HostConfig {
    pub fn validate(&self) -> Result<(), HostError> {
        match self.effects.as_str() {
            "auto" | "classic" => {}
            other => return Err(HostError::Config(format!("effects must be auto|classic, got {other}"))),
        }
        match self.proofs.as_str() {
            "auto" | "require" | "off" => {}
            other => return Err(HostError::Config(format!("proofs must be auto|require|off, got {other}"))),
        }
        match self.flow.as_str() {
            "auto" | "off" => {}
            other => return Err(HostError::Config(format!("flow must be auto|off, got {other}"))),
        }
        Ok(())
    }

    pub fn demo() -> Self {
        Self {
            demo_mode: true,
            require_cap: false,
            ..Self::default()
        }
    }
}

#[derive(Debug, Clone)]
pub struct Session {
    pub session_id: String,
    pub gen: u64,
    pub peer_hello: Value,
}

/// Host runtime — architecture pair to `PeerRuntime`.
pub struct HostRuntime {
    pub config: HostConfig,
    pub caps: CapService,
    pub proofs: ProofService,
    pub stamps: StampTable,
    pub flows: FlowStore,
    pub registry: Registry,
    sessions: HashMap<String, Session>,
}

impl HostRuntime {
    pub fn new(
        cap_secret: impl AsRef<[u8]>,
        proof_secret: impl AsRef<[u8]>,
        config: HostConfig,
    ) -> Result<Self, HostError> {
        config.validate()?;
        let cap_secret = cap_secret.as_ref();
        let proof_secret = proof_secret.as_ref();
        if !config.demo_mode && cap_secret.windows(b"conformance-oracle".len()).any(|w| w == b"conformance-oracle")
        {
            return Err(HostError::OracleInProd);
        }
        if cap_secret == proof_secret {
            return Err(HostError::SharedSecrets);
        }
        if config.proofs == "require" && proof_secret.len() < 16 {
            return Err(HostError::ProofRequired);
        }
        let store: Arc<dyn NonceStore> = Arc::new(MemoryNonceStore::default());
        let caps = CapService::new(cap_secret, 3600)?.with_nonce_store(store);
        let proofs = ProofService::new(proof_secret).map_err(|e| HostError::Proof(e.to_string()))?;
        let require_cap = config.require_cap;
        Ok(Self {
            config,
            caps,
            proofs,
            stamps: StampTable::default(),
            flows: FlowStore::default(),
            registry: Registry::new(require_cap),
            sessions: HashMap::new(),
        })
    }

    pub fn register<F>(&mut self, action: impl Into<String>, handler: F)
    where
        F: Fn(&Value) -> ActionOut + Send + Sync + 'static,
    {
        self.registry.register(action, handler);
    }

    pub fn set_hello(&mut self, session_id: &str, hello: Value) {
        let s = self
            .sessions
            .entry(session_id.into())
            .or_insert_with(|| Session {
                session_id: session_id.into(),
                gen: 1,
                peer_hello: json!({}),
            });
        s.peer_hello = sanitize_hello(&hello);
    }

    pub fn revoke(&mut self, session_id: &str) -> u64 {
        let s = self
            .sessions
            .entry(session_id.into())
            .or_insert_with(|| Session {
                session_id: session_id.into(),
                gen: 1,
                peer_hello: json!({}),
            });
        s.gen += 1;
        self.stamps.on_revoke(session_id);
        s.gen
    }

    pub fn grant_stamp(
        &mut self,
        session_id: &str,
        kind: &str,
        methods: impl IntoIterator<Item = impl Into<String>>,
    ) -> String {
        let gen = self.session(session_id).gen;
        self.stamps.grant(session_id, gen, kind, methods).stamp_id
    }

    pub fn emit_from_graph(
        &mut self,
        g: &EffectGraph,
        session_id: &str,
        ok: bool,
        flow_id: Option<&str>,
        step: Option<i64>,
        meta: Option<Value>,
    ) -> Result<Value, HostError> {
        let hello = self.session(session_id).peer_hello.clone();
        let gen = self.session(session_id).gen;
        let ops = project(g, &hello, &self.config.effects).map_err(HostError::Config)?;
        let mut result = json!({
            "ok": ok,
            "ops": ops,
            "meta": meta.unwrap_or_else(|| json!({})),
        });
        if let Some(fid) = flow_id {
            if self.config.flow == "auto" {
                attach_flow_meta(&mut result, fid, step, "auto").map_err(HostError::Config)?;
            }
        }
        if self.need_proof(session_id) {
            self.proofs
                .sign_value(&mut result, session_id, gen as i64)
                .map_err(|e| HostError::Proof(e.to_string()))?;
        }
        Ok(result)
    }

    pub fn handle_intent(&mut self, intent: &Value, session_id: &str) -> Result<Value, HostError> {
        self.session(session_id);
        if let Some(hello) = intent.get("meta").and_then(|m| m.get("hello")) {
            self.set_hello(session_id, hello.clone());
        }
        let (mut result, graph) = dispatch_typed(&self.registry, &self.caps, intent);
        if let Some(g) = graph {
            let flow_id = result
                .get("meta")
                .and_then(|m| m.get("flow_id"))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let step = result
                .get("meta")
                .and_then(|m| m.get("step"))
                .and_then(|v| v.as_i64());
            let meta = result.get("meta").cloned();
            let ok = result.get("ok").and_then(|v| v.as_bool()).unwrap_or(true);
            let mut projected =
                self.emit_from_graph(&g, session_id, ok, flow_id.as_deref(), step, meta)?;
            if let Some(err) = result.get("error") {
                projected["error"] = err.clone();
            }
            return Ok(projected);
        }
        if self.need_proof(session_id) && result.get("ops").is_some() {
            let gen = self.session(session_id).gen as i64;
            self.proofs
                .sign_value(&mut result, session_id, gen)
                .map_err(|e| HostError::Proof(e.to_string()))?;
        }
        if self.config.flow == "auto" {
            let fid = intent
                .get("args")
                .and_then(|a| a.get("flow_id"))
                .or_else(|| intent.get("meta").and_then(|m| m.get("flow_id")))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let has = result
                .get("meta")
                .and_then(|m| m.get("flow_id"))
                .is_some();
            if let Some(fid) = fid {
                if !has {
                    attach_flow_meta(&mut result, &fid, None, "auto").map_err(HostError::Config)?;
                }
            }
        }
        Ok(result)
    }

    pub fn mint(&self, action: &str, args: &Value, once: bool) -> Result<String, CapError> {
        if once {
            self.caps.mint_once(action, args, None, None, None)
        } else {
            self.caps.mint(action, args, None, None)
        }
    }

    pub fn health(&self) -> Value {
        json!({
            "demo_mode": self.config.demo_mode,
            "effects": self.config.effects,
            "proofs": self.config.proofs,
            "flow": self.config.flow,
            "sessions": self.sessions.len(),
            "once_jti_enforced": self.caps.has_nonce(),
        })
    }

    fn need_proof(&self, session_id: &str) -> bool {
        if self.config.proofs == "off" {
            return false;
        }
        let hello = self
            .sessions
            .get(session_id)
            .map(|s| &s.peer_hello)
            .cloned()
            .unwrap_or(json!({}));
        hello.get("effect_proof").and_then(|v| v.as_bool()).unwrap_or(false)
            || self.config.proofs == "require"
    }

    fn session(&mut self, session_id: &str) -> &mut Session {
        self.sessions.entry(session_id.into()).or_insert_with(|| Session {
            session_id: session_id.into(),
            gen: 1,
            peer_hello: json!({}),
        })
    }
}

fn sanitize_hello(hello: &Value) -> Value {
    let mut out = serde_json::Map::new();
    if let Some(Value::Array(p)) = hello.get("profiles") {
        out.insert(
            "profiles".into(),
            json!(p.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>()),
        );
    }
    if let Some(Value::Array(f)) = hello.get("features") {
        out.insert(
            "features".into(),
            json!(f.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>()),
        );
    }
    if hello.get("effect_proof").is_some() {
        out.insert(
            "effect_proof".into(),
            json!(hello.get("effect_proof").and_then(|v| v.as_bool()).unwrap_or(false)),
        );
    }
    Value::Object(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::apply::PeerApply;
    use crate::drivers::make_web_drivers;
    use crate::effects::{graph, seq, toast};
    use crate::registry::ActionOut;
    use crate::runtime::PeerRuntime;

    fn host(cfg: HostConfig) -> HostRuntime {
        HostRuntime::new(b"0123456789abcdef", b"proof-secret-16b!", cfg).unwrap()
    }

    #[test]
    fn refuses_oracle_in_prod() {
        let err = HostRuntime::new(
            b"conformance-oracle-secret-32chars!!",
            b"proof-secret-16b!",
            HostConfig::default(),
        );
        assert!(matches!(err, Err(HostError::OracleInProd)));
    }

    #[test]
    fn secrets_must_differ() {
        let err = HostRuntime::new(b"0123456789abcdef", b"0123456789abcdef", HostConfig::demo());
        assert!(matches!(err, Err(HostError::SharedSecrets)));
    }

    #[test]
    fn present_cap_must_verify() {
        let mut h = host(HostConfig::demo());
        h.registry.open_actions.insert("Open.ping".into());
        h.register("Open.ping", |_| {
            ActionOut::Result(json!({"ok": true, "ops": [{"op": "toast", "message": "pong"}]}))
        });
        let bad = h
            .handle_intent(
                &json!({"action": "Open.ping", "args": {}, "cap": "bogus"}),
                "s1",
            )
            .unwrap();
        assert_eq!(bad["ok"], false);
        assert_eq!(bad["error"]["code"], "unauthorized");
    }

    #[test]
    fn once_replay_fails() {
        let h = host(HostConfig::demo());
        let tok = h.mint("Order.pay", &json!({"id": 1}), true).unwrap();
        h.caps.verify(&tok, "Order.pay", &json!({"id": 1})).unwrap();
        assert!(h.caps.verify(&tok, "Order.pay", &json!({"id": 1})).is_err());
    }

    #[test]
    fn project_and_peer_apply_with_flow() {
        let mut h = host(HostConfig {
            effects: "auto".into(),
            proofs: "off".into(),
            flow: "auto".into(),
            demo_mode: true,
            require_cap: false,
        });
        h.set_hello("s1", json!({"profiles": ["web.v1"], "features": ["seq"]}));
        let g = graph([seq([toast("a"), toast("b")])]);
        let rec = h.flows.start("checkout").unwrap();
        let result = h
            .emit_from_graph(&g, "s1", true, Some(&rec.flow_id), Some(1), None)
            .unwrap();
        assert_eq!(result["ops"][0]["op"], "seq");
        assert!(result["meta"]["flow_id"].as_str().unwrap().starts_with("flow_"));

        let apply = PeerApply::new(make_web_drivers());
        let mut rt = PeerRuntime::new(apply)
            .with_profiles(["web.v1"])
            .with_features(["seq"]);
        rt.on_result(result).unwrap();
        let msgs: Vec<_> = rt
            .apply
            .ctx
            .log
            .iter()
            .filter_map(|e| e.get(1).and_then(|v| v.as_str()).map(|s| s.to_string()))
            .collect();
        assert_eq!(msgs, ["a", "b"]);
    }

    #[test]
    fn proofs_require_unsigned_peer_applies_nothing() {
        let mut h = host(HostConfig {
            proofs: "require".into(),
            demo_mode: true,
            require_cap: false,
            ..HostConfig::default()
        });
        h.set_hello("s1", json!({"effect_proof": true, "profiles": ["web.v1"]}));
        let result = h
            .emit_from_graph(&graph([toast("x")]), "s1", true, None, None, None)
            .unwrap();
        assert!(result["meta"]["effect"].is_object());

        let proof = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut apply = PeerApply::with_session(make_web_drivers(), "s1").with_proof(proof, true);
        apply.apply_result(&result).unwrap();
        assert_eq!(apply.ctx.log.len(), 1);

        let mut forged = result.clone();
        forged["ops"] = json!([{"op": "toast", "message": "pwn"}]);
        let proof = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut apply = PeerApply::with_session(make_web_drivers(), "s1").with_proof(proof, true);
        apply.apply_result(&forged).unwrap();
        assert_eq!(apply.ctx.reject.as_deref(), Some("proof"));
        assert!(apply.ctx.log.is_empty());
    }

    #[test]
    fn handle_intent_projects_graph() {
        let mut h = host(HostConfig {
            effects: "auto".into(),
            proofs: "off".into(),
            flow: "off".into(),
            demo_mode: true,
            require_cap: false,
        });
        h.set_hello("s1", json!({"profiles": ["web.v1"], "features": ["seq"]}));
        h.register("Demo.hi", |_| ActionOut::Graph(graph([seq([toast("a"), toast("b")])])));
        let r = h
            .handle_intent(&json!({"action": "Demo.hi", "args": {}}), "s1")
            .unwrap();
        assert_eq!(r["ops"][0]["op"], "seq");
    }

    #[test]
    fn classic_clients_stay_on_floor() {
        let mut h = host(HostConfig {
            effects: "auto".into(),
            proofs: "off".into(),
            demo_mode: true,
            require_cap: false,
            ..HostConfig::default()
        });
        h.register("Demo.hi", |_| ActionOut::Graph(graph([seq([toast("a"), toast("b")])])));
        let r = h
            .handle_intent(&json!({"action": "Demo.hi", "args": {}}), "classic")
            .unwrap();
        assert_eq!(r["ops"][0]["op"], "toast");
        assert_eq!(r["ops"][1]["op"], "toast");
    }

    #[test]
    fn handler_panic_is_internal() {
        let mut h = host(HostConfig::demo());
        h.register("Boom.go", |_| panic!("explode"));
        let r = h
            .handle_intent(&json!({"action": "Boom.go", "args": {}}), "s")
            .unwrap();
        assert_eq!(r["ok"], false);
        assert_eq!(r["error"]["code"], "internal");
        assert_eq!(r["ops"], json!([]));
    }

    #[test]
    fn health_advertises_once() {
        let h = host(HostConfig::demo());
        let health = h.health();
        assert_eq!(health["once_jti_enforced"], true);
        assert_eq!(health["demo_mode"], true);
    }
}
