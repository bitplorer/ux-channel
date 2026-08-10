"""
ActionContext — request-scoped context for handlers.

Injected optionally when action signature accepts ``ctx: ActionContext``.
Carries principal, deadlines, request_id, and tracer correlation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional


@dataclass
class Principal:
    """Authenticated subject. ``sub`` is an alias of ``id`` (JWT-style)."""

    id: str
    scopes: tuple[str, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(
        cls,
        id: str | None = None,
        *,
        sub: str | None = None,
        roles: Any = None,
        scopes: tuple[str, ...] = (),
        claims: dict[str, Any] | None = None,
    ) -> "Principal":
        pid = id if id is not None else sub
        if pid is None:
            raise TypeError("Principal.of requires id= or sub=")
        cl = dict(claims or {})
        sc = list(scopes or ())
        if roles is not None:
            role_list = list(roles) if not isinstance(roles, str) else [roles]
            cl.setdefault("roles", role_list)
            sc.extend(role_list)
        return cls(id=str(pid), scopes=tuple(dict.fromkeys(sc)), claims=cl)

    @property
    def sub(self) -> str:
        return self.id

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes

    def has_role(self, role: str) -> bool:
        roles = self.claims.get("roles") or []
        return role in roles or role in self.scopes


@dataclass
class ActionContext:
    """
    Per-invocation context available to action handlers.

    Usage::

        @reg.action(\"Orders.place\")
        async def place(ctx: ActionContext, item_id: str):
            if not ctx.principal or not ctx.principal.has_scope(\"orders:write\"):
                raise ActionError(\"forbidden\", \"no scope\")
            ...
    """

    request_id: str
    action: str
    principal: Optional[Principal] = None
    trace_id: Optional[str] = None
    deadline_monotonic: Optional[float] = None
    idempotency_key: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)
    # Host may stash raw request (framework-specific)
    request: Any = None

    def remaining_s(self) -> Optional[float]:
        if self.deadline_monotonic is None:
            return None
        return max(0.0, self.deadline_monotonic - time.monotonic())

    def check_deadline(self) -> None:
        rem = self.remaining_s()
        if rem is not None and rem <= 0:
            raise TimeoutError("action deadline exceeded")

    @property
    def user_id(self) -> Optional[str]:
        """Subject id when principal is set (enterprise handlers use ctx.user_id)."""
        if self.principal is not None:
            return str(getattr(self.principal, "id", None) or getattr(self.principal, "sub", "") or "") or None
        return None

    @property
    def subject(self) -> Optional[str]:
        return self.user_id

    def key(self, name: str, default: Any = None) -> Any:
        """Read from meta/request scope if hosts stash keys; else default.

        Region loaders use ``ctx.key("tenant_id", "t1")``. Prefer principal claims,
        then meta, then default.
        """
        if self.principal is not None:
            claims = getattr(self.principal, "claims", None) or {}
            if name in claims:
                return claims[name]
        meta = self.meta or {}
        if name in meta:
            return meta[name]
        # common aliases
        if name == "user_id":
            return self.user_id if self.user_id is not None else default
        return default


AuthResolver = Callable[[Any], Optional[Principal]]
