"""
Vertical packs — installable MCP product slices.

Final tool allow = marked tools ∩ policy ∩ pack ∩ claim scopes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "VerticalPack",
    "register_vertical",
    "get_vertical",
    "list_verticals",
    "clear_verticals",
    "filter_tools_by_verticals",
    "tool_matches_verticals",
    "builtin_pos_pack",
    "builtin_lab_pack",
    "register_builtin_verticals",
]


@dataclass(frozen=True)
class VerticalPack:
    """Declarative product vertical for MCP / agents."""

    id: str
    title: str = ""
    room: str = ""
    scopes: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    tags: frozenset[str] = field(default_factory=frozenset)
    confirm: frozenset[str] = field(default_factory=frozenset)
    read_only_tools: frozenset[str] = field(default_factory=frozenset)
    outbox_tools: frozenset[str] = field(default_factory=frozenset)
    io_methods: frozenset[str] = field(default_factory=frozenset)
    version: str = "1"

    def __post_init__(self) -> None:
        if not self.id or not str(self.id).strip():
            raise ValueError("VerticalPack.id required")
        if not self.tags:
            object.__setattr__(
                self, "tags", frozenset({f"vertical:{self.id}"})
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title or self.id,
            "room": self.room,
            "scopes": sorted(self.scopes),
            "tools": sorted(self.tools),
            "tags": sorted(self.tags),
            "confirm": sorted(self.confirm),
            "read_only_tools": sorted(self.read_only_tools),
            "outbox_tools": sorted(self.outbox_tools),
            "io_methods": sorted(self.io_methods),
            "version": self.version,
        }


_lock = threading.RLock()
_REGISTRY: dict[str, VerticalPack] = {}


def register_vertical(pack: VerticalPack, *, replace: bool = False) -> None:
    """Register a vertical pack process-wide. Raises if id exists unless replace."""
    with _lock:
        if pack.id in _REGISTRY and not replace:
            raise ValueError(f"vertical already registered: {pack.id}")
        _REGISTRY[pack.id] = pack


def get_vertical(pack_id: str) -> Optional[VerticalPack]:
    """Return pack by id or None."""
    with _lock:
        return _REGISTRY.get(pack_id)


def list_verticals() -> list[VerticalPack]:
    """All registered packs (snapshot)."""
    with _lock:
        return list(_REGISTRY.values())


def clear_verticals() -> None:
    """Remove all packs (tests only)."""
    with _lock:
        _REGISTRY.clear()


def tool_matches_verticals(
    tool: Mapping[str, Any],
    vertical_ids: Sequence[str],
    *,
    packs: Optional[Mapping[str, VerticalPack]] = None,
) -> bool:
    """True if tool name or tags match any selected pack."""
    if not vertical_ids:
        return True
    name = str(tool.get("name") or "")
    ann = tool.get("annotations") or {}
    uid = ann.get("uid") or {}
    tags = set(uid.get("tags") or ann.get("tags") or [])
    for vid in vertical_ids:
        pack = (packs or _REGISTRY).get(vid) if packs is not None else get_vertical(vid)
        if pack is None:
            # bare tag match vertical:id
            if f"vertical:{vid}" in tags or vid in tags:
                return True
            continue
        if name in pack.tools:
            return True
        if tags & set(pack.tags):
            return True
        if f"vertical:{pack.id}" in tags:
            return True
    return False


def filter_tools_by_verticals(
    tools: Iterable[Mapping[str, Any]],
    vertical_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Keep tools that match any selected vertical (name or tags). Empty ids = no filter."""
    if not vertical_ids:
        return [dict(t) for t in tools]
    # resolve packs; unknown ids still allow tag match
    return [dict(t) for t in tools if tool_matches_verticals(t, vertical_ids)]


def builtin_pos_pack() -> VerticalPack:
    """Sample POS vertical (cart / pay / outbox)."""
    return VerticalPack(
        id="pos",
        title="Point of sale",
        room="pos",
        scopes=frozenset({"pos", "pay", "queue", "drain", "outbox", "add", "scan"}),
        tools=frozenset(
            {"pos_add_line", "pos_pay", "pos_queue_add", "pos_drain"}
        ),
        tags=frozenset({"vertical:pos"}),
        confirm=frozenset({"pos_pay", "pos_drain"}),
        outbox_tools=frozenset({"pos_queue_add"}),
    )


def builtin_lab_pack() -> VerticalPack:
    """Sample lab DUT vertical (read / flash)."""
    return VerticalPack(
        id="lab",
        title="Lab DUT",
        room="lab",
        scopes=frozenset({"lab", "lab.flash", "lab.read"}),
        tools=frozenset({"lab_read", "lab_flash"}),
        tags=frozenset({"vertical:lab"}),
        confirm=frozenset({"lab_flash"}),
        io_methods=frozenset({"read", "flash"}),
        read_only_tools=frozenset({"lab_read"}),
    )


def register_builtin_verticals(*, replace: bool = True) -> None:
    """Register sample pos + lab packs (idempotent when replace=True)."""
    register_vertical(builtin_pos_pack(), replace=replace)
    register_vertical(builtin_lab_pack(), replace=replace)
