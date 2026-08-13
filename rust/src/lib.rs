//! ux_channel_rs — Rust peer for ux-channel Intent → Result → ops.
//!
//! Permanent: `types`, `wire_json`, `cap`, `cxb`, `op_tags`, `peer` gate.  
//! Moving: `actions` demo handlers; `uxc_peer` HTTP chrome.  
//! Docs: repo `START_HERE.md`, `TESTING.md`, `rust/README.md`.

pub mod actions;
pub mod cap;
pub mod cxb;
pub mod nonce;
pub mod op_tags;
pub mod peer;
pub mod types;
pub mod wire_json;

pub use cap::{CapError, CapPayload, CapService, ORACLE_SECRET};
pub use cxb::{decode_cxb, encode_cxb, is_cxb, CxbError, MEDIA_TYPE as CXB_MEDIA_TYPE};
pub use nonce::{MemoryNonceStore, NonceStore};
pub use peer::Peer;
pub use types::{ErrorObject, Hop, Intent, Op, ResultDoc, Trace, IR_VERSION};
pub use wire_json::{
    canonical_json, decode_intent, decode_result, decode_value, encode_intent, encode_result,
    parse_intent_lenient, WireError,
};
