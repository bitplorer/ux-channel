"""
Live UX · AX · Developer tooling inspect — read-only, principal-scoped, prod-closed by default.

Governing stance: opt-in shell. Never a second mutation door.
"""

from __future__ import annotations

import inspect as pyinspect
from typing import Any, Optional, Sequence

__all__ = ["inspect_channel", "inspect_enabled"]


def inspect_enabled(channel: Any) -> bool:
    cfg = getattr(channel, "config", None)
    if cfg is None:
        return True  # no config → allow (tests)
    flag = getattr(cfg, "inspect_enabled", None)
    if flag is not None:
        return bool(flag)
    env = str(getattr(cfg, "environment", "production") or "production")
    return env != "production"


def inspect_channel(
    channel: Any,
    region: Optional[str] = None,
    *,
    principal: Any = None,
    role: Optional[str] = None,
    sections: Sequence[str] = ("ux", "ax", "dx"),
) -> dict[str, Any]:
    if not inspect_enabled(channel):
        return {
            "inspect_schema": 1,
            "error": "inspect_disabled",
            "ok": False,
        }
    sections = tuple(sections or ("ux", "ax", "dx"))
    out: dict[str, Any] = {"inspect_schema": 1, "ok": True, "uid": region}

    from ux_channel.devtools.agents_api import agents

    ag = agents(channel)
    reg = channel.registry

    if "ax" in sections:
        tools = ag.tools_for(
            principal, region=region, role=role, include_caps=False
        )
        sit = ag.situation(principal, region=region, role=role)
        out["ax"] = {
            "role": role,
            "allowed": [t["name"] for t in tools],
            "tools": tools,
            "situation": sit,
            "explain": ag.explain(region=region, role=role, principal=principal).get(
                "items"
            ),
        }

    if "dx" in sections:
        rdir = getattr(channel, "regions_dir", None)
        dx: dict[str, Any] = {"actions": []}
        if region and rdir is not None:
            for row in rdir.list_dx():
                if row["uid"] == region:
                    dx.update(row)
                    break
        # action table from registry
        acts = []
        for name in reg.names():
            meta = reg.action_meta(name)
            if region and meta.get("region_uid") not in (region, None):
                if not name.startswith(region + "."):
                    continue
            if region is None or meta.get("region_uid") == region or name.startswith(
                (region or "") + "."
            ):
                acts.append(
                    {
                        "wire": name,
                        "ax": meta.get("ax", True),
                        "roles": list(meta.get("roles") or []),
                        "summary": meta.get("summary"),
                        "region_uid": meta.get("region_uid"),
                    }
                )
        dx["actions"] = acts
        out["dx"] = dx

    if "ux" in sections and region:
        paint = None
        err = None
        controls = []
        chrome = {}
        rdir = getattr(channel, "regions_dir", None)
        inst = rdir.get(region) if rdir else None
        if inst is None:
            # try regions book paint
            try:
                paint = channel.html(region)
            except Exception as exc:
                err = str(exc)
        else:
            try:
                paint = inst.render(None)
                if not isinstance(paint, str):
                    paint = str(paint)
            except Exception as exc:
                err = str(exc)
            try:
                chrome = dict(inst.facts(principal) or {})
            except Exception:
                chrome = {}
            for name, member in pyinspect.getmembers(
                type(inst), predicate=pyinspect.isfunction
            ):
                meta = getattr(member, "_ux_region_action", None)
                if not meta:
                    continue
                wire = meta.get("name") or f"{inst.uid}.{name}"
                controls.append({"action": wire, "method": name})
        out["ux"] = {
            "paint_preview": paint,
            "controls": controls,
            "chrome_facts": chrome,
            "error": err,
        }

    audit = getattr(channel, "audit", None)
    out["audit"] = {
        "enabled": audit is not None,
        "recent": ag.history(limit=10, region=region, principal=principal)
        if audit
        else [],
    }
    return out
