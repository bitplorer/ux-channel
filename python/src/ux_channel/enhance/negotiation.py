"""Wave D \u2014 Surface capability negotiation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


CLASSIC_SURFACES = frozenset(
    {
        "dom.morph",
        "dom.toast",
        "dom.swap",
        "dom.remove",
        "dom.set_text",
        "dom.set_attr",
        "dom.focus",
        "dom.scroll",
        "nav.navigate",
        "nav.push_url",
        "nav.reload",
        "signal.set",
        "timer.set",
        "timer.clear",
        "bridge.mount",
        "bridge.update",
        "bridge.call",
        "bridge.destroy",
        "sys.noop",
    }
)

DELTA_SURFACES = frozenset({"delta.patch", "delta.signal", "delta.crdt"})
PERCEPTION_FEATURES = frozenset({"perception.v1", "continuations", "seq", "invoke"})


@dataclass
class SurfaceSet:
    surfaces: set[str] = field(default_factory=lambda: set(CLASSIC_SURFACES))
    features: set[str] = field(default_factory=set)

    def supports(self, name: str) -> bool:
        return name in self.surfaces

    def has_feature(self, name: str) -> bool:
        return name in self.features


@dataclass
class PeerHello:
    ir_version: str = "1"
    formats: list[str] = field(default_factory=lambda: ["json"])
    surfaces: list[str] = field(default_factory=lambda: sorted(CLASSIC_SURFACES))
    features: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    peer_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ir_version": self.ir_version,
            "formats": list(self.formats),
            "surfaces": list(self.surfaces),
        }
        if self.features:
            body["features"] = list(self.features)
        if self.actions:
            body["actions"] = list(self.actions)
        if self.peer_id:
            body["peer_id"] = self.peer_id
        return body

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeerHello":
        return cls(
            ir_version=str(data.get("ir_version") or data.get("ir") or "1"),
            formats=list(data.get("formats") or ["json"]),
            surfaces=list(data.get("surfaces") or sorted(CLASSIC_SURFACES)),
            features=list(data.get("features") or []),
            actions=list(data.get("actions") or []),
            peer_id=data.get("peer_id"),
        )

    def surface_set(self) -> SurfaceSet:
        return SurfaceSet(surfaces=set(self.surfaces), features=set(self.features))


_OP_TO_SURFACE: dict[str, str] = {
    "morph": "dom.morph",
    "swap": "dom.swap",
    "remove": "dom.remove",
    "set_text": "dom.set_text",
    "set_attr": "dom.set_attr",
    "toast": "dom.toast",
    "focus": "dom.focus",
    "scroll": "dom.scroll",
    "navigate": "nav.navigate",
    "push_url": "nav.push_url",
    "reload": "nav.reload",
    "signal.set": "signal.set",
    "timer.set": "timer.set",
    "timer.clear": "timer.clear",
    "bridge.mount": "bridge.mount",
    "bridge.update": "bridge.update",
    "bridge.call": "bridge.call",
    "bridge.destroy": "bridge.destroy",
    "noop": "sys.noop",
    "delta.patch": "delta.patch",
    "delta.signal": "delta.signal",
    "delta.crdt": "delta.crdt",
}


def negotiate_ops(
    ops: Sequence[dict[str, Any]],
    peer: SurfaceSet | PeerHello | None,
    *,
    drop_unknown: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter / warn ops against peer surface set.

    Returns (emitted_ops, warnings).
    """
    if peer is None:
        surfaces = SurfaceSet()
    elif isinstance(peer, PeerHello):
        surfaces = peer.surface_set()
    else:
        surfaces = peer

    emitted: list[dict[str, Any]] = []
    warnings: list[str] = []
    for op in ops:
        kind = str(op.get("op") or "")
        surface = _OP_TO_SURFACE.get(kind, f"unknown.{kind}")
        if surfaces.supports(surface) or surface.startswith("unknown."):
            if surface.startswith("unknown.") and drop_unknown:
                warnings.append(f"dropped unknown op: {kind}")
                continue
            emitted.append(dict(op))
        else:
            warnings.append(f"peer lacks surface {surface} for op {kind}")
            if not drop_unknown:
                emitted.append(dict(op))
    return emitted, warnings
