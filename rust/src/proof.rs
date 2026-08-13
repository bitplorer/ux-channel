//! Host-directed effect proofs — HMAC-SHA256 over Result body hash.
//!
//! Matches Python `ux_channel.arch.proof.ProofService`.
//! Key MUST differ from the Cap secret (enforced by the host, not here).

use crate::types::ResultDoc;
use crate::wire_json::canonical_json;
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use hmac::{Hmac, Mac};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ProofError {
    #[error("proof secret too short")]
    WeakSecret,
    #[error("canonical json: {0}")]
    Canonical(String),
}

/// HMAC effect-proof service (Cap key ≠ proof key).
pub struct ProofService {
    secret: Vec<u8>,
    pub kid: String,
    pub max_age_s: u64,
}

impl ProofService {
    pub fn new(secret: impl AsRef<[u8]>) -> Result<Self, ProofError> {
        let secret = secret.as_ref().to_vec();
        if secret.len() < 16 {
            return Err(ProofError::WeakSecret);
        }
        Ok(Self {
            secret,
            kid: "p1".into(),
            max_age_s: 120,
        })
    }

    pub fn with_kid(mut self, kid: impl Into<String>) -> Self {
        self.kid = kid.into();
        self
    }

    pub fn with_max_age(mut self, secs: u64) -> Self {
        self.max_age_s = secs;
        self
    }

    /// SHA-256 hex of canonical `{error, ok, ops}`.
    pub fn body_hash(result: &Value) -> Result<String, ProofError> {
        let core = json!({
            "ok": result.get("ok").cloned().unwrap_or(Value::Null),
            "ops": result.get("ops").cloned().unwrap_or_else(|| json!([])),
            "error": result.get("error").cloned().unwrap_or(Value::Null),
        });
        let raw = canonical_json(&core).map_err(|e| ProofError::Canonical(e.to_string()))?;
        Ok(hex::encode(Sha256::digest(raw.as_bytes())))
    }

    pub fn body_hash_doc(doc: &ResultDoc) -> Result<String, ProofError> {
        let value = serde_json::to_value(doc).map_err(|e| ProofError::Canonical(e.to_string()))?;
        Self::body_hash(&value)
    }

    pub fn sign_value(
        &self,
        result: &mut Value,
        session_id: &str,
        gen: i64,
    ) -> Result<(), ProofError> {
        let bh = Self::body_hash(result)?;
        let exp = now_secs() + self.max_age_s as i64;
        let jti = fresh_jti(&self.secret);
        let mut payload = json!({
            "session_id": session_id,
            "gen": gen,
            "jti": jti,
            "exp": exp,
            "body_hash": bh,
            "kid": self.kid,
        });
        let raw = canonical_json(&payload).map_err(|e| ProofError::Canonical(e.to_string()))?;
        let sig = hmac_sha256(&self.secret, raw.as_bytes());
        payload
            .as_object_mut()
            .expect("payload object")
            .insert("sig".into(), json!(sig));

        let meta = result
            .as_object_mut()
            .map(|o| o.entry("meta").or_insert_with(|| json!({})))
            .ok_or_else(|| ProofError::Canonical("result must be an object".into()))?;
        if !meta.is_object() {
            *meta = json!({});
        }
        meta.as_object_mut()
            .expect("meta object")
            .insert("effect".into(), payload);
        Ok(())
    }

    pub fn sign_doc(
        &self,
        doc: &mut ResultDoc,
        session_id: &str,
        gen: i64,
    ) -> Result<(), ProofError> {
        let mut value = serde_json::to_value(&*doc).map_err(|e| ProofError::Canonical(e.to_string()))?;
        self.sign_value(&mut value, session_id, gen)?;
        let signed: ResultDoc =
            serde_json::from_value(value).map_err(|e| ProofError::Canonical(e.to_string()))?;
        *doc = signed;
        Ok(())
    }

