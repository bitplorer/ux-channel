"""
Safe agent/MCP tool runner — the only path agents should use to hit actions.

CONTRIBUTION
------------
UI clicks use Intent + caps. Agents use AgentRunner.call_tool which:
  1. Enforces AgentPolicy (allow/deny/confirm/read_only)
  2. Enforces session budgets
  3. Builds Intent with agent principal + agent-scoped meta
  4. Optionally dry-runs
  5. Writes AuditEvent
  6. Dispatches via ActionRegistry (same pipeline as humans)

This keeps one security pipeline, two entry surfaces (UI vs agent).
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ux_channel.agent_runtime.tool_audit import (
    AuditEvent,
    AuditSink,
    LoggingAuditSink,
    redact_args,
)
from ux_channel.agent_runtime.session import AgentSession
from ux_channel.agent_runtime.tools import ToolMeta
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result


@dataclass
class ToolCall:
    """MCP-shaped tool call."""

    name: str
    arguments: dict[str, Any]
    # Client must pass confirmation token for dangerous/confirm_actions
    confirmation: Optional[str] = None
    dry_run: Optional[bool] = None
    call_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class AgentRunner:
    """
    Production-safe façade for agent tool execution.

    Usage::

        policy = AgentPolicy.production(allow=[\"Search.query\", \"Docs.get\"])
        session = AgentSession(agent_id=\"support-bot\", policy=policy)
        runner = AgentRunner(registry, session)
        result = await runner.call_tool_async(ToolCall(\"Search.query\", {\"q\": \"uid\"}))
    """

    def __init__(
        self,
        registry: ActionRegistry,
        session: AgentSession,
        *,
        audit: Optional[AuditSink] = None,
        # If set, confirmation string must match for confirm_actions
        confirmation_secret: Optional[str] = None,
        # Cap signing for agent path (optional; can disable require_cap for agent-only reg)
        mint_caps: bool = True,
    ):
        self.registry = registry
        self.session = session
        self.audit = audit or LoggingAuditSink()
        self.confirmation_secret = confirmation_secret
        self.mint_caps = mint_caps

    def list_tools(self, *, only_marked: bool = False) -> list[dict[str, Any]]:
        from ux_channel.agent_runtime.tools import tools_from_registry

        tools = tools_from_registry(self.registry, only_marked=only_marked)
        # Filter by policy
        return [t for t in tools if self.session.policy.allows(t["name"])]

    def call_tool(self, call: ToolCall | Mapping[str, Any]) -> Result:
        if not isinstance(call, ToolCall):
            call = ToolCall(
                name=str(call.get("name") or call.get("action")),
                arguments=dict(call.get("arguments") or call.get("args") or {}),
                confirmation=call.get("confirmation"),
                dry_run=call.get("dry_run"),
                call_id=call.get("call_id") or call.get("id"),
                idempotency_key=call.get("idempotency_key"),
            )
        return self.registry.dispatch(self._to_intent(call, dry_run=self._dry(call))) if not self._is_async_needed(call) else self._sync_guard(call)

    async def call_tool_async(self, call: ToolCall | Mapping[str, Any]) -> Result:
        if not isinstance(call, ToolCall):
            call = ToolCall(
                name=str(call.get("name") or call.get("action")),
                arguments=dict(call.get("arguments") or call.get("args") or {}),
                confirmation=call.get("confirmation"),
                dry_run=call.get("dry_run"),
                call_id=call.get("call_id") or call.get("id"),
                idempotency_key=call.get("idempotency_key"),
            )
        t0 = time.perf_counter()
        blocked = self._precheck(call)
        if blocked is not None:
            self._audit(call, blocked, t0)
            return blocked

        dry = self._dry(call)
        if dry:
            result = Result.success(
                meta={
                    "dry_run": True,
                    "action": call.name,
                    "agent_id": self.session.agent_id,
                    "session_id": self.session.session_id,
                }
            )
            # empty ops + ok means planned — attach preview in meta
            result = Result(
                ok=True,
                ops=[],
                meta={
                    "dry_run": True,
                    "would_call": call.name,
                    "arguments": redact_args(call.arguments),
                    "agent_id": self.session.agent_id,
                    "session_id": self.session.session_id,
                },
            )
            self.session.record_call()
            self._audit(call, result, t0)
            return result

        intent = self._to_intent(call, dry_run=False)
        # Bind agent principal via temporary auth_resolver if none
        prev = self.registry.auth_resolver
        principal = self.session.principal

        def _resolve(_req):
            return principal

        self.registry.auth_resolver = _resolve
        try:
            result = await self.registry.async_dispatch(intent)
        finally:
            self.registry.auth_resolver = prev

        self.session.record_call()
        self._audit(call, result, t0)
        return result

    def _is_async_needed(self, call: ToolCall) -> bool:
        return True  # prefer async path documentation; sync uses dispatch

    def _sync_guard(self, call: ToolCall) -> Result:
        t0 = time.perf_counter()
        blocked = self._precheck(call)
        if blocked is not None:
            self._audit(call, blocked, t0)
            return blocked
        if self._dry(call):
            result = Result(
                ok=True,
                ops=[],
                meta={
                    "dry_run": True,
                    "would_call": call.name,
                    "arguments": redact_args(call.arguments),
                },
            )
            self.session.record_call()
            self._audit(call, result, t0)
            return result
        intent = self._to_intent(call, dry_run=False)
        prev = self.registry.auth_resolver
        principal = self.session.principal

        def _resolve(_req):
            return principal

        self.registry.auth_resolver = _resolve
        try:
            result = self.registry.dispatch(intent)
        finally:
            self.registry.auth_resolver = prev
        self.session.record_call()
        self._audit(call, result, t0)
        return result

    def _dry(self, call: ToolCall) -> bool:
        if call.dry_run is not None:
            return bool(call.dry_run)
        return bool(self.session.policy.dry_run_default)

    def _precheck(self, call: ToolCall) -> Optional[Result]:
        policy = self.session.policy
        action = call.name
        if not action:
            return Result.failure("bad_request", "tool name required")

        budget = self.session.check_budget()
        if budget:
            return Result.failure(
                budget,
                "agent budget exceeded",
                retryable=budget == "agent_budget_rate",
            )

        if not policy.allows(action):
            return Result.failure("forbidden", f"action not allowed for agent: {action}")

        # payload size
        try:
            raw = _serde.dumps(call.arguments, default=str)
        except Exception:
            return Result.failure("bad_request", "arguments not JSON-serializable")
        if len(raw.encode("utf-8")) > policy.max_payload_bytes:
            return Result.failure("payload_too_large", "tool arguments too large")

        fn = self.registry.get(action)
        if fn is None:
            return Result.failure("not_found", f"unknown action: {action}")

        meta: Optional[ToolMeta] = getattr(fn, "__ux_tool__", None)
        if policy.read_only and meta and not meta.read_only:
            return Result.failure("forbidden", "read_only agent cannot call write tool")
        if policy.read_only and meta is None:
            # unmarked treated as write under strict read_only
            return Result.failure("forbidden", "read_only agent requires agent_tool(read_only=True)")

        if policy.required_scopes and self.session.principal:
            for sc in policy.required_scopes:
                if not self.session.principal.has_scope(sc):
                    return Result.failure("forbidden", f"missing scope: {sc}")

        if policy.needs_confirmation(action) or (meta and meta.dangerous):
            if not self._confirmed(call):
                meta_out: dict = {
                    "confirmation_required": True,
                    "action": action,
                    "would_call": action,
                }
                # mint signed confirm token when we have a secret (>=16)
                secret = self.confirmation_secret or getattr(
                    getattr(self.registry, "config", None), "secret", None
                )
                if secret and len(str(secret)) >= 16:
                    try:
                        from ux_channel.mcp.confirm import mint_confirm_token

                        tok, exp = mint_confirm_token(
                            str(secret),
                            action=action,
                            arguments=call.arguments,
                            session_id=self.session.session_id,
                            agent_id=self.session.agent_id,
                        )
                        meta_out["confirm_token"] = tok
                        meta_out["confirm_expires_at"] = exp
                    except Exception:
                        pass
                return Result.failure(
                    "confirmation_required",
                    f"action {action} requires confirmation",
                    **meta_out,
                )

        return None

    def _confirmed(self, call: ToolCall) -> bool:
        if not call.confirmation:
            return False

        def _deny(reason: str) -> bool:
            try:
                from ux_channel.security.security_events import emit_security

                emit_security(
                    "agent_confirm_denied",
                    action=getattr(call, "name", "") or "",
                    reason=reason,
                    principal=str(
                        getattr(getattr(self, "session", None), "agent_id", "") or ""
                    ),
                )
            except Exception:
                pass
            return False

        secret = self.confirmation_secret or getattr(
            getattr(self.registry, "config", None), "secret", None
        )
        if secret and len(str(secret)) >= 16:
            from ux_channel.mcp.confirm import verify_confirm_token

            store = getattr(self, "_confirm_nonces", None)
            if store is None:
                self._confirm_nonces = set()  # type: ignore[attr-defined]
                store = self._confirm_nonces
            ok, reason = verify_confirm_token(
                str(secret),
                call.confirmation,
                action=call.name,
                arguments=call.arguments,
                session_id=self.session.session_id,
                agent_id=self.session.agent_id,
                nonce_store=store,
            )
            if isinstance(store, set) and len(store) > 50_000:
                for _ in range(len(store) // 10):
                    store.pop()
            if not ok:
                return _deny(str(reason or "invalid confirmation token"))
            return True
        # Fail closed without signing secret
        return _deny("confirmation_secret not configured")

    def _to_intent(self, call: ToolCall, *, dry_run: bool) -> Intent:
        args = dict(call.arguments)
        cap = None
        if self.mint_caps and self.registry.require_cap:
            # agent path: sign with empty extra; principal bound via auth_resolver
            sub = self.session.principal.id if self.session.principal else None
            cap = self.registry.mint(call.name, args, sub=sub, once=False)
        return Intent(
            action=call.name,
            args=args,
            cap=cap,
            request_id=f"agent_{call.call_id or self.session.session_id}_{self.session.call_count}",
            idempotency_key=call.idempotency_key,
            meta={
                "agent_id": self.session.agent_id,
                "session_id": self.session.session_id,
                "source": "agent",
                "dry_run": dry_run,
            },
        )

    def _audit(self, call: ToolCall, result: Result, t0: float) -> None:
        ms = (time.perf_counter() - t0) * 1000
        ev = AuditEvent(
            ts=time.time(),
            session_id=self.session.session_id,
            agent_id=self.session.agent_id,
            action=call.name,
            ok=result.ok,
            duration_ms=round(ms, 3),
            request_id=result.meta.get("request_id") if result.meta else None,
            error_code=result.error.code if result.error else None,
            dry_run=bool(result.meta.get("dry_run")) if result.meta else False,
            confirmed=bool(call.confirmation),
            args_preview=redact_args(call.arguments),
            meta={"call_id": call.call_id},
        )
        self.audit.write(ev)
