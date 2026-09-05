"""L7 EffectGraph builders + Cap-gated classic-floor project (cut #4).

Not L1. Not a Cap. Not a second Host kernel. ``after_cek_cut2`` refuses
``_graph`` without a present Cap and projects when a Cap is present.

Classic floor only: seq / invoke flatten; delayed ``after`` drops.
Rich hello-gated seq/timer/invoke lived on the deleted arch Host plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence


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


def _as_node(raw: Any) -> Optional[Node]:
    if isinstance(raw, Node):
        return raw
    if isinstance(raw, Mapping) and raw.get("kind"):
        kids = raw.get("children") or []
        return Node(
            str(raw["kind"]),
            dict(raw.get("data") or {}),
            [c for c in (_as_node(k) for k in kids) if c is not None],
        )
    return None


def project_graph(g: Sequence[Any] | None) -> list[dict]:
    """Classic-floor graph → ops. Caller already Cap-gated."""
    out: list[dict] = []
    for raw in list(g or []):
        node = _as_node(raw)
        if node is not None:
            out.extend(_lower(node))
    return out


def _lower(node: Node) -> list[dict]:
    k = node.kind
    if k in ("seq", "invoke"):
        ops: list[dict] = []
        for ch in node.children:
            ops.extend(_lower(ch))
        return ops
    if k == "after":
        ms = int(node.data.get("ms") or 0)
        if ms <= 0:
            ops = []
            for ch in node.children:
                ops.extend(_lower(ch))
            return ops
        return []
    if k == "morph":
        return [{"op": "morph", "target": node.data["target"], "html": node.data["html"]}]
    if k == "toast":
        op = {
            "op": "toast",
            "message": node.data["message"],
            "level": node.data.get("level", "info"),
        }
        if "duration_ms" in node.data:
            op["duration_ms"] = node.data["duration_ms"]
        return [op]
    if k == "navigate":
        return [
            {
                "op": "navigate",
                "href": node.data["href"],
                "replace": bool(node.data.get("replace")),
            }
        ]
    if k == "dispatch":
        op = {"op": "dispatch", "name": node.data["name"]}
        if node.data.get("target"):
            op["target"] = node.data["target"]
        if "detail" in node.data:
            op["detail"] = node.data["detail"]
        return [op]
    return []
