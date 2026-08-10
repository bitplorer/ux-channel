"""
Client + db safety helpers for ``ux_channel.state``.

Application entry: ``from ux_channel import state`` — not this module.

Path risk set is **sector-neutral authority** (payments, inventory, clinical, secrets…).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.protocol.ops import signal_set, toast
from ux_channel.host.ssr_state import SsrState, ssr_state
from ux_channel.protocol.types import Result

__all__ = [
    "planes",
    "attach_planes",
    "Planes",
    "ClientPlane",
    "Db",
    "ClientSafetyError",
    "path_is_risky",
    "RISKY_SEGMENTS",
]

RISKY_SEGMENTS = frozenset(
    {
        "amount",
        "price",
        "total",
        "balance",
        "payment",
        "pay",
        "charge",
        "cart",
        "order",
        "checkout",
        "card",
        "cvv",
        "cvc",
        "pan",
        "money",
        "currency",
        "salary",
        "wage",
        "inventory",
        "stock",
        "quota",
        "capacity",
        "allocation",
        "dosage",
        "dose",
        "prescription",
        "score",
        "limit",
        "credits",
        "password",
        "passwd",
        "secret",
        "token",
        "cap",
        "apikey",
        "api_key",
        "private_key",
        "ssn",
    }
)

_RISKY_SUFFIXES = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "apikey",
        "api_key",
        "private_key",
        "ssn",
        "cvv",
        "cvc",
        "amount",
        "balance",
        "quota",
        "dosage",
    }
)

_MAX_PATH_LEN = 256
_SEG = re.compile(r"^[A-Za-z0-9_@+-]+$")


class ClientSafetyError(ValueError):
    """Client path / value rejected as unsafe or not allowlisted."""


def path_is_risky(path: str) -> bool:
    if path is None or not str(path).strip():
        return True
    raw = str(path).strip().replace("-", "_")
    if len(raw) > _MAX_PATH_LEN:
        return True
    for seg in raw.split("."):
        if not seg:
            return True
        if seg in RISKY_SEGMENTS:
            return True
        for sfx in _RISKY_SUFFIXES:
            if seg == sfx or seg.endswith("_" + sfx):
                return True
    return False


def _validate_client_path(path: str) -> str:
    p = str(path or "").strip()
    if not p or len(p) > _MAX_PATH_LEN:
        raise ClientSafetyError(f"invalid client path: {path!r}")
    if ".." in p or p.startswith(".") or p.endswith("."):
        raise ClientSafetyError(f"invalid client path: {path!r}")
    for seg in p.replace("-", "_").split("."):
        if not seg or not _SEG.match(seg):
            raise ClientSafetyError(f"invalid client path segment: {seg!r}")
    return p


class ClientPlane:
    """Browser bag — signal.set ops; never durable Quantity types."""

    def __init__(
        self,
        *,
        persist_allowlist: Sequence[str] = (),
        strict: bool = True,
    ) -> None:
        self._allow = {str(x) for x in persist_allowlist}
        self.strict = bool(strict)
        self._pending: list[dict[str, Any]] = []

    def configure(
        self,
        *,
        persist_allowlist: Optional[Sequence[str]] = None,
        strict: Optional[bool] = None,
    ) -> "ClientPlane":
        if persist_allowlist is not None:
            self._allow = {str(x) for x in persist_allowlist}
        if strict is not None:
            self.strict = bool(strict)
        return self

    def allow(self, *paths: str) -> "ClientPlane":
        self._allow.update(str(p) for p in paths)
        return self

    def _persist_allowed(self, path: str) -> bool:
        return path in self._allow

    def check(self, path: str, *, persist: bool = False) -> str:
        p = _validate_client_path(path)
        if path_is_risky(p):
            if persist or self.strict:
                raise ClientSafetyError(
                    f"client path {p!r} looks like durable quantity — use your store"
                )
        if persist and not self._persist_allowed(p):
            raise ClientSafetyError(
                f"client path {p!r} not on persist allowlist {sorted(self._allow)}"
            )
        return p

    def op(
        self,
        path: str,
        value: Any,
        *,
        persist: bool = False,
    ) -> dict[str, Any]:
        p = self.check(path, persist=persist)
        try:
            from ux_channel.foundations.quantity import Quantity

            if isinstance(value, Quantity):
                raise ClientSafetyError(
                    "Quantity type cannot be stored in client bag"
                )
        except ImportError:
            pass
        body = dict(signal_set(p, value))
        if persist:
            body["persist"] = True
        return body

    def set(self, path: str, value: Any, *, persist: bool = False) -> "ClientPlane":
        self._pending.append(self.op(path, value, persist=persist))
        return self

    def push(self, mapping: Mapping[str, Any], *, persist: bool = False) -> "ClientPlane":
        for k, v in mapping.items():
            self.set(str(k), v, persist=persist)
        return self

    def take(self) -> list[dict[str, Any]]:
        ops, self._pending = self._pending, []
        return ops

    def flush(self, *, notice: Optional[str] = None) -> Result:
        ops = self.take()
        if notice:
            ops = list(ops) + [toast(str(notice))]
        return Result.success(*ops) if ops else Result.success()

    def __call__(
        self,
        path: str,
        value: Any,
        *,
        persist: bool = False,
    ) -> Result:
        op = self.op(path, value, persist=persist)
        pending = self.take()
        return Result.success(*(pending + [op]))

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "client",
            "strict": self.strict,
            "persist_allowlist": sorted(self._allow),
            "pending": len(self._pending),
        }


class Db:
    """Guards only — channel does not store your durable data."""

    def __init__(self, *, banned: Sequence[str] = ()) -> None:
        self._banned = {str(x) for x in banned}

    def ban_request_keys(
        self,
        mapping: Mapping[str, Any],
        *,
        banned: Optional[Sequence[str]] = None,
    ) -> None:
        ban = set(self._banned)
        if banned:
            ban.update(str(x) for x in banned)
        for k, v in mapping.items():
            key = str(k)
            if v in (None, ""):
                continue
            if key in ban:
                raise ClientSafetyError(f"request key {key!r} is banned")
            if path_is_risky(key):
                raise ClientSafetyError(
                    f"request key {key!r} looks like durable quantity from client"
                )

    def guard(self, args: Optional[Mapping[str, Any]] = None) -> None:
        self.ban_request_keys(dict(args or {}))

    def require(self, **loaded: Any) -> None:
        for k, v in loaded.items():
            if path_is_risky(k) and v is None:
                raise ClientSafetyError(
                    f"db.require: {k!r} missing — load from durable store"
                )

    def describe(self) -> dict[str, Any]:
        return {"kind": "db", "banned": sorted(self._banned), "role": "guards_only"}


@dataclass
class Planes:
    session: SsrState
    client: ClientPlane
    db: Db = field(default_factory=Db)


def attach_planes(
    channel: Any,
    *,
    persist_allowlist: Sequence[str] = (),
    client_strict: bool = True,
    prefix: str = "ui.",
) -> Planes:
    existing = getattr(channel, "_planes", None)
    if isinstance(existing, Planes):
        existing.client.configure(
            persist_allowlist=persist_allowlist,
            strict=client_strict,
        )
        return existing
    bag = ssr_state(channel, prefix=prefix)
    client = ClientPlane(
        persist_allowlist=persist_allowlist,
        strict=client_strict,
    )
    pl = Planes(session=bag, client=client, db=Db())
    channel._planes = pl
    return pl


def planes(
    channel: Any,
    *,
    persist_allowlist: Sequence[str] = (),
    client_strict: bool = True,
) -> Planes:
    """Thin alias — prefer ``state(ch)``."""
    return attach_planes(
        channel,
        persist_allowlist=persist_allowlist,
        client_strict=client_strict,
    )
