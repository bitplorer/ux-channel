"""EffectGraph builders — host-side until project()."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Node:
    kind: str
    data: dict = field(default_factory=dict)
    children: List["Node"] = field(default_factory=list)


EffectGraph = List[Node]


def morph(target: str, html: str) -> Node:
    return Node("morph", {"target": target, "html": html})


def toast(message: str, level: str = "info", duration_ms: Optional[int] = None) -> Node:
    d: dict[str, Any] = {"message": message, "level": level}
    if duration_ms is not None:
        d["duration_ms"] = duration_ms
    return Node("toast", d)


def navigate(href: str, replace: bool = False) -> Node:
    return Node("navigate", {"href": href, "replace": replace})


def seq(*nodes: Node) -> Node:
    return Node("seq", {}, list(nodes))


def after(ms: int, *nodes: Node, timer_id: str = "t") -> Node:
    return Node("after", {"ms": int(ms), "id": timer_id}, list(nodes))


def dispatch_event(
    name: str, target: Optional[str] = None, detail: Optional[dict] = None
) -> Node:
    d: dict[str, Any] = {"name": name}
    if target is not None:
        d["target"] = target
    if detail is not None:
        d["detail"] = detail
    return Node("dispatch", d)


def invoke(
    ref: str, method: str, args: Optional[dict] = None, body: Optional[List[Node]] = None
) -> Node:
    return Node(
        "invoke",
        {"ref": ref, "method": method, "args": args or {}},
        list(body or []),
    )


def graph(*nodes: Node) -> EffectGraph:
    return list(nodes)
