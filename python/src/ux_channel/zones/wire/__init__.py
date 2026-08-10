"""Zone / package: **wire**

SUBPACKAGE: JSON/CXB codecs + negotiate.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'wire'
DESCRIPTION = 'SUBPACKAGE: JSON/CXB codecs + negotiate.'
MEMBERS = {'core': 'Core wire codec: formats, JSON engines, process policy.', 'cxb': '**CXB** — Channel eXchange Binary (``format="cxb"``).', 'negotiate': 'HTTP Accept / Content-Type negotiation and body encode/decode.', 'plugins': 'Internal wire **format plugin** registry.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
