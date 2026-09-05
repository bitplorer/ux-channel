//! ux_channel_rs — classic IR 0.1 floor (types, wire, CXB, cap, peer gate).
//!
//! Channel product Cap machine is cek-runtime Host (Python wrap, ADR 0011).
//! This crate is the classic Peer **verify-only** gate plus codecs.
//! No HostRuntime / PeerApply / Peer mint.

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
