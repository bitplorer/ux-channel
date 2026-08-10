//! ux_channel_rs — Rust peer for the ux-channel Intent → Result → ops contract.
//!
//! Phase 2 surface:
//! - `types` / `wire_json` — IR JSON floor
//! - `cap` — portable capability mint/verify (itsdangerous-compatible)
//! - `cxb` / `op_tags` — CXB1/CXBZ codec (decode matches frozen oracle blobs)
//! - `peer` / `actions` — Intent → Result dispatch
//! - bins: `uxc_check`, `uxc_peer`

pub mod actions;
pub mod cap;
pub mod cxb;
pub mod op_tags;
pub mod peer;
pub mod types;
pub mod wire_json;

pub use cap::{CapError, CapPayload, CapService, ORACLE_SECRET};
pub use cxb::{decode_cxb, encode_cxb, is_cxb, CxbError, MEDIA_TYPE as CXB_MEDIA_TYPE};
pub use peer::Peer;
pub use types::{ErrorObject, Hop, Intent, Op, ResultDoc, Trace, IR_VERSION};
pub use wire_json::{
    canonical_json, decode_intent, decode_result, decode_value, encode_intent, encode_result,
    parse_intent_lenient, WireError,
};
