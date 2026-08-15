"""Optional enhancement plane (Waves B–G).

Additive envelopes only. Classic IR 0.1 clients ignore unknown keys.
Does not grow root ``ux_channel`` exports.

Load order for peer companions (browser)::

    ux-peer-kernel.js        # authority apply only
    ux-peer-perception.js    # SEPARATE perception IR
    ux-peer-continuations.js # SEPARATE slot-fill
    ux-peer-dom-drivers.js   # optional real DOM bindings

Host runtime::

    from ux_channel.enhance.attach import attach_enhance
    attach_enhance(ch)  # or auto via Channel.boot when enhance!=False
"""
from __future__ import annotations

from ux_channel.enhance.continuations import (
    Continuation,
    attach_continuations,
    match_continuation,
    resolve_args,
)
from ux_channel.enhance.envelopes import enhance_result, strip_unknown_for_classic
from ux_channel.enhance.negotiation import PeerHello, SurfaceSet, negotiate_ops
from ux_channel.enhance.causal import Trace, Hop, attach_trace, new_trace
from ux_channel.enhance.delta import region_hash, prefer_delta, peer_wants_deltas
from ux_channel.enhance.recorder import SessionRecorder, SessionEvent
from ux_channel.enhance.handshake import PeerSession, HandshakeRegistry
from ux_channel.enhance.attach import (
    EnhanceFacade,
    attach_enhance,
    get_enhance,
    session_id_from_headers,
)

__all__ = [
    "Continuation",
    "attach_continuations",
    "match_continuation",
    "resolve_args",
    "enhance_result",
    "strip_unknown_for_classic",
    "PeerHello",
    "SurfaceSet",
    "negotiate_ops",
    "Trace",
    "Hop",
    "attach_trace",
    "new_trace",
    "region_hash",
    "prefer_delta",
    "peer_wants_deltas",
    "SessionRecorder",
    "SessionEvent",
    "PeerSession",
    "HandshakeRegistry",
    "EnhanceFacade",
    "attach_enhance",
    "get_enhance",
    "session_id_from_headers",
]
