"""Thin present-cap-must-verify dispatch used by HostRuntime.

Production Channel uses ActionRegistry. This path keeps the architecture
e2e contract (dict Intent/Result) on top of production CapService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Set

from ux_channel.protocol.capability import CapError, CapService

Handler = Callable[[Mapping[str, Any], dict], dict]


@dataclass
class RegistryConfig:
    require_cap: bool = True
    open_actions: Set[str] = field(default_factory=set)


@dataclass
class ArchRegistry:
    caps: CapService
    config: RegistryConfig = field(default_factory=RegistryConfig)
    _handlers: Dict[str, Handler] = field(default_factory=dict)

    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    def dispatch(self, intent: Mapping[str, Any]) -> dict:
        action = str(intent.get("action") or "")
        args = dict(intent.get("args") or {})
        cap_token = intent.get("cap")
        meta: dict[str, Any] = {"action": action}
        if intent.get("request_id") is not None:
            meta["request_id"] = intent["request_id"]

        if action not in self._handlers:
            return {
                "ok": False,
                "ops": [],
                "error": {"code": "not_found", "message": f"unknown action {action}"},
                "meta": meta,
            }

        needs_cap = self.config.require_cap and action not in self.config.open_actions
        if needs_cap or cap_token:
            if not cap_token:
                return _unauth("missing capability", meta)
            try:
                self.caps.verify(str(cap_token), action, args, consume_once=True)
            except CapError as e:
                return _unauth(str(e), meta)

        ctx: dict = {"action": action}
        result = self._handlers[action](args, ctx)
        if not isinstance(result, dict):
            result = {"ok": True, "ops": []}
        result.setdefault("ok", True)
        result.setdefault("ops", [])
        m = dict(result.get("meta") or {})
        m.update({k: v for k, v in meta.items() if v is not None})
        result["meta"] = m
        return result


def _unauth(message: str, meta: dict) -> dict:
    return {
        "ok": False,
        "ops": [],
        "error": {"code": "unauthorized", "message": message},
        "meta": meta,
    }
