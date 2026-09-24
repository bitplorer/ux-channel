"""Classic Channel ops → declared-catalog pairs for Host.project_wire.

Channel wire (toast, navigate, …) is the product floor. Only pairs in the
declared catalog are projected by a CEK Host. Everything else stays on the Channel peer.

EffectGraph is not a Cap and is not projected here. Graph → ops is
L7, after Cap (``cek.effects.project_graph``).
"""

from __future__ import annotations

from typing import Any, Sequence

from ux_channel.ops.translate import from_classic


def to_catalog(ops: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep declared-catalog pairs. ``ui.dom.morph`` payload becomes {target, patch}."""
    from cek_host.catalog import in_catalog

    out: list[dict[str, Any]] = []
    for op in from_classic(list(ops)):
        if not in_catalog(op.ns, op.name):
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


def project_catalog(ops: Sequence[dict[str, Any]], stamp: frozenset | None = None) -> list[dict[str, Any]]:
    """Fail closed on pairs outside the session stamp. Channel-only ops are dropped first."""
    from cek_host.catalog import CATALOG_PAIRS, project_wire

    return project_wire(to_catalog(ops), stamp if stamp is not None else CATALOG_PAIRS)
