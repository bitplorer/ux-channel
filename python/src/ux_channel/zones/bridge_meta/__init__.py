"""Zone / package: **bridge_meta**

Bridge contracts/scaffold (presets in bridges/).

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'bridge_meta'
DESCRIPTION = 'Bridge contracts/scaffold (presets in bridges/).'
MEMBERS = {'bridge_api': 'Bridge API — npm widget hosts (not regions).', 'bridge_contract': 'Bridge contracts — how unknown npm APIs become knowable without FFI.', 'bridge_plane': 'Bridge plane — npm **widget** hosts as **data + ops** (not HTML).', 'bridge_preset_gen': 'Automate bridge **preset** creation (adapter + contract + Python façade).', 'bridge_protocol': 'Sealed bridge protocols — guest islands may only use declared methods/events.', 'bridge_scaffold': 'Scaffold npm widget bridges — any package via string ops (not FFI).', 'bridge_style': 'Host chrome for bridge islands — class / style / CSS variables.', 'guest_runtime': 'Sealed guest runtime — islands may paint, not invent durable quantities.', 'plugins': 'Plugin system — plug-and-play integration points for ux-channel.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
