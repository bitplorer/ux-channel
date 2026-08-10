"""ux-dom / duck trees → Morph IR (``ux_channel.morph_ir``)."""

from __future__ import annotations

from typing import Any, Optional

from ux_channel.paint.morph_ir import MorphNode, elem, lower_html, morph_ops, text_node
from ux_channel_ux_dom.tree import tree_to_dict


def ux_dom_to_morph_ir(node: Any) -> MorphNode:
    d = tree_to_dict(node)
    return _from_dict(d)


def _from_dict(d: Any) -> MorphNode:
    if not isinstance(d, dict):
        return text_node(d)
    if d.get("tag") == "#text" or (
        d.get("text") is not None
        and not d.get("children")
        and d.get("tag") in (None, "#text")
    ):
        return text_node(d.get("text", ""))
    if d.get("text") is not None and not d.get("children"):
        return text_node(d.get("text", ""))
    kids = []
    for c in d.get("children") or []:
        kids.append(_from_dict(c))
    if d.get("text") and not kids:
        kids.append(text_node(d["text"]))
    attrs = dict(d.get("attrs") or {})
    uid = d.get("uid") or attrs.get("data-channel-id") or attrs.get("data_channel_id")
    return elem(str(d.get("tag") or "div"), *kids, uid=uid, **attrs)


def paint_ux_dom_region(node: Any, *, uid: Optional[str] = None) -> list[dict]:
    """Compile duck/ux-dom node to morph ops for channel Result."""
    ir = ux_dom_to_morph_ir(node)
    if uid:
        ir.uid = uid
        ir.attrs["data-channel-id"] = uid
    return morph_ops(ir, target=uid or ir.uid)
