//! Process-local once/jti store. Fail-closed when full or lock poisoned.
//! Multi-worker hosts should use a durable store (Redis SET NX EX).

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

pub trait NonceStore: Send + Sync {
    /// True if key was unused and is now consumed; false if replay or refuse.
    fn use_once(&self, key: &str, ttl: Duration) -> bool;
}

pub struct MemoryNonceStore {
    inner: Mutex<HashMap<String, Instant>>,
    max_keys: usize,
}

impl MemoryNonceStore {
    pub fn new(max_keys: usize) -> Self {
        Self {
            inner: Mutex::new(HashMap::new()),
            max_keys,
        }
    }
}

impl Default for MemoryNonceStore {
    fn default() -> Self {
        Self::new(100_000)
    }
}

impl NonceStore for MemoryNonceStore {
    fn use_once(&self, key: &str, ttl: Duration) -> bool {
        let mut map = match self.inner.lock() {
            Ok(g) => g,
            Err(_) => return false,
        };
        let now = Instant::now();
        map.retain(|_, exp| *exp > now);
        if map.get(key).map(|e| *e > now).unwrap_or(false) {
            return false;
        }
        if map.len() >= self.max_keys {
            return false;
        }
        map.insert(key.to_string(), now + ttl);
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replay_fails() {
        let s = MemoryNonceStore::default();
        assert!(s.use_once("a", Duration::from_secs(60)));
        assert!(!s.use_once("a", Duration::from_secs(60)));
    }

    #[test]
    fn lock_poison_fail_closed() {
        let s = MemoryNonceStore::default();
        let _ = std::panic::catch_unwind(|| {
            let _g = s.inner.lock().unwrap();
            panic!("poison");
        });
        assert!(!s.use_once("after-poison", Duration::from_secs(60)));
    }
}
