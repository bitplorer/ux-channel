"""
Glue: ux-dom/duck tree → capability-shaped compile (rejects illegal controls).

Does not live in ux_channel core.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.security.tree_cap import TreeCapError, TreeEnvelope, compile_tree_caps, nest_envelope
from ux_channel_ux_dom.tree import tree_to_dict


def compile_capability_tree(
    node: Any,
    *,
    scopes: Sequence[str] = ("*",),
    trust: Optional[Mapping[str, Any]] = None,
    max_money: Optional[float] = None,
    strict: bool = True,
) -> tuple[dict[str, Any], TreeEnvelope]:
    """
    Convert duck/ux-dom/dict → tree dict, validate controls under root envelope.

    ``strict=True`` raises TreeCapError if any control is illegal.
    """
    root = TreeEnvelope(
        scopes=frozenset(scopes),
        trust=dict(trust or {}),
        max_money=max_money,
        path="root",
    )
    d = tree_to_dict(node)
    out, errors = compile_tree_caps(d, root)
    if errors and strict:
        raise TreeCapError("; ".join(errors))
    return out, root


def nest_page(
    *,
    scopes: Sequence[str],
    trust: Optional[Mapping[str, Any]] = None,
    max_money: Optional[float] = None,
) -> TreeEnvelope:
    """Root page envelope helper."""
    return TreeEnvelope(
        scopes=frozenset(scopes),
        trust=dict(trust or {}),
        max_money=max_money,
        path="page",
    )
