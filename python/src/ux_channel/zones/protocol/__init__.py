"""Zone / package: **protocol**

Wire IR + codecs + capabilities — shared law with Rust.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'protocol'
DESCRIPTION = 'Wire IR + codecs + capabilities — shared law with Rust.'
MEMBERS = {'capability': 'Capability tokens — HMAC authority for browser→server Intents.', 'encode': 'encode_result — lift Python return values into Result.', 'error_map': 'Error plane — codes → HTTP status, client kind, batch envelope status.', 'errors': 'Channel error types — **public**.', 'jsonutil': 'JSON safety helpers (depth / breadth limits for untrusted Intent args).', 'ops': 'Ops — client apply instructions inside a Result.', 'serde': 'JSON helpers — thin re-export of ``ux_channel.wire`` dumps/loads.', 'types': 'Protocol types: Intent (request) and Result (response).'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
