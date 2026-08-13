//! Host-kernel registry: present-cap-must-verify, then handler.
//! SPEC: `SPEC/architecture/host-kernel.md` dispatch order 1–5.

use crate::cap::{CapError, CapService};
use crate::effects::EffectGraph;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::panic::{catch_unwind, AssertUnwindSafe};

pub enum ActionOut {
    Result(Value),
    Graph(EffectGraph),
}

type Handler = Box<dyn Fn(&Value) -> ActionOut + Send + Sync>;

pub struct Registry {
    handlers: HashMap<String, Handler>,
    pub require_cap: bool,
    pub open_actions: HashSet<String>,
}

impl Registry {
    pub fn new(require_cap: bool) -> Self {
        Self {
            handlers: HashMap::new(),
            require_cap,
            open_actions: HashSet::new(),
        }
    }

    pub fn register<F>(&mut self, action: impl Into<String>, handler: F)
    where
        F: Fn(&Value) -> ActionOut + Send + Sync + 'static,
    {
        self.handlers.insert(action.into(), Box::new(handler));
    }
}

fn fail(code: &str, message: impl Into<String>, meta: Value) -> Value {
    json!({
        "ok": false,
        "ops": [],
        "error": {"code": code, "message": message.into()},
        "meta": meta,
    })
}

fn cap_message(e: &CapError) -> String {
    e.to_string()
}

/// Dispatch that preserves a typed graph for the host runtime.
pub fn dispatch_typed(
    registry: &Registry,
    caps: &CapService,
    intent: &Value,
) -> (Value, Option<EffectGraph>) {
    let action = intent
        .get("action")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let args = intent.get("args").cloned().unwrap_or_else(|| json!({}));
    let cap_token = intent.get("cap").and_then(|v| v.as_str());
    let mut meta = json!({"action": action});
    if let Some(rid) = intent.get("request_id") {
        meta["request_id"] = rid.clone();
    }

    if !registry.handlers.contains_key(&action) {
        return (
            fail("not_found", format!("unknown action {action}"), meta),
            None,
        );
    }

    let needs_cap = registry.require_cap && !registry.open_actions.contains(&action);
    if needs_cap || cap_token.is_some() {
        let Some(token) = cap_token else {
            return (fail("unauthorized", "missing capability", meta), None);
        };
        if let Err(e) = caps.verify(token, &action, &args) {
            return (fail("unauthorized", cap_message(&e), meta), None);
        }
    }

    let handler = &registry.handlers[&action];
    match catch_unwind(AssertUnwindSafe(|| handler(&args))) {
        Err(_) => (fail("internal", "handler failed: panic", meta), None),
        Ok(ActionOut::Graph(g)) => (json!({"ok": true, "ops": [], "meta": meta}), Some(g)),
        Ok(ActionOut::Result(mut result)) => {
            if !result.is_object() {
                result = json!({"ok": true, "ops": []});
            }
            let obj = result.as_object_mut().unwrap();
            obj.entry("ok").or_insert(json!(true));
            obj.entry("ops").or_insert(json!([]));
            let mut m = obj.get("meta").cloned().unwrap_or_else(|| json!({}));
            if let Some(dst) = m.as_object_mut() {
                if let Some(src) = meta.as_object() {
                    for (k, v) in src {
                        dst.insert(k.clone(), v.clone());
                    }
                }
            }
            obj.insert("meta".into(), m);
            (result, None)
        }
    }
}
