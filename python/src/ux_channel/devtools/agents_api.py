"""AX façade — ``agents(ch)`` for tools_for · situation · dispatch · effects.

Human path: Intent + caps. Agent path: ``agents(ch).dispatch`` → same registry.
"""


from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from ux_channel.agent_runtime.peer import AgentPeer, dispatch_peer
from ux_channel.protocol.types import Result

__all__ = ["Agents", "agents", "attach_agents", "EffectReport"]

_log = logging.getLogger("ux_channel.devtools.agents_api")


@dataclass(frozen=True)
class EffectReport:
    """Compact post-Intent summary for agents (not HTML)."""

    ok: bool
    action: str
    notices: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    next_tools: tuple[str, ...] = ()
    error_code: Optional[str] = None
    op_kinds: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "notices": list(self.notices),
            "changed": list(self.changed),
            "next_tools": list(self.next_tools),
            "error_code": self.error_code,
            "op_kinds": list(self.op_kinds),
        }


def _tool_params_from_handler(fn: Any) -> dict[str, Any]:
    """Best-effort JSON Schema properties from call signature (private)."""
    props: dict[str, Any] = {}
    required: list[str] = []
    try:
        sig = getattr(fn, "__signature__", None) or inspect.signature(fn)
    except (TypeError, ValueError):
        return {"type": "object", "properties": props}
    skip = {"self", "ctx", "context", "intent", "principal", "request", "ch", "channel"}
    for name, p in sig.parameters.items():
        if name in skip or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = p.annotation
        t = "string"
        if ann is int:
            t = "integer"
        elif ann is float:
            t = "number"
        elif ann is bool:
            t = "boolean"
        elif ann is inspect.Parameter.empty:
            t = "string"
        else:
            origin = getattr(ann, "__name__", str(ann))
            if origin in ("int", "float", "bool"):
                t = {"int": "integer", "float": "number", "bool": "boolean"}.get(
                    origin, "string"
                )
        props[name] = {"type": t}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


