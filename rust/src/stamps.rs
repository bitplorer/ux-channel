//! Host-owned stamp table for invoke refs. Peer never owns authority.

use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::collections::{HashMap, HashSet};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone)]
pub struct Stamp {
    pub stamp_id: String,
    pub kind: String,
    pub methods: HashSet<String>,
    pub session_id: String,
    pub gen: u64,
}

pub struct StampTable {
    inner: Mutex<HashMap<String, HashMap<String, Stamp>>>,
}

impl Default for StampTable {
    fn default() -> Self {
        Self {
            inner: Mutex::new(HashMap::new()),
        }
    }
}

impl StampTable {
    pub fn grant(
        &self,
        session_id: &str,
        gen: u64,
        kind: &str,
        methods: impl IntoIterator<Item = impl Into<String>>,
    ) -> Stamp {
        let stamp_id = fresh_id(session_id, gen, kind);
        let st = Stamp {
            stamp_id: stamp_id.clone(),
            kind: kind.into(),
            methods: methods.into_iter().map(Into::into).collect(),
            session_id: session_id.into(),
            gen,
        };
        let mut g = self.inner.lock().expect("stamps");
        g.entry(session_id.into())
            .or_default()
            .insert(stamp_id, st.clone());
        st
    }

    pub fn allows(&self, session_id: &str, stamp_id: &str, gen: u64, method: &str) -> bool {
        let g = self.inner.lock().expect("stamps");
        match g.get(session_id).and_then(|m| m.get(stamp_id)) {
            Some(st) if st.gen == gen => st.methods.contains(method) || st.methods.contains("*"),
            _ => false,
        }
    }

    pub fn on_revoke(&self, session_id: &str) {
        self.inner.lock().expect("stamps").remove(session_id);
    }
}

fn fresh_id(session_id: &str, gen: u64, kind: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mut mac = HmacSha256::new_from_slice(b"uxc-stamp").expect("hmac");
    mac.update(session_id.as_bytes());
    mac.update(&gen.to_be_bytes());
    mac.update(kind.as_bytes());
    mac.update(&nanos.to_be_bytes());
    let out = mac.finalize().into_bytes();
    hex::encode(&out[..8])
}
