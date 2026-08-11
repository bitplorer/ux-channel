"""Enterprise helpers — multi-tenant safety nets for production apps.
WHAT THIS MODULE IS FOR
Patterns that show up in real commerce / admin products:
1. **once=True capabilities** — money moves, refunds, irreversible deletes.
   Boot wires MemoryNonceStore so once-caps work without Redis in single-worker
   dev; multi-worker must use Redis nonce store.
2. **roles=[...]** on @ch.on — handler runs…"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from ux_channel.protocol.types import Result


@dataclass
class ActionPolicy:
    once: bool = False
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    audit: bool = False


@dataclass
class AuditEvent:
    ts: float
    action: str
    actor: Any
    detail: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """In-process audit ring (swap for SIEM in production)."""

    def __init__(self, *, retain: int = 5000):
        self.retain = retain
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def emit(self, action: str, *, actor: Any = None, **detail: Any) -> AuditEvent:
        ev = AuditEvent(ts=time.time(), action=action, actor=actor, detail=dict(detail))
        with self._lock:
            self._events.append(ev)
            if len(self._events) > self.retain:
                self._events = self._events[-self.retain :]
        return ev

    def list(self, *, limit: int = 100, action: str | None = None) -> list[AuditEvent]:
        with self._lock:
            items = list(self._events)
        if action:
            items = [e for e in items if e.action == action]
        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


def paginate(
    items: Sequence[Any],
    *,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """Stable list pagination for region loaders."""
    page = max(1, int(page or 1))
    per_page = max(1, min(200, int(per_page or 20)))
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    if page > pages:
        page = pages
    start = (page - 1) * per_page
    slice_ = list(items[start : start + per_page])
    return {
        "items": slice_,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


def roles_of(principal: Any, ctx: Any = None) -> set[str]:
    """Roles from principal claims/scopes only (never ctx.scope)."""
    found: set[str] = set()
    if principal is None and ctx is not None:
        principal = getattr(ctx, "principal", None)
    if principal is None:
        return found
    if isinstance(principal, Mapping):
        r = principal.get("roles") or principal.get("role") or ()
    else:
        r = getattr(principal, "roles", None) or getattr(principal, "role", None)
        if not r and hasattr(principal, "claims"):
            r = (principal.claims or {}).get("roles") or (principal.claims or {}).get("role")
        if not r and hasattr(principal, "scopes"):
            r = principal.scopes
        r = r or ()
    if isinstance(r, str):
        found.add(r)
    else:
        found.update(map(str, r or ()))
    return found


def require_roles(
    ch: Any,
    allowed: Sequence[str],
    *,
    principal: Any = None,
    ctx: Any = None,
) -> Optional[Result]:
    """Return err Result if role check fails; else None."""
    if not allowed:
        return None
    have = roles_of(principal, ctx)
    need = set(allowed)
    if have & need:
        return None
    # also allow roles passed as kwargs key on ctx
    return ch.fail.forbidden("insufficient role")


class PolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[str, ActionPolicy] = {}
        self._lock = threading.Lock()

    def set(self, action: str, policy: ActionPolicy) -> None:
        with self._lock:
            self._policies[action] = policy

    def get(self, action: str) -> ActionPolicy:
        with self._lock:
            return self._policies.get(action, ActionPolicy())


def attach_enterprise(channel: Any) -> None:
    """Attach audit, policy, paginate; ensure nonce store for once-caps."""
    from ux_channel.host.idempotency import MemoryIdempotencyStore
    from ux_channel.host.nonce import MemoryNonceStore

    reg = channel.registry
    if getattr(reg, "nonce_store", None) is None:
        reg.nonce_store = MemoryNonceStore()
    if getattr(reg, "idempotency_store", None) is None:
        reg.idempotency_store = MemoryIdempotencyStore()

    channel.audit_log = AuditLog()
    channel.policies = PolicyRegistry()

    def audit(action: str, *, actor: Any = None, **detail: Any) -> AuditEvent:
        return channel.audit_log.emit(action, actor=actor, **detail)

    channel.audit = audit
    channel.paginate = staticmethod(paginate) if False else paginate
    # bind as function
    channel.paginate = paginate

    # Patch mint/attrs/button to honor policy.once automatically
    _orig_mint = channel.mint

    def mint(action: str, args: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> str:
        pol = channel.policies.get(action)
        if pol.once and "once" not in kwargs:
            kwargs["once"] = True
        if pol.scopes and "scopes" not in kwargs:
            kwargs["scopes"] = list(pol.scopes)
        return _orig_mint(action, args, **kwargs)

    channel.mint = mint

    _orig_attrs = channel._protocol_attrs

    def attrs(action: str, **kwargs: Any) -> str:
        pol = channel.policies.get(action)
        if pol.once and not kwargs.get("once"):
            kwargs["once"] = True
        return _orig_attrs(action, **kwargs)

    channel._protocol_attrs = attrs
