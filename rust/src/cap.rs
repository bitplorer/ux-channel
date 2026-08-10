//! Capability tokens — compatible with Python `CapService` /
//! `itsdangerous.URLSafeTimedSerializer` (django-concat + HMAC-SHA1 +
//! optional zlib, URL-safe base64, timed signature).
//!
//! See SPEC/capability.md and conformance/vectors/cap/.

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha1::Sha1;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

type HmacSha1 = Hmac<Sha1>;

/// Default salt used by Python `CapService`.
pub const DEFAULT_SALT: &str = "ux-channel-cap";

/// Conformance oracle secret from `conformance/vectors/cap/02-oracle-token.json`.
pub const ORACLE_SECRET: &str = "conformance-oracle-secret-32chars!!";

#[derive(Debug, Error, PartialEq, Eq)]
pub enum CapError {
    #[error("capability token required")]
    Missing,
    #[error("invalid capability — bad signature or corrupt token")]
    Invalid,
    #[error("capability expired")]
    Expired,
    #[error("capability action mismatch")]
    ActionMismatch,
    #[error("capability args mismatch")]
    ArgsMismatch,
    #[error("capability principal mismatch")]
    PrincipalMismatch,
    #[error("capability missing scopes")]
    MissingScopes,
    #[error("capability secret too short (min 16)")]
    WeakSecret,
    #[error("payload error: {0}")]
    Payload(String),
}

impl CapError {
    /// Stable error code for Result.error.code (SPEC error vocabulary).
    pub fn code(&self) -> &'static str {
        match self {
            CapError::Missing
            | CapError::Expired
            | CapError::Invalid
            | CapError::ActionMismatch
            | CapError::ArgsMismatch
            | CapError::PrincipalMismatch
            | CapError::MissingScopes => "unauthorized",
            CapError::WeakSecret | CapError::Payload(_) => "internal",
        }
    }
}

/// Logical claims inside a capability token (after unsign).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CapPayload {
    pub action: String,
    pub args_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sub: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scopes: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub iat: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub jti: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub once: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub extra: Option<BTreeMap<String, Value>>,
}

/// HMAC capability issuer / verifier.
#[derive(Debug, Clone)]
pub struct CapService {
    secret: Vec<u8>,
    previous: Vec<Vec<u8>>,
    salt: Vec<u8>,
    max_age: u64,
}

impl CapService {
    pub fn new(secret: impl AsRef<[u8]>, max_age: u64) -> Result<Self, CapError> {
        Self::with_salt(secret, DEFAULT_SALT, max_age, None)
    }

    /// Conformance oracle service (known secret + generous max_age for frozen tokens).
    pub fn oracle() -> Self {
        Self::with_salt(ORACLE_SECRET, DEFAULT_SALT, 10_000_000, None)
            .expect("oracle secret is valid")
    }

    pub fn with_salt(
        secret: impl AsRef<[u8]>,
        salt: impl AsRef<[u8]>,
        max_age: u64,
        previous_secrets: Option<Vec<Vec<u8>>>,
    ) -> Result<Self, CapError> {
        let secret = secret.as_ref().to_vec();
        if secret.len() < 16 {
            return Err(CapError::WeakSecret);
        }
        let previous = previous_secrets
            .unwrap_or_default()
            .into_iter()
            .filter(|s| s.len() >= 16 && s.as_slice() != secret.as_slice())
            .collect();
        Ok(Self {
            secret,
            previous,
            salt: salt.as_ref().to_vec(),
            max_age,
        })
    }

    pub fn max_age(&self) -> u64 {
        self.max_age
    }

    /// Canonical args hash — matches oracle notes and Python `CapService._hash_args`
    /// when args are plain JSON (stdlib sorted-keys compact JSON, sha256[:32]).
    pub fn hash_args(args: &Value) -> String {
        let canon = canonical_args_json(args);
        let digest = Sha256::digest(canon.as_bytes());
        hex::encode(&digest[..16]) // 16 bytes → 32 hex chars
    }

