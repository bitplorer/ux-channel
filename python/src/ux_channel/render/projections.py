"""Multi-surface projections from Morph IR.

* **Not AX** — ``project_agent_view`` is Morph IR; world model is ``agents(ch).situation``."""

from __future__ import annotations

from typing import Any, Optional

from ux_channel.render.morph_ir import MorphNode, lower_html, project_agent, project_json
from ux_channel.protocol.ops import morph as morph_op

__all__ = [
    "project_html",
    "project_agent_view",
    "project_a11y",
    "project_print",
    "project_all",
    "morph_from_ir",
]


def project_html(node: MorphNode) -> str:
    return lower_html(node)


def project_agent_view(node: MorphNode) -> dict[str, Any]:
    """Alias of ``project_agent`` (Morph IR skin — not AX situation)."""
    return project_agent(node)


def project_a11y(node: MorphNode) -> dict[str, Any]:
    """Accessibility-oriented projection (roles, names, text)."""

    def walk(n: MorphNode) -> dict[str, Any]:
        if n.kind == "text":
            return {"role": "text", "name": n.text or ""}
        role = (n.attrs or {}).get("role") or n.tag or "generic"
        name = (
            (n.attrs or {}).get("aria-label")
            or (n.attrs or {}).get("aria_label")
            or (n.attrs or {}).get("alt")
            or ""
        )
        kids = [walk(c) for c in n.children]
        text = " ".join(
            (c.get("name") or "") for c in kids if c.get("role") == "text"
        ).strip()
        return {
            "role": role,
            "name": name or text,
            "uid": n.uid,
            "children": [c for c in kids if c.get("role") != "text" or c.get("name")],
        }

    return walk(node)


def project_print(node: MorphNode) -> str:
    """Plain-text / print-friendly serialization."""

    def walk(n: MorphNode, depth: int = 0) -> str:
        pad = "  " * depth
        if n.kind == "text":
            return pad + (n.text or "")
        lines = [f"{pad}{n.tag or 'block'}" + (f"#{n.uid}" if n.uid else "")]
        for c in n.children:
            lines.append(walk(c, depth + 1))
        return "\n".join(lines)

    return walk(node)


def project_all(node: MorphNode) -> dict[str, Any]:
    return {
        "html": project_html(node),
        "agent": project_agent_view(node),
        "a11y": project_a11y(node),
        "print": project_print(node),
        "ir": project_json(node),
    }


def morph_from_ir(node: MorphNode, *, target: Optional[str] = None) -> list[dict[str, Any]]:
    uid = target or node.uid
    if not uid:
        raise ValueError("morph_from_ir requires uid")
    sel = uid if str(uid).startswith("[") else f'[data-channel-id="{uid}"]'
    return [morph_op(sel, project_html(node))]
