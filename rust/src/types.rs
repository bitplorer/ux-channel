//! Core IR types for ux-channel 0.1 (Intent / Result / Op).
//! Matches SPEC/intent-result-ops.md and conformance vectors.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Protocol major version label.
pub const IR_VERSION: &str = "1";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Intent {
    pub v: String,
    pub action: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub args: Option<HashMap<String, Value>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cap: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub form: Option<HashMap<String, Value>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub idempotency_key: Option<String>,
    /// Unknown fields preserved for forward-compatibility.
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ErrorObject {
    pub code: String,
    pub message: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fields: Option<HashMap<String, Vec<String>>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub retryable: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<Value>,
}

/// A single effect. `op` is required; remaining fields are free-form.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Op {
    pub op: String,
    #[serde(flatten)]
    pub fields: HashMap<String, Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Hop {
    pub peer: String,
    pub at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cap_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Trace {
    pub intent_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub caused_by: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub hops: Vec<Hop>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ResultDoc {
    pub ok: bool,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub ops: Vec<Op>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorObject>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub meta: Option<HashMap<String, Value>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trace: Option<Trace>,
}

impl Intent {
    pub fn validate(&self) -> Result<(), String> {
        if self.v != IR_VERSION {
            return Err(format!("v must be '{}', got '{}'", IR_VERSION, self.v));
        }
        if self.action.is_empty() {
            return Err("action must be non-empty".into());
        }
        Ok(())
    }
}

impl ResultDoc {
    pub fn validate(&self) -> Result<(), String> {
        if !self.ok {
            match &self.error {
                Some(e) if !e.code.is_empty() && !e.message.is_empty() => {}
                _ => return Err("error.code and error.message required when ok=false".into()),
            }
        }
        for (i, op) in self.ops.iter().enumerate() {
            if op.op.is_empty() {
                return Err(format!("ops[{i}].op must be non-empty"));
            }
        }
        if let Some(tr) = &self.trace {
            if tr.intent_id.is_empty() {
                return Err("trace.intent_id required when trace present".into());
            }
        }
        Ok(())
    }
}