    pub fn mint(
        &self,
        action: &str,
        args: &Value,
        sub: Option<&str>,
        scopes: Option<&[String]>,
    ) -> Result<String, CapError> {
        let now = unix_now();
        let mut payload = serde_json::json!({
            "action": action,
            "args_hash": Self::hash_args(args),
            "iat": now,
        });
        if let Some(s) = sub {
            payload["sub"] = Value::String(s.to_string());
        }
        if let Some(sc) = scopes {
            if !sc.is_empty() {
                payload["scopes"] = Value::Array(
                    sc.iter()
                        .map(|s| Value::String(s.clone()))
                        .collect(),
                );
            }
        }
        let body = serde_json::to_vec(&payload).map_err(|e| CapError::Payload(e.to_string()))?;
        self.dumps_timed(&body)
    }

    pub fn verify(
        &self,
        token: &str,
        action: &str,
        args: &Value,
    ) -> Result<CapPayload, CapError> {
        self.verify_full(token, action, args, None, None, None)
    }

    pub fn verify_full(
        &self,
        token: &str,
        action: &str,
        args: &Value,
        max_age: Option<u64>,
        expected_sub: Option<&str>,
        required_scopes: Option<&[String]>,
    ) -> Result<CapPayload, CapError> {
        let age = max_age.unwrap_or(self.max_age);
        let mut last = CapError::Invalid;
        for secret in std::iter::once(&self.secret).chain(self.previous.iter()) {
            match unsign_timed(token, secret, &self.salt, Some(age)) {
                Ok(raw) => {
                    let data: CapPayload = serde_json::from_slice(&raw)
                        .map_err(|e| CapError::Payload(e.to_string()))?;
                    if data.action != action {
                        return Err(CapError::ActionMismatch);
                    }
                    let expected = Self::hash_args(args);
                    if data.args_hash != expected {
                        return Err(CapError::ArgsMismatch);
                    }
                    if let Some(want) = expected_sub {
                        if data.sub.as_deref() != Some(want) {
                            return Err(CapError::PrincipalMismatch);
                        }
                    }
                    if let Some(need) = required_scopes {
                        let have: std::collections::HashSet<&str> = data
                            .scopes
                            .as_ref()
                            .map(|v| v.iter().map(|s| s.as_str()).collect())
                            .unwrap_or_default();
                        if !have.contains("*") {
                            for s in need {
                                if !have.contains(s.as_str()) {
                                    return Err(CapError::MissingScopes);
                                }
                            }
                        }
                    }
                    return Ok(data);
                }
                // Expired is definitive for this token; do not try previous secrets as "ok".
                Err(CapError::Expired) => return Err(CapError::Expired),
                Err(e) => last = e,
            }
        }
        Err(last)
    }

    fn dumps_timed(&self, json_bytes: &[u8]) -> Result<String, CapError> {
        let payload = dump_payload(json_bytes);
        let ts = unix_now() as u64;
        let ts_b64 = URL_SAFE_NO_PAD.encode(int_to_bytes(ts));
        let value = format!("{}.{}", String::from_utf8_lossy(&payload), ts_b64);
        let sig = sign_value(value.as_bytes(), &self.secret, &self.salt);
        Ok(format!("{}.{}", value, sig))
    }
}

