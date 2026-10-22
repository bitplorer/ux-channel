"""
ActionContext — request-scoped context for handlers.

Injected optionally when action signature accepts ``ctx: ActionContext``.
Carries principal, deadlines, request_id, tracer correlation, and what the
Cap Host verified (``ctx.verified``).
"""

from __future__ import annotations

import copy
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
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


# Context keys that name the caller. They are filled from the principal only:
# an Intent arg with one of these names is client data, never identity.
IDENTITY_KEYS = ("user_id", "subject", "sub")


def cap_subject(claims: Mapping[str, Any]) -> Optional[str]:
    """Cap subject from verify output: cek-runtime Host ``subject``, classic ``sub``."""
    subject = claims.get("subject", claims.get("sub"))
    return None if subject is None else str(subject)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    return copy.deepcopy(value)


@dataclass(frozen=True)
class VerifiedContext:
    """What the Cap Host verified for this Intent. Deeply read-only.

    Built only from the claims ``verify`` returned (cek-runtime Host, or
    classic ``CapService``), never from Intent args. ``subject`` is the
    subject the Cap is bound to (SPEC/capability.md rule 5), ``None`` when
    the Cap names none. ``claims`` is frozen recursively: mappings are
    ``MappingProxyType``, lists are tuples, sets are frozensets.
    """

    action: str
    subject: Optional[str]
    claims: Mapping[str, Any]

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> "VerifiedContext":
        frozen = _freeze(claims)
        return cls(
            action=str(frozen["action"]),
            subject=cap_subject(frozen),
            claims=frozen,
        )


_verified: ContextVar[Optional[VerifiedContext]] = ContextVar(
    "ux_channel_verified", default=None
)


def current_verified() -> Optional[VerifiedContext]:
    """The verified Cap of the action running now, or ``None``.

    ``None`` outside a dispatch (a page paint, a push render) and for an
    Intent that carried no Cap. The registry binds it around the handler and
    the Result encode, so a region repainted for the action sees it too.
    """
    return _verified.get()


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

    ``principal`` is the authenticated principal (``dispatch(principal=)`` or
    ``auth_resolver``) or ``None``; ``subject`` and ``user_id`` are its id.
    None of them, nor the identity keys of ``meta``, ever come from Intent
    args. ``verified`` is the verified Cap, or ``None`` when the Intent carried
    no Cap.
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
    verified: Optional[VerifiedContext] = None

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
