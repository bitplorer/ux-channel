"""
ux-dom tree → generic dict / slot compile / attenuated controls.

Imports ``ux_dom`` only inside functions that need it.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.security.attenuate import attenuate
from ux_channel.render.slot_compile import SlotMap, compile_tree


def tree_to_dict(node: Any) -> dict[str, Any]:
    """
    Best-effort convert ux-dom-like node to tree dict for ``compile_tree``.

    Accepts:
      * already a dict with tag/attrs/children
      * objects with ``tag`` / ``attrs`` / ``children`` or ``__render__``
    """
    if isinstance(node, Mapping):
        kids = node.get("children") or []
        out = {
            "tag": node.get("tag") or node.get("type") or "div",
            "attrs": dict(node.get("attrs") or {}),
            "key": node.get("key"),
            "children": [tree_to_dict(c) for c in kids],
        }
        if node.get("text") is not None:
            out["text"] = node.get("text")
        if node.get("uid") is not None:
            out["uid"] = node.get("uid")
        # capability-shaped document fields
        if node.get("control") is not None:
            out["control"] = dict(node["control"]) if isinstance(node["control"], dict) else node["control"]
        if node.get("envelope") is not None:
            out["envelope"] = dict(node["envelope"]) if isinstance(node["envelope"], dict) else node["envelope"]
        return out

    # duck-typed element
    tag = getattr(node, "tag", None) or getattr(node, "name", None) or type(node).__name__
    attrs = {}
    raw_attrs = getattr(node, "attributes", None) or getattr(node, "attrs", None) or {}
    if isinstance(raw_attrs, Mapping):
        attrs = dict(raw_attrs)
    children = getattr(node, "children", None) or getattr(node, "child", None) or []
    if callable(children):
        children = children()
    key = getattr(node, "key", None)
    # string / raw
    if isinstance(node, str):
        return {"tag": "#text", "attrs": {}, "children": [], "text": node}
    return {
        "tag": str(tag).lower() if tag else "div",
        "attrs": attrs,
        "key": key,
        "children": [tree_to_dict(c) for c in (children or [])],
    }


def compile_ux_dom(node: Any, *, prefix: str = "ui") -> SlotMap:
    """Stable uids for a ux-dom (or duck) tree via pure ``compile_tree``."""
    return compile_tree(tree_to_dict(node), prefix=prefix)


def attenuate_control(
    channel: Any,
    action: Any,
    *,
    parent_cap: Optional[str] = None,
    caveats: Optional[Sequence[str]] = None,
    **trust: Any,
) -> dict[str, str]:
    """
    Mint attenuated cap and return ux-dom kwargs (data_channel_*).

    Glue only — uses ``ux_channel.attenuate`` + ``ch.control``.
    """
    base = channel.control(action, **trust).as_ux_dom()
    if not parent_cap and not caveats:
        return base

    reg = channel.registry
    caps = getattr(reg, "_caps", None)
    if caps is None:
        raise RuntimeError("registry has no capability service")

    name = action if isinstance(action, str) else getattr(action, "__name__", None)
    if not name:
        # fall back to control action field
        name = base.get("data_channel_action") or base.get("data-channel-action")

    args = {}
    for k, v in trust.items():
        key = k[6:] if k.startswith("trust_") else k
        args[key] = v

    token = attenuate(
        caps,
        str(name),
        args,
        parent_token=parent_cap,
        caveats=caveats,
    )
    for k in list(base):
        if k.replace("-", "_").endswith("cap") or k.endswith("_cap") or "uid_cap" in k.replace("-", "_"):
            base[k] = token
    return base


def inject_uids(node: Any, *, prefix: str = "ui") -> tuple[dict[str, Any], SlotMap]:
    """
    Compile tree and return **(annotated_dict, SlotMap)** with ``data-channel-id`` on every node.

    Pure dict output — safe without ux-dom installed. Hosts can re-render from dict
    or walk ``SlotMap.uids``.
    """
    d = tree_to_dict(node)
    sm = compile_tree(d, prefix=prefix)
    assert isinstance(sm.tree, dict)
    return sm.tree, sm


def inject_ux_dom(node: Any, *, prefix: str = "ui") -> SlotMap:
    """
    Best-effort: compile + if node has mutable ``attrs``/``attributes``, write uids back.

    Does not require the ``ux_dom`` package; duck-typed elements only.
    """
    sm = compile_ux_dom(node, prefix=prefix)
    # try to stamp root if mutable
    _stamp_duck(node, sm)
    return sm


def _stamp_duck(node: Any, sm: SlotMap, path: str = "root") -> None:
    if node is None or isinstance(node, (str, bytes, int, float, bool)):
        return
    uid = None
    # find uid for this path
    for u, p in sm.uids.items():
        if p == path:
            uid = u
            break
    if uid is not None:
        attrs = getattr(node, "attrs", None)
        if isinstance(attrs, dict):
            attrs["data-channel-id"] = uid
        attributes = getattr(node, "attributes", None)
        if isinstance(attributes, dict):
            attributes["data-channel-id"] = uid
        if hasattr(node, "set_attr") and callable(node.set_attr):
            try:
                node.set_attr("data-channel-id", uid)
            except Exception:
                pass
    children = getattr(node, "children", None) or []
    if callable(children):
        try:
            children = children()
        except Exception:
            children = []
    tag = getattr(node, "tag", None) or type(node).__name__
    key = getattr(node, "key", None)
    for i, ch in enumerate(children or []):
        child_path = f"{path}/{key if key is not None else tag}:{i}"
        _stamp_duck(ch, sm, child_path)
