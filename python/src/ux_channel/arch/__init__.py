"""Architecture runtime — EffectGraph, project, proofs, stamps, flow, host/peer.

L2 host-adjacent. Does not replace CapService or Channel. Production crypto
is ``ux_channel.protocol.CapService`` (itsdangerous). These modules add:

* EffectGraph + ``project(effects=auto|classic)``
* Host-directed effect proofs (separate key from Cap)
* Stamp table for invoke
* FlowStore / ``meta.flow_id`` (correlation only — never authority)
* HostRuntime + PeerApply (no DOM in the peer kernel)

Use ``Channel`` (``attach_arch``) in apps. Use ``HostRuntime`` in gate tests.

Classic IR 0.1 clients stay on the floor: without a peer hello advertising
``seq`` / ``invoke`` / ``web.v1`` / ``agent.v1``, project emits classic ops.
"""

from ux_channel.arch.drivers import (
    make_agent_drivers,
    make_trace_drivers,
    make_web_drivers,
    make_wire_drivers,
)
from ux_channel.arch.effects import after, dispatch_event, graph, invoke, morph, navigate, seq, toast
from ux_channel.arch.flow_store import FlowError, FlowStore, attach_flow_meta, new_flow_id
from ux_channel.arch.host_runtime import HostConfig, HostRuntime
from ux_channel.arch.modes import EFFECTS_MODES, FLOW_MODES, PROOFS_MODES, validate_arch_modes
from ux_channel.arch.peer import ApplyError, PeerApply, PeerRuntime
from ux_channel.arch.project import project
from ux_channel.arch.proof import ProofError, ProofService
from ux_channel.arch.stamps import StampTable

__all__ = [
    "EFFECTS_MODES",
    "FLOW_MODES",
    "PROOFS_MODES",
    "validate_arch_modes",
    "HostConfig",
    "HostRuntime",
    "PeerApply",
    "PeerRuntime",
    "ApplyError",
    "ProofService",
    "ProofError",
    "StampTable",
    "FlowStore",
    "FlowError",
    "attach_flow_meta",
    "new_flow_id",
    "project",
    "graph",
    "morph",
    "toast",
    "navigate",
    "seq",
    "after",
    "dispatch_event",
    "invoke",
    "make_web_drivers",
    "make_agent_drivers",
    "make_trace_drivers",
    "make_wire_drivers",
]