class Agents:
    """
    Agent control-plane façade bound to one Channel.

    Human: ``ch.control(inc)`` / ``st.bind(inc)``
    Agent: ``ag.dispatch("inc", {})`` — same ``@ch.on`` handler.
    """

    def __init__(self, channel: Any) -> None:
        self.ch = channel
        self._facts: dict[str, Any] = {}
        self._allowed_extra: set[str] = set()
        self._blocked: set[str] = set()

    def peer(self, id: str, *, scopes: Sequence[str] = ()) -> AgentPeer:
        return AgentPeer(id=str(id), scopes=tuple(scopes))

    def tools_for(
        self,
        principal: Any = None,
        *,
        region: Optional[str] = None,
        role: Optional[str] = None,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        include_caps: bool = True,
    ) -> list[dict[str, Any]]:
        """MCP-shaped tool list from the same action registry as buttons."""
        reg = self.ch.registry
        names = list(reg.names())
        filtered: list[str] = []
        for n in names:
            meta = reg.action_meta(n)
            if meta.get("ax", True) is False:
                continue
            if region is not None and meta.get("region_uid") not in (region, None):
                ru = meta.get("region_uid")
                if ru != region and not (
                    isinstance(ru, str) and ru.startswith(region + ":")
                ):
                    if not n.startswith(region + "."):
                        continue
            if role is not None:
                roles = meta.get("roles") or []
                if roles and role not in roles:
                    continue
            filtered.append(n)
        names = filtered
        if include is not None:
            allow = set(include)
            names = [n for n in names if n in allow]
        if exclude:
            ban = set(exclude)
            names = [n for n in names if n not in ban]
        names = [n for n in names if n not in self._blocked]

        tools: list[dict[str, Any]] = []
        for name in names:
            fn = reg.get(name)
            if fn is None:
                continue
            meta = reg.action_meta(name)
            doc = (inspect.getdoc(fn) or "").strip().split("\n")[0] if fn else ""
            params = _tool_params_from_handler(fn)
            tool: dict[str, Any] = {
                "name": name,
                "description": doc or f"Action {name}",
                "parameters": params,
                "idempotent": bool(meta.get("idempotent")),
            }
            if include_caps and getattr(reg, "require_cap", False):
                try:
                    sub = None
                    if principal is not None:
                        sub = getattr(principal, "id", None) or str(principal)
                    tool["cap"] = reg.mint(name, {}, sub=sub)
                except Exception:
                    _log.debug(
                        "tools_for cap sign failed action=%s", name, exc_info=True
                    )
            tools.append(tool)
        return tools

    def mcp_tools(self, principal: Any = None, **kw: Any) -> list[dict[str, Any]]:
        return self.tools_for(principal, **kw)

    def situation(
        self,
        principal: Any = None,
        *,
        facts: Optional[Mapping[str, Any]] = None,
        notices: Optional[Sequence[str]] = None,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        region: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """AX world model — not Morph IR ``project_agent``."""
        merged = dict(self._facts)
        if region and facts is None:
            rdir = getattr(self.ch, "regions_dir", None) or getattr(
                self.ch, "region_tree", None
            )
            if rdir is not None:
                inst = rdir.get(region)
                if inst is not None and hasattr(inst, "facts"):
                    try:
                        merged.update(inst.facts(principal) or {})
                    except Exception:
                        _log.warning(
                            "region facts() failed region=%s", region, exc_info=True
                        )
        if facts:
            merged.update(facts)
        tools = self.tools_for(
            principal, include=include, exclude=exclude, region=region, role=role
        )
        allowed = [t["name"] for t in tools]
        for extra in self._allowed_extra:
            if extra not in allowed and extra not in self._blocked:
                if include is not None and extra not in set(include):
                    continue
                if exclude is not None and extra in set(exclude):
                    continue
                allowed.append(extra)
        blocked = sorted(self._blocked)
        if exclude:
            for e in exclude:
                if e not in blocked and e not in allowed:
                    blocked.append(str(e))
            blocked = sorted(set(blocked))
        return {
            "facts": merged,
            "allowed": allowed,
            "blocked": blocked,
            "notices": list(notices or ()),
            "principal": getattr(principal, "id", None)
            or (str(principal) if principal is not None else None),
            "tool_count": len(tools),
        }

    def set_facts(self, **facts: Any) -> "Agents":
        self._facts.update(facts)
        return self

    def block(self, *actions: str) -> "Agents":
        self._blocked.update(str(a) for a in actions)
        return self

    def allow(self, *actions: str) -> "Agents":
        self._allowed_extra.update(str(a) for a in actions)
        return self

    def unblock(self, *actions: str) -> "Agents":
        for a in actions:
            self._blocked.discard(str(a))
        return self

    def clear_policy(self) -> "Agents":
        self._blocked.clear()
        self._allowed_extra.clear()
        return self

    def dispatch(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        peer: Optional[AgentPeer] = None,
        principal: Any = None,
    ) -> Result:
        if action in self._blocked:
            r = Result.failure("forbidden", f"action {action!r} blocked for agents")
            r.meta["action"] = action
            return r
        p = peer or self.peer("agent")
        return dispatch_peer(
            self.ch, action, args, peer=p, principal=principal, async_=False
        )

    async def async_dispatch(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        peer: Optional[AgentPeer] = None,
        principal: Any = None,
    ) -> Result:
        if action in self._blocked:
            r = Result.failure("forbidden", f"action {action!r} blocked for agents")
            r.meta["action"] = action
            return r
        p = peer or self.peer("agent")
        return await dispatch_peer(
            self.ch, action, args, peer=p, principal=principal, async_=True
        )

    dispatch_async = async_dispatch

    def effects(self, result: Result, *, next_tools: Sequence[str] = ()) -> EffectReport:
        notices: list[str] = []
        changed: list[str] = []
        kinds: list[str] = []
        action = str((result.meta or {}).get("action") or "")
        for op in result.ops or []:
            if not isinstance(op, dict):
                continue
            kind = str(op.get("op") or "")
            kinds.append(kind)
            if kind in ("toast", "notice"):
                msg = op.get("message") or op.get("text")
                if msg:
                    notices.append(str(msg))
            if kind == "morph":
                t = op.get("target") or ""
                if "data-channel-id" in str(t):
                    import re

                    m = re.search(r'data-channel-id=["\']([^"\']+)', str(t))
                    if m:
                        changed.append(m.group(1))
                elif t:
                    changed.append(str(t))
            if kind == "signal.set":
                path = op.get("path")
                if path:
                    changed.append(f"signal:{path}")
            if kind in ("navigate", "go", "push_url"):
                changed.append("navigation")
        err = None
        if not result.ok and result.error is not None:
            err = getattr(result.error, "code", None) or str(result.error)
        return EffectReport(
            ok=bool(result.ok),
            action=action,
            notices=tuple(notices),
            changed=tuple(dict.fromkeys(changed)),
            next_tools=tuple(next_tools),
            error_code=err,
            op_kinds=tuple(kinds),
        )

    def explain(
        self,
        action: Optional[str] = None,
        *,
        region: Optional[str] = None,
        role: Optional[str] = None,
        principal: Any = None,
    ) -> dict[str, Any]:
        reg = self.ch.registry
        names = [action] if action else list(reg.names())
        if region:
            names = [
                n
                for n in names
                if reg.action_meta(n).get("region_uid") == region
                or n.startswith(region + ".")
            ]
        out = []
        allowed_set = {
            t["name"]
            for t in self.tools_for(
                principal, region=region, role=role, include_caps=False
            )
        }
        for n in names:
            meta = reg.action_meta(n)
            reasons = []
            ok = n in allowed_set
            if meta.get("ax", True) is False:
                reasons.append("ax=False")
            roles = meta.get("roles") or []
            if role and roles and role not in roles:
                reasons.append(f"role:{role} not in {roles}")
            if n in self._blocked:
                reasons.append("agents.blocked")
            if reg.get(n) is None:
                reasons.append("unknown")
                ok = False
            if ok and not reasons:
                reasons.append("allowed")
            out.append(
                {
                    "action": n,
                    "allowed": ok,
                    "reasons": reasons,
                    "meta": {
                        "region_uid": meta.get("region_uid"),
                        "roles": list(roles),
                        "ax": meta.get("ax", True),
                    },
                }
            )
        return {"items": out}

    def history(
        self,
        *,
        limit: int = 50,
        region: Optional[str] = None,
        principal: Any = None,
    ) -> list[dict[str, Any]]:
        audit = getattr(self.ch, "audit", None)
        if audit is None:
            return []
        try:
            pack = audit.export()
        except Exception:
            _log.warning("agents.history audit.export failed", exc_info=True)
            return []
        items = list(pack.get("intents") or [])
        if region:
            items = [
                i
                for i in items
                if i.get("region") == region
                or str(i.get("action", "")).startswith(region + ".")
            ]
        out = []
        for i in items[-limit:]:
            out.append(
                {
                    "action": i.get("action"),
                    "ok": i.get("ok"),
                    "ts": i.get("ts") or i.get("time"),
                }
            )
        return out

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "agents",
            "api": [
                "tools_for",
                "situation",
                "dispatch",
                "effects",
                "peer",
                "explain",
                "history",
            ],
            "law": "agent tool == button Intent (same registry)",
            "not": "DOM / project_agent tree dumps (use situation)",
            "peer_impl": "ux_channel.agent_runtime.peer",
        }


def agents(channel: Any) -> Agents:
    """Application: ``ag = agents(ch)``."""
    existing = getattr(channel, "agents_api", None)
    if isinstance(existing, Agents):
        return existing
    ag = Agents(channel)
    channel.agents_api = ag
    if not hasattr(channel, "ag"):
        channel.ag = ag
    return ag


def attach_agents(channel: Any) -> Agents:
    return agents(channel)
