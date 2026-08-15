"""Optional enhancement plane (Waves B–G).

Additive envelopes only. Classic IR 0.1 clients ignore unknown keys.
Does not grow root ``ux_channel`` exports.
"""
from __future__ import annotations

from ux_channel.enhance.continuations import Continuation, attach_continuations, match_continuation
from ux_channel.enhance.envelopes import enhance_result, strip_unknown_for_classic
from ux_channel.enhance.negotiation import PeerHello, SurfaceSet, negotiate_ops
from ux_channel.enhance.causal import Trace, Hop, attach_trace
from ux_channel.enhance.delta import region_hash, prefer_delta
from ux_channel.enhance.recorder import SessionRecorder, SessionEvent

__all__ = [
    "Continuation",
    "attach_continuations",
    "match_continuation",
    "enhance_result",
    "strip_unknown_for_classic",
    "PeerHello",
    "SurfaceSet",
    "negotiate_ops",
    "Trace",
    "Hop",
    "attach_trace",
    "region_hash",
    "prefer_delta",
    "SessionRecorder",
    "SessionEvent",
]
