//! JSON encode/decode for the IR (`application/ux-channel+json` floor).
//!
//! Strict decode validates IR rules. Lenient parse is only used to recover
//! `action` / `request_id` for error Result.meta — never to bypass caps.

use crate::types::{Intent, ResultDoc};
use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum WireError {
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("validation: {0}")]
    Validation(String),
}

/// Strict: deserialize + IR validation.
pub fn decode_intent(data: &[u8]) -> Result<Intent, WireError> {
    let intent: Intent = serde_json::from_slice(data)?;
    intent.validate().map_err(WireError::Validation)?;
    Ok(intent)
}

/// Lenient: deserialize without IR validation (error-reporting only).
pub fn parse_intent_lenient(data: &[u8]) -> Result<Intent, WireError> {
    Ok(serde_json::from_slice(data)?)
}

pub fn encode_intent(intent: &Intent) -> Result<Vec<u8>, WireError> {
    intent.validate().map_err(WireError::Validation)?;
    Ok(serde_json::to_vec(intent)?)
}

pub fn decode_result(data: &[u8]) -> Result<ResultDoc, WireError> {
    let doc: ResultDoc = serde_json::from_slice(data)?;
    doc.validate().map_err(WireError::Validation)?;
    Ok(doc)
}

pub fn encode_result(doc: &ResultDoc) -> Result<Vec<u8>, WireError> {
    doc.validate().map_err(WireError::Validation)?;
    Ok(serde_json::to_vec(doc)?)
}

/// Decode any JSON value (handshake / unknown docs).
pub fn decode_value(data: &[u8]) -> Result<Value, WireError> {
    Ok(serde_json::from_slice(data)?)
}

/// Canonical compact JSON (sorted keys) for stable comparison in tests.
pub fn canonical_json(value: &Value) -> Result<String, WireError> {
    let sorted = sort_value(value.clone());
    Ok(serde_json::to_string(&sorted)?)
}

fn sort_value(v: Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            let mut out = serde_json::Map::new();
            for k in keys {
                if let Some(val) = map.get(&k) {
                    out.insert(k, sort_value(val.clone()));
                }
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.into_iter().map(sort_value).collect()),
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Intent, Op, ResultDoc, IR_VERSION};
    use serde_json::json;
    use std::collections::HashMap;

    #[test]
    fn intent_roundtrip_json() {
        let mut args = HashMap::new();
        args.insert("n".into(), json!(1));
        let intent = Intent {
            v: IR_VERSION.into(),
            action: "Counter.inc".into(),
            args: Some(args),
            cap: None,
            target: None,
            request_id: Some("r1".into()),
            form: None,
            idempotency_key: None,
            extra: HashMap::new(),
        };
        let bytes = encode_intent(&intent).unwrap();
        let back = decode_intent(&bytes).unwrap();
        assert_eq!(back.action, "Counter.inc");
        assert_eq!(back.v, IR_VERSION);
    }

    #[test]
    fn result_roundtrip_json() {
        let mut fields = HashMap::new();
        fields.insert("message".into(), json!("hi"));
        let doc = ResultDoc {
            ok: true,
            ops: vec![Op {
                op: "toast".into(),
                fields,
            }],
            error: None,
            meta: None,
            trace: None,
        };
        let bytes = encode_result(&doc).unwrap();
        let back = decode_result(&bytes).unwrap();
        assert!(back.ok);
        assert_eq!(back.ops.len(), 1);
        assert_eq!(back.ops[0].op, "toast");
    }

    #[test]
    fn canonical_json_sorts_keys() {
        let v = json!({"b": 1, "a": 2});
        let c = canonical_json(&v).unwrap();
        assert_eq!(c, r#"{"a":2,"b":1}"#);
    }
}

#[cfg(test)]
mod prop_tests {
    use super::*;
    use crate::types::{Intent, IR_VERSION};
    use proptest::prelude::*;
    use serde_json::{json, Map, Value};
    use std::collections::HashMap;

    fn leaf() -> impl Strategy<Value = Value> {
        prop_oneof![
            Just(Value::Null),
            any::<bool>().prop_map(Value::Bool),
            (-100i64..100i64).prop_map(|n| json!(n)),
            "[a-z0-9]{0,12}".prop_map(|s| json!(s)),
        ]
    }

    proptest! {
        #[test]
        fn canonical_json_stable(keys in prop::collection::vec("[a-z]{1,4}", 0..5), vals in prop::collection::vec(leaf(), 0..5)) {
            let n = keys.len().min(vals.len());
            let mut map = Map::new();
            for i in 0..n {
                map.insert(keys[i].clone(), vals[i].clone());
            }
            let v = Value::Object(map);
            let c1 = canonical_json(&v).unwrap();
            let c2 = canonical_json(&v).unwrap();
            prop_assert_eq!(c1, c2);
        }

        #[test]
        fn intent_json_roundtrip(action in "[A-Za-z][A-Za-z0-9_.]{0,20}") {
            let mut args = HashMap::new();
            args.insert("x".into(), json!(1));
            let intent = Intent {
                v: IR_VERSION.into(),
                action: action.clone(),
                args: Some(args),
                cap: None,
                target: None,
                request_id: None,
                form: None,
                idempotency_key: None,
                extra: HashMap::new(),
            };
            let bytes = encode_intent(&intent).expect("enc");
            let back = decode_intent(&bytes).expect("dec");
            prop_assert_eq!(back.action, action);
            prop_assert_eq!(back.v, IR_VERSION);
        }
    }
}
