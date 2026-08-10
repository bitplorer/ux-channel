"""
Enrich MCP tool descriptors with vertical / outbox / I/O annotations.

Hosts (Claude Desktop, Cursor, custom MCP clients) can hide tools, force
confirmation, or offline-route using ``annotations.ux_channel`` without
hardcoding action names.

Public
------
* ``classify_tool`` — build annotation fragment for one tool name/tags
* ``enrich_tool`` / ``enrich_tools`` — merge into tools/list entries

Does not change dispatch; pure metadata for list_tools.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.mcp.verticals import VerticalPack, get_vertical, list_verticals

__all__ = ["enrich_tool", "enrich_tools", "classify_tool"]


def classify_tool(
    name: str,
    tags: Sequence[str] = (),
    *,
    pack: Optional[VerticalPack] = None,
) -> dict[str, Any]:
    """
    Return a ``ux_channel`` annotation fragment for one tool.

    Resolves the vertical pack from ``pack``, ``vertical:*`` tags, or registry.
    Sets kind hints: ``outbox.queue``, ``io.read``, ``io.command``, ``read``, ``command``.
    """
    tagset = set(tags)
    out: dict[str, Any] = {}
    if pack is None:
        for t in tagset:
            if t.startswith("vertical:"):
                pack = get_vertical(t.split(":", 1)[1])
                if pack:
                    break
        if pack is None:
            for p in list_verticals():
                if name in p.tools or tagset & set(p.tags):
                    pack = p
                    break
    if pack is None:
        if "outbox" in tagset:
            out["outbox"] = True
            out["kind"] = "outbox"
        return out

    out["vertical"] = pack.id
    if pack.scopes:
        out["scopes"] = sorted(pack.scopes)
    if name in pack.confirm:
        out["confirm"] = True
    if name in pack.outbox_tools or "outbox" in tagset:
        out["outbox"] = True
        out["kind"] = out.get("kind") or "outbox.queue"
    if name in pack.read_only_tools:
        out["read_only"] = True
        out["kind"] = out.get("kind") or "read"
    if pack.io_methods:
        for m in pack.io_methods:
            if name == m or name.endswith(f"_{m}") or f".{m}" in name or name.endswith(m):
                out["kind"] = "io.command" if m not in ("read", "id", "status") else "io.read"
                out["io_method"] = m
                break
        if "kind" not in out:
            if any(x in name for x in ("flash", "write", "actuate", "scan")):
                out["kind"] = "io.command"
            elif any(x in name for x in ("read", "id", "status", "view")):
                out["kind"] = "io.read"
    if name in pack.confirm and "kind" not in out:
        out["kind"] = "command"
    if out.get("kind") == "io.command":
        out["requires_quantity"] = True
    return out


def enrich_tool(tool: Mapping[str, Any], *, verticals: Sequence[str] = ()) -> dict[str, Any]:
    """
    Copy a tools/list entry and attach ``annotations.uid`` + ``annotations.ux_channel``.

    Existing annotation keys are preserved (setdefault). Destructive/readOnly
    MCP hints are aligned with pack confirm / read_only flags.
    """
    t = dict(tool)
    ann = dict(t.get("annotations") or {})
    uid = dict(ann.get("uid") or {})
    tags = list(uid.get("tags") or [])
    name = str(t.get("name") or "")
    pack = None
    for vid in verticals or ():
        p = get_vertical(vid)
        if p and (name in p.tools or set(tags) & set(p.tags)):
            pack = p
            break
    frag = classify_tool(name, tags, pack=pack)
    for k, v in frag.items():
        uid.setdefault(k, v)
    if uid.get("read_only") or ann.get("readOnlyHint"):
        ann["readOnlyHint"] = True
    if uid.get("confirm"):
        ann["destructiveHint"] = True
    ann["uid"] = uid
    ann["ux_channel"] = {
        "vertical": uid.get("vertical"),
        "kind": uid.get("kind"),
        "confirm": bool(uid.get("confirm")),
        "outbox": bool(uid.get("outbox")),
        "scopes": uid.get("scopes") or [],
        "requires_quantity": bool(uid.get("requires_quantity")),
        "io_method": uid.get("io_method"),
    }
    t["annotations"] = ann
    return t


def enrich_tools(
    tools: Sequence[Mapping[str, Any]], *, verticals: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """Enrich a list of tools/list entries (see ``enrich_tool``)."""
    return [enrich_tool(t, verticals=verticals) for t in tools]
