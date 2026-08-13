//! ux_channel_rs — architecture kernel + runtime (host and peer).
//!
//! Host kernel: cap, nonce, registry, effects, project, proof.
//! Host runtime: `HostRuntime` (sessions, handle_intent, health).
//! Peer kernel: `PeerApply` (apply Result, no DOM).
//! Peer runtime: `PeerRuntime` (hello, submit_intent, revoke).
//! Classic IR 0.1 floor: `peer::Peer` gate + types/wire/CXB.

pub mod actions;
pub mod apply;
pub mod cap;
pub mod cxb;
pub mod drivers;
pub mod effects;
pub mod flow;
pub mod host;
pub mod nonce;
pub mod op_tags;
pub mod peer;
pub mod project;
pub mod proof;
pub mod registry;
pub mod runtime;
pub mod stamps;
pub mod types;
pub mod wire_json;

pub use apply::{ApplyCtx, ApplyError, PeerApply};
pub use cap::{CapError, CapPayload, CapService, ORACLE_SECRET};
pub use cxb::{decode_cxb, encode_cxb, is_cxb, CxbError, MEDIA_TYPE as CXB_MEDIA_TYPE};
pub use drivers::{make_agent_drivers, make_web_drivers, safe_href};
pub use effects::{after, dispatch_event, graph, invoke, morph, navigate, seq, toast, EffectGraph, Node};
pub use flow::{attach_flow_meta, new_flow_id, FlowError, FlowStore};
pub use host::{HostConfig, HostError, HostRuntime};
pub use nonce::{MemoryNonceStore, NonceStore};
pub use peer::Peer; // classic Intent gate (uxc_peer). Not PeerApply.
pub use project::project;
pub use proof::{ProofError, ProofService};
pub use registry::{ActionOut, Registry};
pub use runtime::{Loopback, Outbox, PeerRuntime, Transport};
pub use stamps::StampTable;
pub use types::{ErrorObject, Hop, Intent, Op, ResultDoc, Trace, IR_VERSION};
pub use wire_json::{
    canonical_json, decode_intent, decode_result, decode_value, encode_intent, encode_result,
    parse_intent_lenient, WireError,
};

/// SPEC name for the peer kernel.
pub type PeerKernel = PeerApply;
