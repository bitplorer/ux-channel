"""Shared architecture mode tokens.

Keep these strings in one place so HostRuntime, project(), and attach
cannot drift. ChannelConfig validates the same set independently so
``host`` does not import ``arch`` at config-parse time.
"""

from __future__ import annotations

EFFECTS_MODES = ("auto", "classic")
PROOFS_MODES = ("auto", "require", "off")
FLOW_MODES = ("auto", "off")


def validate_arch_modes(effects: str, proofs: str, flow: str) -> None:
    if effects not in EFFECTS_MODES:
        raise ValueError(f'effects must be one of {EFFECTS_MODES}, got {effects!r}')
    if proofs not in PROOFS_MODES:
        raise ValueError(f'proofs must be one of {PROOFS_MODES}, got {proofs!r}')
    if flow not in FLOW_MODES:
        raise ValueError(f'flow must be one of {FLOW_MODES}, got {flow!r}')
