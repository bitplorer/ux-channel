//! Flow correlation only — never authority.
//! SPEC: `SPEC/architecture/flow.md` · ADR 0007.

use hmac::{Hmac, Mac};
use serde_json::Value;
use sha2::Sha256;
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum FlowError {
    #[error("unknown flow {0}")]
    Unknown(String),
    #[error("flow not open ({0})")]
    NotOpen(String),
    #[error("flow store full")]
    Full,
}

#[derive(Debug, Clone)]
pub struct FlowRecord {
    pub flow_id: String,
    pub kind: String,
    pub step: i64,
    pub status: String,
}

pub struct FlowStore {
    rows: Mutex<HashMap<String, FlowRecord>>,
    max_rows: usize,
}

impl Default for FlowStore {
    fn default() -> Self {
        Self {
            rows: Mutex::new(HashMap::new()),
            max_rows: 50_000,
        }
    }
}

impl FlowStore {
    pub fn start(&self, kind: &str) -> Result<FlowRecord, FlowError> {
        let flow_id = new_flow_id("flow");
        let rec = FlowRecord {
            flow_id: flow_id.clone(),
            kind: kind.into(),
            step: 1,
            status: "open".into(),
        };
        let mut g = self.rows.lock().expect("flows");
        if g.len() >= self.max_rows {
            return Err(FlowError::Full);
        }
        g.insert(flow_id, rec.clone());
        Ok(rec)
    }

    pub fn get(&self, flow_id: &str) -> Option<FlowRecord> {
        self.rows.lock().expect("flows").get(flow_id).cloned()
    }

    pub fn advance(&self, flow_id: &str) -> Result<FlowRecord, FlowError> {
        let mut g = self.rows.lock().expect("flows");
        let rec = g.get_mut(flow_id).ok_or_else(|| FlowError::Unknown(flow_id.into()))?;
        if rec.status != "open" {
            return Err(FlowError::NotOpen(rec.status.clone()));
        }
        rec.step += 1;
        Ok(rec.clone())
    }
}

pub fn new_flow_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mut mac = HmacSha256::new_from_slice(b"uxc-flow").expect("hmac");
    mac.update(&nanos.to_be_bytes());
    let out = mac.finalize().into_bytes();
    format!("{}_{}", prefix, hex::encode(&out[..9]))
}

/// Attach correlation only. Does not authorize.
pub fn attach_flow_meta(result: &mut Value, flow_id: &str, step: Option<i64>, flow_mode: &str) -> Result<(), String> {
    if flow_mode == "off" {
        return Ok(());
    }
    if flow_mode != "auto" {
        return Err("flow_mode must be \"auto\" or \"off\"".into());
    }
    let meta = result
        .as_object_mut()
        .ok_or("result must be object")?
        .entry("meta")
        .or_insert_with(|| serde_json::json!({}));
    if !meta.is_object() {
        *meta = serde_json::json!({});
    }
    let m = meta.as_object_mut().unwrap();
    m.insert("flow_id".into(), Value::String(flow_id.into()));
    if let Some(s) = step {
        m.insert("step".into(), Value::from(s));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unknown_flow_is_explicit() {
        let store = FlowStore::default();
        assert!(matches!(store.advance("missing"), Err(FlowError::Unknown(_))));
    }
}
