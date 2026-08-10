//! Peer request handling: Intent → (cap verify) → action → Result.
//!
//! Caps authorize; transports only deliver.
//!
//! Cap policy (this peer):
//! - `Cart.add` always requires a valid cap.
//! - If any Intent carries a `cap` field, it is verified against action+args
//!   (present-cap-must-verify — never silently ignored).

use crate::actions;
use crate::cap::{CapError, CapService};
use crate::types::{ErrorObject, Intent, ResultDoc};
use crate::wire_json::{decode_intent, encode_result, parse_intent_lenient, WireError};
use serde_json::{json, Value};
use std::collections::HashMap;

/// Actions that require a capability token on this peer.
const CAP_REQUIRED: &[&str] = &["Cart.add"];

#[derive(Debug)]
pub struct Peer {
    pub caps: CapService,
    pub name: String,
}

impl Peer {
    pub fn with_oracle() -> Self {
        Self {
            caps: CapService::oracle(),
            name: "ux_channel_rs".into(),
        }
    }

    pub fn new(caps: CapService) -> Self {
        Self {
            caps,
            name: "ux_channel_rs".into(),
        }
    }

    /// Full path: bytes in → Result bytes out (JSON floor).
    ///
    /// Wire/parse failures are converted into a Result { ok:false } so clients
    /// always see a stable IR shape (never a bare HTTP-only error body).
    pub fn handle_json(&self, body: &[u8]) -> Result<Vec<u8>, WireError> {
        let result = match decode_intent(body) {
            Ok(intent) => self.handle_intent(&intent),
            Err(e) => self.wire_fail(body, e),
        };
        encode_result(&result)
    }

    pub fn handle_intent(&self, intent: &Intent) -> ResultDoc {
        if let Err(e) = intent.validate() {
            return fail(
                "validation",
                e,
                intent.action.as_str(),
                intent.request_id.as_deref(),
            );
        }

        // Cap gate: required actions OR any present cap must verify.
        if CAP_REQUIRED.contains(&intent.action.as_str()) || intent.cap.is_some() {
            match self.verify_cap(intent) {
                Ok(()) => {}
                Err(err) => {
                    return fail(
                        err.code(),
                        err.to_string(),
                        &intent.action,
                        intent.request_id.as_deref(),
                    );
                }
            }
        }

        let mut result = actions::dispatch(intent.action.as_str(), intent.args.as_ref());
        if let Some(rid) = &intent.request_id {
            let meta = result.meta.get_or_insert_with(HashMap::new);
            meta.insert("request_id".into(), json!(rid));
        }
        let meta = result.meta.get_or_insert_with(HashMap::new);
        meta.insert("peer".into(), json!(self.name));
        result
    }

    fn verify_cap(&self, intent: &Intent) -> Result<(), CapError> {
        let token = intent.cap.as_deref().ok_or(CapError::Missing)?;
        if token.is_empty() {
            return Err(CapError::Missing);
        }
        let args_val = args_to_value(intent.args.as_ref());
        self.caps
            .verify(token, &intent.action, &args_val)
            .map(|_| ())
    }

    /// Dev helper: mint a cap for sealed args (same secret as verifier).
    pub fn mint_cap(
        &self,
        action: &str,
        args: &Value,
        sub: Option<&str>,
        scopes: Option<&[String]>,
    ) -> Result<String, CapError> {
        self.caps.mint(action, args, sub, scopes)
    }

    /// Build a Result for wire-level failures, preserving action when parseable.
    fn wire_fail(&self, body: &[u8], err: WireError) -> ResultDoc {
        let (action, request_id) = match parse_intent_lenient(body) {
            Ok(i) => (
                if i.action.is_empty() {
                    "unknown".into()
                } else {
                    i.action
                },
                i.request_id,
            ),
            Err(_) => ("unknown".into(), None),
        };
        let code = match &err {
            WireError::Validation(_) => "validation",
            WireError::Json(_) => "validation",
        };
        fail(
            code,
            err.to_string(),
            &action,
            request_id.as_deref(),
        )
    }
}

fn args_to_value(args: Option<&HashMap<String, Value>>) -> Value {
    match args {
        Some(map) => {
            let mut obj = serde_json::Map::new();
            for (k, v) in map {
                obj.insert(k.clone(), v.clone());
            }
            Value::Object(obj)
        }
        None => json!({}),
    }
}

fn fail(code: &str, message: String, action: &str, request_id: Option<&str>) -> ResultDoc {
    let mut meta = HashMap::from([
        ("action".into(), json!(action)),
        ("runtime".into(), json!("ux_channel_rs")),
    ]);
    if let Some(rid) = request_id {
        meta.insert("request_id".into(), json!(rid));
    }
    ResultDoc {
        ok: false,
        ops: vec![],
        error: Some(ErrorObject {
            code: code.into(),
            message,
            fields: None,
            retryable: Some(false),
            details: None,
        }),
        meta: Some(meta),
        trace: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::actions::reset_counter;
    use serde_json::json;

    #[test]
    fn cart_missing_cap_is_unauthorized_missing() {
        let peer = Peer::with_oracle();
        let body = serde_json::to_vec(&json!({
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "a", "qty": 1}
        }))
        .unwrap();
        let out = peer.handle_json(&body).unwrap();
        let v: Value = serde_json::from_slice(&out).unwrap();
        assert_eq!(v["ok"], false);
        assert_eq!(v["error"]["code"], "unauthorized");
        assert!(v["error"]["message"].as_str().unwrap().contains("required"));
    }

    #[test]
    fn wrong_ir_version_preserves_action() {
        let peer = Peer::with_oracle();
        let body = serde_json::to_vec(&json!({
            "v": "2",
            "action": "Counter.inc",
            "args": {}
        }))
        .unwrap();
        let out = peer.handle_json(&body).unwrap();
        let v: Value = serde_json::from_slice(&out).unwrap();
        assert_eq!(v["ok"], false);
        assert_eq!(v["error"]["code"], "validation");
        assert_eq!(v["meta"]["action"], "Counter.inc");
    }

    #[test]
    fn present_cap_must_verify_even_on_open_action() {
        let peer = Peer::with_oracle();
        let body = serde_json::to_vec(&json!({
            "v": "1",
            "action": "Counter.inc",
            "args": {"by": 1},
            "cap": "not.real"
        }))
        .unwrap();
        let out = peer.handle_json(&body).unwrap();
        let v: Value = serde_json::from_slice(&out).unwrap();
        assert_eq!(v["ok"], false);
        assert_eq!(v["error"]["code"], "unauthorized");
    }

    #[test]
    fn counter_inc_ok() {
        reset_counter();
        let peer = Peer::with_oracle();
        let body = serde_json::to_vec(&json!({
            "v": "1",
            "action": "Counter.inc",
            "args": {"by": 2},
            "request_id": "t1"
        }))
        .unwrap();
        let out = peer.handle_json(&body).unwrap();
        let v: Value = serde_json::from_slice(&out).unwrap();
        assert_eq!(v["ok"], true);
        assert_eq!(v["meta"]["request_id"], "t1");
        assert_eq!(v["meta"]["peer"], "ux_channel_rs");
    }
}
