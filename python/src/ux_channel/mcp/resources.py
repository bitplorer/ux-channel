"""
MCP resources — read-only context (situation, region, claim, verticals).

Never a substitute for Quantity authority.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from typing import Any, Callable, Mapping, Optional, Sequence

__all__ = ["list_resources", "read_resource"]


def list_resources(
    *,
    room: str = "",
    region_uids: Sequence[str] = (),
    verticals: Sequence[str] = (),
    has_claim: bool = False,
) -> list[dict[str, Any]]:
    """
    MCP resources/list entries for the current session context.

    Always includes ``uid://verticals``; claim/situation/outbox/regions when applicable.
    """
    out: list[dict[str, Any]] = [
        {
            "uri": "uid://verticals",
            "name": "Mounted vertical packs",
            "mimeType": "application/json",
        }
    ]
    if has_claim:
        out.append(
            {
                "uri": "uid://claim",
                "name": "Current MCP claim",
                "mimeType": "application/json",
            }
        )
    if room:
        out.append(
            {
                "uri": f"uid://situation/{room}",
                "name": f"Situation ({room})",
                "mimeType": "application/json",
            }
        )
        out.append(
            {
                "uri": f"uid://outbox/{room}",
                "name": f"Outbox ({room})",
                "mimeType": "application/json",
            }
        )
    for uid in region_uids:
        out.append(
            {
                "uri": f"uid://region/{uid}",
                "name": f"Region {uid}",
                "mimeType": "text/html",
            }
        )
    return out


def read_resource(
    uri: str,
    *,
    channel: Any = None,
    room: str = "",
    scopes: Sequence[str] = (),
    sub: str = "",
    verticals: Sequence[str] = (),
    region_uids: Sequence[str] = (),
    situation_fn: Optional[Callable[..., Any]] = None,
    region_html_fn: Optional[Callable[[str], str]] = None,
    outbox_summary_fn: Optional[Callable[[], Any]] = None,
) -> dict[str, Any]:
    """
    Returns { uri, mimeType, text } or raises ValueError/PermissionError.
    """
    u = str(uri or "").strip()
    if u == "uid://verticals":
        from ux_channel.mcp.verticals import list_verticals

        packs = [p.to_dict() for p in list_verticals() if not verticals or p.id in verticals]
        import json

        return {
            "uri": u,
            "mimeType": "application/json",
            "text": _serde.dumps({"verticals": packs}, pretty=True),
        }
    if u == "uid://claim":
        import json

        return {
            "uri": u,
            "mimeType": "application/json",
            "text": _serde.dumps(
                {"room": room, "sub": sub, "scopes": list(scopes), "verticals": list(verticals)},
                indent=2,
            ),
        }
    if u.startswith("uid://situation/"):
        r = u.split("/", 3)[-1]
        if room and r != room:
            raise PermissionError("situation room mismatch")
        import json

        facts: dict[str, Any] = {"room": r or room, "scopes": list(scopes)}
        if situation_fn:
            try:
                sit = situation_fn(facts)
                if hasattr(sit, "to_dict"):
                    facts = sit.to_dict()
                elif isinstance(sit, dict):
                    facts = sit
            except Exception as exc:
                facts["error"] = str(exc)
        return {
            "uri": u,
            "mimeType": "application/json",
            "text": _serde.dumps(facts, default=str, pretty=True),
        }
    if u.startswith("uid://region/"):
        uid = u[len("uid://region/") :]
        if region_uids and uid not in region_uids:
            raise PermissionError(f"region not allowlisted: {uid}")
        html = ""
        if region_html_fn:
            html = region_html_fn(uid) or ""
        elif channel is not None and hasattr(channel, "regions"):
            try:
                html = channel.regions.render(uid)  # type: ignore[attr-defined]
            except Exception:
                book = getattr(channel, "regions", None)
                if book and hasattr(book, "get"):
                    reg = book.get(uid)
                    if reg and callable(getattr(reg, "render", None)):
                        html = reg.render(None)
        return {"uri": u, "mimeType": "text/html", "text": html or f"<!-- empty {uid} -->"}
    if u.startswith("uid://outbox/"):
        import json

        summary: Any = {"pending": 0}
        if outbox_summary_fn:
            summary = outbox_summary_fn()
        return {
            "uri": u,
            "mimeType": "application/json",
            "text": _serde.dumps(summary, default=str, pretty=True),
        }
    raise ValueError(f"unknown resource: {uri}")
