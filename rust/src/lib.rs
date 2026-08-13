//! ux_channel_rs — Rust peer for ux-channel Intent → Result → ops.
//!
//! Permanent: `types`, `wire_json`, `cap`, `cxb`, `op_tags`, `peer` gate,
//! `apply` kernel, `runtime`, `proof`, `drivers`.
//! Moving: `actions` demo handlers; `uxc_peer` HTTP chrome.
//! Docs: repo `START_HERE.md`, `TESTING.md`, `rust/README.md`,
//! `SPEC/architecture/`.

pub mod actions;
pub mod apply;
pub mod cap;
pub mod cxb;
pub mod drivers;
pub mod nonce;
pub mod op_tags;
pub mod peer;
pub mod proof;
pub mod runtime;
pub mod types;
pub mod wire_json;

pub use apply::{ApplyCtx, ApplyError, PeerApply};
pub use cap::{CapError, CapPayload, CapService, ORACLE_SECRET};
pub use cxb::{decode_cxb, encode_cxb, is_cxb, CxbError, MEDIA_TYPE as CXB_MEDIA_TYPE};
pub use drivers::{make_agent_drivers, make_web_drivers, safe_href};
pub use nonce::{MemoryNonceStore, NonceStore};
pub use peer::Peer;
pub use proof::{ProofError, ProofService};
pub use runtime::{Loopback, Outbox, PeerRuntime, Transport};
pub use types::{ErrorObject, Hop, Intent, Op, ResultDoc, Trace, IR_VERSION};
pub use wire_json::{
    canonical_json, decode_intent, decode_result, decode_value, encode_intent, encode_result,
    parse_intent_lenient, WireError,
};
