"""Wave F — Differential ops helpers + region hash policy."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from ux_channel.ops.catalog import Op
from ux_channel.ops.translate import to_classic
from ux_channel.enhance.negotiation import SurfaceSet, DELTA_SURFACES


def region_hash(html_or_state: Any) -> str:
    """Stable short hash for last-known region state."""
    if isinstance(html_or_state, (bytes, bytearray)):
        raw = bytes(html_or_state)
    else:
        raw = str(html_or_state).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def prefer_delta(
    *,
    target: str,
    full_html: str,
    patch: Any | None,
    last_hash: str | None,
    peer: SurfaceSet | None,
    force_full: bool = False,
) -> list[dict[str, Any]]:
    """Emit delta.patch when peer supports it and we have a patch; else morph."""
    if force_full or patch is None or peer is None:
        return to_classic([Op.morph(target, full_html)])
    if not peer.supports("delta.patch"):
        return to_classic([Op.morph(target, full_html)])
    op = Op.delta_patch(target, patch, base_hash=last_hash)
    return to_classic([op])


def peer_wants_deltas(peer: SurfaceSet | None) -> bool:
    if peer is None:
        return False
    return bool(peer.surfaces & DELTA_SURFACES)
