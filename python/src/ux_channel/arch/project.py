"""Pure project(graph, hello, effects) -> ops[]. Classic floor is permanent."""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from ux_channel.arch.effects import EffectGraph, Node


def project(
    graph: EffectGraph,
    peer_hello: Optional[Mapping[str, Any]] = None,
    *,
    effects: str = "auto",
) -> List[dict]:
    if effects not in ("auto", "classic"):
        raise ValueError('effects must be "auto" or "classic"')
    hello = dict(peer_hello or {})
    profiles = set(hello.get("profiles") or [])
    features = set(hello.get("features") or [])
    allow_rich = effects == "auto" and (
        "seq" in features
        or "invoke" in features
        or "web.v1" in profiles
        or "agent.v1" in profiles
    )
    classic_only = effects == "classic" or not allow_rich
    # agent.v1 without web.v1: no chrome-only morph/navigate (profiles/agent.v1.md)
    drop_chrome = "agent.v1" in profiles and "web.v1" not in profiles
    out: List[dict] = []
    for node in graph:
        out.extend(_lower(node, classic_only=classic_only, drop_chrome=drop_chrome))
    return out


def _lower(node: Node, *, classic_only: bool, drop_chrome: bool = False) -> List[dict]:
    k = node.kind
    if k == "seq":
        if classic_only:
            ops: List[dict] = []
            for ch in node.children:
                ops.extend(_lower(ch, classic_only=True, drop_chrome=drop_chrome))
            return ops
        return [
            {
                "op": "seq",
                "ops": [
                    o
                    for ch in node.children
                    for o in _lower(ch, classic_only=False, drop_chrome=drop_chrome)
                ],
            }
        ]
    if k == "after":
        ms = int(node.data.get("ms") or 0)
        tid = str(node.data.get("id") or "t")
        body = [
            o
            for ch in node.children
            for o in _lower(ch, classic_only=classic_only, drop_chrome=drop_chrome)
        ]
        if classic_only:
            return body if ms <= 0 else []
        return [{"op": "timer.set", "id": tid, "ms": ms, "ops": body}]
    if k == "invoke":
        if classic_only:
            return [
                o
                for ch in node.children
                for o in _lower(ch, classic_only=True, drop_chrome=drop_chrome)
            ]
        op: dict[str, Any] = {
            "op": "invoke",
            "ref": node.data["ref"],
            "method": node.data["method"],
            "args": node.data.get("args") or {},
        }
        if node.children:
            op["ops"] = [
                o
                for ch in node.children
                for o in _lower(ch, classic_only=False, drop_chrome=drop_chrome)
            ]
        return [op]
    if drop_chrome and k in ("morph", "navigate"):
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
