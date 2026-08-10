"""
Stable slot/uid compile from host-agnostic tree dicts.

Input shape (JSON-serializable)::

    {"tag": "div", "attrs": {...}, "children": [ ... ], "key": "row-1"}

No ux-dom dependency — interop layer converts ux-dom → this shape.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

__all__ = ["stable_uid", "SlotMap", "compile_tree", "TreeDict"]

_SAFE = re.compile(r"[^A-Za-z0-9_.:@+-]+")


def stable_uid(*parts: Any, prefix: str = "") -> str:
    """Deterministic uid from path parts (region/list identity)."""
    cleaned = []
    for p in parts:
        if p is None:
            continue
        s = _SAFE.sub("-", str(p)).strip("-")
        if s:
            cleaned.append(s)
    if not cleaned:
        raise ValueError("stable_uid requires at least one part")
    body = ".".join(cleaned)
    if prefix:
        return f"{prefix}.{body}"
    return body


TreeDict = Mapping[str, Any]


@dataclass
class SlotMap:
    """Compiled slots: uid → path within tree."""

    uids: dict[str, str] = field(default_factory=dict)  # uid → dotted path
    root_uid: Optional[str] = None
    tree: Any = None  # annotated copy

    def __contains__(self, uid: str) -> bool:
        return uid in self.uids


def compile_tree(
    tree: TreeDict,
    *,
    prefix: str = "ui",
    uid_attr: str = "data-channel-id",
) -> SlotMap:
    """
    Walk a tree dict; assign stable uids where missing; record SlotMap.

    Recognizes:
      * attrs[uid_attr] or attrs['uid'] as explicit uid
      * key on node for list identity
    """
    sm = SlotMap()
    annotated = _walk(tree, path="root", prefix=prefix, sm=sm, uid_attr=uid_attr)
    sm.tree = annotated
    if isinstance(annotated, dict):
        sm.root_uid = (annotated.get("attrs") or {}).get(uid_attr)
    return sm


def _walk(
    node: Any,
    *,
    path: str,
    prefix: str,
    sm: SlotMap,
    uid_attr: str,
) -> Any:
    if not isinstance(node, Mapping):
        return node
    tag = node.get("tag") or node.get("type") or "node"
    attrs = dict(node.get("attrs") or {})
    key = node.get("key")
    explicit = attrs.get(uid_attr) or attrs.get("uid") or node.get("uid")
    if explicit:
        uid = str(explicit)
    else:
        parts = [prefix, path]
        if key is not None:
            parts.append(key)
        else:
            parts.append(tag)
        # short hash for stability without huge paths
        digest = hashlib.sha1(".".join(str(p) for p in parts).encode()).hexdigest()[:10]
        uid = stable_uid(prefix, path.replace("/", "."), digest)
    attrs[uid_attr] = uid
    sm.uids[uid] = path
    children_in = node.get("children") or []
    children_out = []
    for i, ch in enumerate(children_in):
        child_path = f"{path}/{key if key is not None else tag}:{i}"
        children_out.append(
            _walk(ch, path=child_path, prefix=prefix, sm=sm, uid_attr=uid_attr)
        )
    out = dict(node)
    out["attrs"] = attrs
    out["uid"] = uid
    out["children"] = children_out
    return out
