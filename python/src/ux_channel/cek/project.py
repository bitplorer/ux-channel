"""Classic Channel ops → S pairs for Host.project_wire.

Channel wire (toast, navigate, …) is the product floor. Only pairs in S
are legal on a CEK Host. Everything else stays on the Channel peer.
"""

from __future__ import annotations

from typing import Any, Sequence

from ux_channel.ops.translate import from_classic


def to_s(ops: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only S pairs. ``ui.dom.morph`` payload becomes {target, patch}."""
    from cek_host.legal import is_legal

    out: list[dict[str, Any]] = []
    for op in from_classic(list(ops)):
        if not is_legal(op.ns, op.name):
            continue
        payload = dict(op.payload)
        if op.ns == "ui.dom" and op.name == "morph":
            target = payload.get("target") or payload.get("id") or payload.get("region") or ""
            patch = payload.get("patch")
            if patch is None:
                patch = {k: v for k, v in payload.items() if k not in {"target", "id", "region"}}
            payload = {"target": target, "patch": patch}
        out.append({"ns": op.ns, "name": op.name, "payload": payload})
    return out


def project_s(ops: Sequence[dict[str, Any]], stamp: frozenset | None = None) -> list[dict[str, Any]]:
    """Fail closed on illegal / unstamped pairs. Channel-only ops are dropped first."""
    from cek_host.legal import LEGAL_PAIRS, project_wire

    return project_wire(to_s(ops), stamp if stamp is not None else LEGAL_PAIRS)
