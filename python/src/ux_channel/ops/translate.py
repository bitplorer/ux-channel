"""Bidirectional translator: structured Op \u2194 classic wire dict."""
from __future__ import annotations

from typing import Any, Sequence

from ux_channel.ops.catalog import Op

# structured (ns, name) \u2192 classic "op" field
_TO_CLASSIC: dict[tuple[str, str], str] = {
    ("ui.dom", "morph"): "morph",
    ("ui.dom", "swap"): "swap",
    ("ui.dom", "remove"): "remove",
    ("ui.dom", "set_text"): "set_text",
    ("ui.dom", "set_attr"): "set_attr",
    ("ui", "toast"): "toast",
    ("ui", "focus"): "focus",
    ("ui", "scroll"): "scroll",
    ("ui", "busy"): "busy",
    ("nav", "navigate"): "navigate",
    ("nav", "push_url"): "push_url",
    ("nav", "reload"): "reload",
    ("signal", "set"): "signal.set",
    ("timer", "set"): "timer.set",
    ("timer", "clear"): "timer.clear",
    ("sys", "noop"): "noop",
    ("delta", "patch"): "delta.patch",
    ("delta", "signal"): "delta.signal",
}

_FROM_CLASSIC: dict[str, tuple[str, str]] = {v: k for k, v in _TO_CLASSIC.items()}


def to_classic(ops: Sequence[Op | dict[str, Any]]) -> list[dict[str, Any]]:
    """Emit classic wire ops suitable for Result.ops."""
    out: list[dict[str, Any]] = []
    for item in ops:
        if isinstance(item, dict) and "op" in item:
            out.append(dict(item))
            continue
        if isinstance(item, dict) and "ns" in item:
            op = Op(item["ns"], item["name"], item.get("payload"))
        else:
            op = item  # type: ignore[assignment]
        key = (op.ns, op.name)
        classic = _TO_CLASSIC.get(key)
        if classic is None:
            out.append({"op": "noop", "meta": {"dropped": f"{op.ns}.{op.name}"}})
            continue
        body: dict[str, Any] = {"op": classic}
        for k, v in op.payload.items():
            if v is not None:
                if classic == "swap" and k == "mode":
                    body["swap"] = v
                elif classic == "morph" and k == "html":
                    body["html"] = v
                else:
                    body[k] = v
        out.append(body)
    return out


def from_classic(ops: Sequence[dict[str, Any]]) -> list[Op]:
    """Classic wire \u2192 structured Ops (best-effort)."""
    out: list[Op] = []
    for o in ops:
        kind = o.get("op")
        if not kind:
            continue
        mapped = _FROM_CLASSIC.get(str(kind))
        if mapped is None:
            out.append(Op("unknown", str(kind), {k: v for k, v in o.items() if k != "op"}))
            continue
        ns, name = mapped
        payload = {k: v for k, v in o.items() if k != "op"}
        if kind == "swap" and "swap" in payload:
            payload["mode"] = payload.pop("swap")
        out.append(Op(ns, name, payload))
    return out