    pub fn verify_value(&self, result: &Value, session_id: &str, gen: i64) -> bool {
        let Some(eff) = result
            .get("meta")
            .and_then(|m| m.get("effect"))
            .and_then(|e| e.as_object())
        else {
            return false;
        };
        let Some(sid) = eff.get("session_id").and_then(|v| v.as_str()) else {
            return false;
        };
        if sid != session_id {
            return false;
        }
        let Some(g) = as_i64(eff.get("gen")) else {
            return false;
        };
        if g != gen {
            return false;
        }
        let Some(exp) = as_i64(eff.get("exp")) else {
            return false;
        };
        if now_secs() > exp {
            return false;
        }
        let Ok(bh) = Self::body_hash(result) else {
            return false;
        };
        if eff.get("body_hash").and_then(|v| v.as_str()) != Some(bh.as_str()) {
            return false;
        }
        let Some(jti) = eff.get("jti").and_then(|v| v.as_str()) else {
            return false;
        };
        let Some(kid) = eff.get("kid").and_then(|v| v.as_str()) else {
            return false;
        };
        let payload = json!({
            "session_id": sid,
            "gen": g,
            "jti": jti,
            "exp": exp,
            "body_hash": bh,
            "kid": kid,
        });
        let Ok(raw) = canonical_json(&payload) else {
            return false;
        };
        let expect = hmac_sha256_raw(&self.secret, raw.as_bytes());
        let Some(sig_b64) = eff.get("sig").and_then(|v| v.as_str()) else {
            return false;
        };
        let pad = pad_b64(sig_b64);
        let Ok(sig) = URL_SAFE_NO_PAD.decode(pad.trim_end_matches('=')) else {
            // URL_SAFE_NO_PAD rejects padding; try after stripping.
            let stripped: String = sig_b64.chars().filter(|c| *c != '=').collect();
            match URL_SAFE_NO_PAD.decode(stripped.as_bytes()) {
                Ok(s) => return constant_eq(&expect, &s),
                Err(_) => return false,
            }
        };
        constant_eq(&expect, &sig)
    }

    pub fn verify_doc(&self, doc: &ResultDoc, session_id: &str, gen: i64) -> bool {
        match serde_json::to_value(doc) {
            Ok(v) => self.verify_value(&v, session_id, gen),
            Err(_) => false,
        }
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn as_i64(v: Option<&Value>) -> Option<i64> {
    let v = v?;
    v.as_i64()
        .or_else(|| v.as_u64().map(|u| u as i64))
        .or_else(|| v.as_f64().map(|f| f as i64))
}

fn hmac_sha256(secret: &[u8], raw: &[u8]) -> String {
    URL_SAFE_NO_PAD.encode(hmac_sha256_raw(secret, raw))
}

fn hmac_sha256_raw(secret: &[u8], raw: &[u8]) -> Vec<u8> {
    let mut mac = HmacSha256::new_from_slice(secret).expect("hmac key");
    mac.update(raw);
    mac.finalize().into_bytes().to_vec()
}

fn fresh_jti(secret: &[u8]) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let pid = std::process::id();
    let mut mac = HmacSha256::new_from_slice(secret).expect("hmac key");
    mac.update(&nanos.to_be_bytes());
    mac.update(&pid.to_be_bytes());
    let out = mac.finalize().into_bytes();
    URL_SAFE_NO_PAD.encode(&out[..12])
}

fn pad_b64(s: &str) -> String {
    let mut t = s.to_string();
    while t.len() % 4 != 0 {
        t.push('=');
    }
    t
}

fn constant_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b.iter()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sign_verify_roundtrip() {
        let p = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut result = json!({
            "ok": true,
            "ops": [{"op": "toast", "message": "hi", "level": "info"}],
            "error": null
        });
        p.sign_value(&mut result, "s1", 1).unwrap();
        assert!(p.verify_value(&result, "s1", 1));
        assert!(!p.verify_value(&result, "s1", 2));
        assert!(!p.verify_value(&result, "other", 1));
    }

    #[test]
    fn forged_sig_fails() {
        let p = ProofService::new(b"proof-secret-16b!").unwrap();
        let mut result = json!({"ok": true, "ops": [], "error": null});
        p.sign_value(&mut result, "s1", 1).unwrap();
        result["ops"] = json!([{"op": "toast", "message": "pwn"}]);
        assert!(!p.verify_value(&result, "s1", 1));
    }

    #[test]
    fn short_secret_refused() {
        assert!(ProofService::new(b"short").is_err());
    }
}
