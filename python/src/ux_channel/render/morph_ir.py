"""Morph IR — host-agnostic UI structure for multi-surface projection.

* **Not AX** — ``project_agent`` is an IR skin, not ``agents(ch).situation(...)``.
* ``region(uid, …)`` is a **morph target** (same law as ``@ch.region``) — not an HTML tag.

Authoring may happen in a document host (via interop) or plain dicts; this module
never imports a document library. HTML is one projection among many."""

from __future__ import annotations

import html as html_lib
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

from ux_channel.protocol.ops import morph as morph_op

__all__ = [
    "MorphNode",
    "elem",
    "text_node",
    "region",
    "list_node",
    "lower_html",
    "project_agent",
    "project_json",
    "morph_ops",
]

_VOID = frozenset(
    {
        "img",
        "br",
        "hr",
        "input",
        "meta",
        "link",
        "area",
        "base",
        "col",
        "embed",
        "source",
        "track",
        "wbr",
    }
)


@dataclass
class MorphNode:
    """
    Structural node (power public).

    kind: element | text | region | list

    * ``region`` — morph target with stable uid (control-plane paint surface)
    * ``element`` — generic tree node (tag is projection detail)
    """

    kind: str
    tag: Optional[str] = None
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["MorphNode"] = field(default_factory=list)
    text: Optional[str] = None
    uid: Optional[str] = None
    key: Optional[str] = None


def _normalize_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in attrs.items():
        if k == "class_":
            out["class"] = v
        elif k == "for_":
            out["for"] = v
        else:
            out[k] = v
    return out


def _as_children(children: Sequence[Union["MorphNode", str, None]]) -> list[MorphNode]:
    kids: list[MorphNode] = []
    for c in children:
        if c is None:
            continue
        if isinstance(c, MorphNode):
            kids.append(c)
        else:
            kids.append(text_node(str(c)))
    return kids


def elem(
    tag: str,
    *children: Union[MorphNode, str, None],
    uid: Optional[str] = None,
    **attrs: Any,
) -> MorphNode:
    """Tree node. String children become text. ``class_`` → ``class``."""
    na = _normalize_attrs(dict(attrs))
    node = MorphNode(
        kind="element",
        tag=tag,
        attrs=na,
        children=_as_children(children),
        uid=uid,
    )
    if uid:
        na.setdefault("data-channel-id", uid)
    return node


def text_node(text: str) -> MorphNode:
    return MorphNode(kind="text", text=str(text) if text is not None else "")


def region(
    uid: str,
    *children: Union[MorphNode, str, None],
    **attrs: Any,
) -> MorphNode:
    """
    Morph target with stable uid — same intent as ``@ch.region(uid)``.

    Result.ops morph into this uid. Not an HTML element type.
    """
    na = _normalize_attrs(dict(attrs))
    na["data-channel-id"] = uid
    return MorphNode(
        kind="region",
        tag="div",
        uid=uid,
        attrs=na,
        children=_as_children(children),
    )


def list_node(
    *children: Union[MorphNode, str, None],
    key: Optional[str] = None,
) -> MorphNode:
    return MorphNode(kind="list", children=_as_children(children), key=key)


def _attr_string(attrs: dict[str, Any]) -> str:
    parts: list[str] = []
    for k, v in attrs.items():
        if v is None or v is False:
            continue
        if v is True:
            parts.append(f" {html_lib.escape(str(k))}")
            continue
        parts.append(
            f' {html_lib.escape(str(k))}="{html_lib.escape(str(v), quote=True)}"'
        )
    return "".join(parts)


def _is_region(node: MorphNode) -> bool:
    return node.kind == "region"


def lower_html(node: MorphNode) -> str:
    """Project IR to an HTML string (one skin)."""
    if node.kind == "text":
        return html_lib.escape(node.text or "")
    if node.kind == "list":
        return "".join(lower_html(c) for c in node.children)
    if _is_region(node):
        attrs = dict(node.attrs or {})
        if node.uid:
            attrs["data-channel-id"] = node.uid
        tag = node.tag or "div"
        inner = "".join(lower_html(c) for c in node.children)
        return f"<{tag}{_attr_string(attrs)}>{inner}</{tag}>"
    tag = node.tag or "div"
    attrs = dict(node.attrs or {})
    if node.uid:
        attrs.setdefault("data-channel-id", node.uid)
    inner = "".join(lower_html(c) for c in node.children)
    if tag.lower() in _VOID:
        return f"<{tag}{_attr_string(attrs)} />"
    return f"<{tag}{_attr_string(attrs)}>{inner}</{tag}>"


def project_agent(node: MorphNode) -> dict[str, Any]:
    """
    IR → compact dict for machines.

    **Not** the AX world model (``ag.situation``).
    """
    if node.kind == "text":
        return {"kind": "text", "text": node.text or ""}
    kind = "region" if node.kind == "region" else node.kind
    base: dict[str, Any] = {
        "kind": kind,
        "tag": node.tag,
        "attrs": dict(node.attrs or {}),
        "children": [project_agent(c) for c in node.children],
    }
    if node.uid is not None:
        base["uid"] = node.uid
    if node.key is not None:
        base["key"] = node.key
    if node.text is not None and node.kind != "text":
        base["text"] = node.text
    return base


def project_json(node: MorphNode) -> dict[str, Any]:
    return project_agent(node)


def morph_ops(
    node: MorphNode,
    *,
    target: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Lower IR to morph op(s). Region nodes morph inner HTML into their uid."""
    if _is_region(node) and node.uid:
        inner = "".join(lower_html(c) for c in node.children)
        uid = target or node.uid
        return [morph_op(uid, inner)]
    uid = target or node.uid
    if not uid:
        raise ValueError("morph_ops requires target or node.uid")
    return [morph_op(uid, lower_html(node))]
