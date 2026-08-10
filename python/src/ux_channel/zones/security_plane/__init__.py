"""Zone / package: **security_plane**

CSRF, attenuate, limits, auth doors.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'security_plane'
DESCRIPTION = 'CSRF, attenuate, limits, auth doors.'
MEMBERS = {'attenuate': 'Cap attenuation — child capabilities may only narrow parent authority.', 'bulkhead': 'Bulkhead / concurrency limiter — protect the channel under sudden load spikes.', 'host_csrf': 'Host CSRF forwarding (optional) + stable channel CSRF (**ux-channel** 0.1).', 'limits': 'Result size / safety limits.', 'policy': 'Policy hooks — optional allow/deny for actions and topics (Wave 5).', 'push_security': 'SSE / push subscribe authorization — production-ready doors for GET /push/{topic', 'ratelimit': 'Rate limiting for action endpoints — protect heavy-lifting apps under load.', 'security': 'HTTP-layer and apply-op security helpers (hardened after adversarial review).', 'security_events': 'Structured security event stream — Wireshark-like DX for auth doors.', 'tree_cap': 'Capability-shaped documents — envelopes attenuate down the tree.', 'ws_security': 'WebSocket authorization — production doors for ``WS /ux-channel/ws``.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
