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