/// Compact sorted-key JSON used for args_hash (oracle algorithm).
pub fn canonical_args_json(args: &Value) -> String {
    let sorted = sort_value(args.clone());
    serde_json::to_string(&sorted).unwrap_or_else(|_| "{}".into())
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

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn derive_key(secret: &[u8], salt: &[u8]) -> Vec<u8> {
    // django-concat: sha1(salt + b"signer" + secret)
    let mut h = Sha1::new();
    h.update(salt);
    h.update(b"signer");
    h.update(secret);
    h.finalize().to_vec()
}

fn sign_value(value: &[u8], secret: &[u8], salt: &[u8]) -> String {
    let key = derive_key(secret, salt);
    let mut mac = HmacSha1::new_from_slice(&key).expect("HMAC key");
    mac.update(value);
    let sig = mac.finalize().into_bytes();
    URL_SAFE_NO_PAD.encode(sig)
}

fn verify_signature(value: &[u8], sig_b64: &str, secret: &[u8], salt: &[u8]) -> bool {
    let expected = sign_value(value, secret, salt);
    // Constant-time compare (length must match first).
    expected.as_bytes().len() == sig_b64.as_bytes().len()
        && expected
            .as_bytes()
            .iter()
            .zip(sig_b64.as_bytes().iter())
            .fold(0u8, |acc, (a, b)| acc | (a ^ b))
            == 0
}

fn dump_payload(json: &[u8]) -> Vec<u8> {
    let mut enc = ZlibEncoder::new(Vec::new(), Compression::default());
    let compressed = if enc.write_all(json).is_ok() {
        enc.finish().ok()
    } else {
        None
    };
    let (bytes, compressed_flag) = match compressed {
        Some(c) if c.len() < json.len().saturating_sub(1) => (c, true),
        _ => (json.to_vec(), false),
    };
    let b64 = URL_SAFE_NO_PAD.encode(&bytes);
    if compressed_flag {
        format!(".{}", b64).into_bytes()
    } else {
        b64.into_bytes()
    }
}

fn load_payload(payload: &[u8]) -> Result<Vec<u8>, CapError> {
    let (rest, decompress) = if payload.starts_with(b".") {
        (&payload[1..], true)
    } else {
        (payload, false)
    };
    let decoded = URL_SAFE_NO_PAD
        .decode(rest)
        .map_err(|e| CapError::Payload(format!("base64: {e}")))?;
    if !decompress {
        return Ok(decoded);
    }
    let mut dec = ZlibDecoder::new(&decoded[..]);
    let mut out = Vec::new();
    dec.read_to_end(&mut out)
        .map_err(|e| CapError::Payload(format!("zlib: {e}")))?;
    Ok(out)
}

fn int_to_bytes(num: u64) -> Vec<u8> {
    let b = num.to_be_bytes();
    let mut i = 0;
    while i < b.len() - 1 && b[i] == 0 {
        i += 1;
    }
    b[i..].to_vec()
}

fn bytes_to_int(bytes: &[u8]) -> u64 {
    let mut buf = [0u8; 8];
    let start = 8 - bytes.len().min(8);
    buf[start..].copy_from_slice(&bytes[bytes.len().saturating_sub(8)..]);
    u64::from_be_bytes(buf)
}

fn unsign_timed(
    token: &str,
    secret: &[u8],
    salt: &[u8],
    max_age: Option<u64>,
) -> Result<Vec<u8>, CapError> {
    // Token form: <payload>.<ts>.<sig>  where payload may start with '.'
    let bytes = token.as_bytes();
    let sig_dot = bytes
        .iter()
        .rposition(|&c| c == b'.')
        .ok_or(CapError::Invalid)?;
    let sig = std::str::from_utf8(&bytes[sig_dot + 1..]).map_err(|_| CapError::Invalid)?;
    let before_sig = &bytes[..sig_dot];
    let ts_dot = before_sig
        .iter()
        .rposition(|&c| c == b'.')
        .ok_or(CapError::Invalid)?;
    let ts_b64 = std::str::from_utf8(&before_sig[ts_dot + 1..]).map_err(|_| CapError::Invalid)?;
    let payload_part = &before_sig[..ts_dot];

    if !verify_signature(before_sig, sig, secret, salt) {
        return Err(CapError::Invalid);
    }

    let ts_raw = URL_SAFE_NO_PAD
        .decode(ts_b64.as_bytes())
        .map_err(|_| CapError::Invalid)?;
    let ts = bytes_to_int(&ts_raw);
    if let Some(max) = max_age {
        let now = unix_now() as u64;
        let age = now as i64 - ts as i64;
        if age > max as i64 || age < 0 {
            return Err(CapError::Expired);
        }
    }

    load_payload(payload_part)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn oracle_args_hash() {
        let args = json!({"sku": "abc-123", "qty": 2});
        assert_eq!(
            CapService::hash_args(&args),
            "96e4f83e3793b646323a67f314b51044"
        );
    }

    #[test]
    fn mint_verify_roundtrip() {
        let svc = CapService::oracle();
        let args = json!({"sku": "x", "qty": 1});
        let tok = svc
            .mint("Cart.add", &args, Some("user:1"), Some(&["cart:write".into()]))
            .unwrap();
        svc.verify(&tok, "Cart.add", &args).unwrap();
        assert!(matches!(
            svc.verify(&tok, "Cart.remove", &args),
            Err(CapError::ActionMismatch)
        ));
        let mut bad = args.clone();
        bad["qty"] = json!(9);
        assert!(matches!(
            svc.verify(&tok, "Cart.add", &bad),
            Err(CapError::ArgsMismatch)
        ));
    }

    /// hash_args is pure + order-independent for object keys.
    #[test]
    fn hash_args_key_order_independent() {
        let a = json!({"sku": "a", "qty": 2});
        let b = json!({"qty": 2, "sku": "a"});
        assert_eq!(CapService::hash_args(&a), CapService::hash_args(&b));
    }

    #[test]
    fn weak_secret_rejected() {
        assert!(matches!(
            CapService::new("short", 3600),
            Err(CapError::WeakSecret)
        ));
    }
}

#[cfg(test)]
mod prop_tests {
    use super::*;
    use proptest::prelude::*;
    use serde_json::{json, Map, Value};

    fn leaf() -> impl Strategy<Value = Value> {
        prop_oneof![
            Just(Value::Null),
            any::<bool>().prop_map(Value::Bool),
            (-1000i64..1000i64).prop_map(|n| json!(n)),
            ".*".prop_map(|s| json!(s)),
        ]
    }

    fn json_object() -> impl Strategy<Value = Value> {
        prop::collection::btree_map("[a-z]{1,8}", leaf(), 0..6)
            .prop_map(|m| {
                let mut map = Map::new();
                for (k, v) in m {
                    map.insert(k, v);
                }
                Value::Object(map)
            })
    }

    fn action_name() -> impl Strategy<Value = String> {
        "[A-Za-z][A-Za-z0-9_.]{0,24}"
    }

    proptest! {
        #[test]
        fn hash_args_deterministic(args in json_object()) {
            let h1 = CapService::hash_args(&args);
            let h2 = CapService::hash_args(&args);
            prop_assert_eq!(h1.clone(), h2);
            prop_assert_eq!(h1.len(), 32);
        }

        #[test]
        fn mint_verify_roundtrip_prop(
            action in action_name(),
            args in json_object(),
        ) {
            let svc = CapService::oracle();
            let tok = svc.mint(&action, &args, None, None).expect("mint");
            svc.verify(&tok, &action, &args).expect("verify");
        }

        #[test]
        fn verify_rejects_tampered_args(
            action in action_name(),
            args in json_object(),
            extra_key in "[a-z]{3,6}",
        ) {
            prop_assume!(!args.as_object().unwrap().contains_key(&extra_key));
            let svc = CapService::oracle();
            let tok = svc.mint(&action, &args, None, None).expect("mint");
            let mut bad = args.clone();
            bad.as_object_mut().unwrap().insert(extra_key, json!(1));
            let err = svc.verify(&tok, &action, &bad).unwrap_err();
            prop_assert!(matches!(err, CapError::ArgsMismatch));
        }

        #[test]
        fn verify_rejects_wrong_action(
            action in action_name(),
            other in action_name(),
            args in json_object(),
        ) {
            prop_assume!(action != other);
            let svc = CapService::oracle();
            let tok = svc.mint(&action, &args, None, None).expect("mint");
            let err = svc.verify(&tok, &other, &args).unwrap_err();
            prop_assert!(matches!(err, CapError::ActionMismatch));
        }
    }
}
