"""Intent log — ordered record of dispatched Intents (support / audit).

* **Prefer product façade:** ``attach_audit(ch)`` (pairs log + forensics).
* Not a substitute for your business event store."""


from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Optional, Protocol, Sequence

from ux_channel.protocol.types import Intent, Result

__all__ = ["IntentLogEntry", "IntentLog", "MemoryIntentLog", "attach_intent_log"]


@dataclass
class IntentLogEntry:
    seq: int
    ts: float
    action: str
    args_keys: tuple[str, ...]
    ok: bool
    error_code: Optional[str]
    op_kinds: tuple[str, ...]
    principal: Optional[str] = None
    request_id: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "action": self.action,
            "args_keys": list(self.args_keys),
            "ok": self.ok,
            "error_code": self.error_code,
            "op_kinds": list(self.op_kinds),
            "principal": self.principal,
            "request_id": self.request_id,
            "meta": dict(self.meta),
        }


class IntentLog(Protocol):
    def append(
        self,
        intent: Intent | Mapping[str, Any],
        result: Result,
        *,
        principal: Optional[str] = None,
    ) -> IntentLogEntry: ...

    def since(self, seq: int = 0) -> list[IntentLogEntry]: ...

    def replay_ops(self, *, from_seq: int = 0, to_seq: Optional[int] = None) -> list[str]:
        """Return op kinds in order (audit-friendly; not full HTML)."""
        ...


class MemoryIntentLog:
    """Process-local ring buffer (prod: wrap Redis/DB similarly)."""

    def __init__(self, *, maxlen: int = 10_000) -> None:
        self._maxlen = max(100, int(maxlen))
        self._entries: list[IntentLogEntry] = []
        self._seq = 0
        self._lock = threading.RLock()

    def append(
        self,
        intent: Intent | Mapping[str, Any],
        result: Result,
        *,
        principal: Optional[str] = None,
    ) -> IntentLogEntry:
        if isinstance(intent, Intent):
            action = intent.action
            args = intent.args or {}
            rid = intent.request_id
        else:
            action = str(intent.get("action", "?"))
            args = dict(intent.get("args") or {})
            rid = intent.get("request_id")
        ops = tuple(str(o.get("op", "?")) for o in (result.ops or []) if isinstance(o, Mapping))
        err = None
        if not result.ok and result.error is not None:
            err = getattr(result.error, "code", None) or str(result.error)
        with self._lock:
            self._seq += 1
            entry = IntentLogEntry(
                seq=self._seq,
                ts=time.time(),
                action=action,
                args_keys=tuple(sorted(str(k) for k in args.keys())),
                ok=bool(result.ok),
                error_code=err,
                op_kinds=ops,
                principal=principal,
                request_id=rid,
            )
            self._entries.append(entry)
            if len(self._entries) > self._maxlen:
                self._entries = self._entries[-self._maxlen :]
            return entry

    def since(self, seq: int = 0) -> list[IntentLogEntry]:
        with self._lock:
            return [e for e in self._entries if e.seq > seq]

    def replay_ops(self, *, from_seq: int = 0, to_seq: Optional[int] = None) -> list[str]:
        out: list[str] = []
        for e in self.since(from_seq):
            if to_seq is not None and e.seq > to_seq:
                break
            out.extend(e.op_kinds)
        return out

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


def attach_intent_log(
    channel: Any,
    log: Any = None,
    *,
    redis_url: Optional[str] = None,
    maxlen: int = 10_000,
) -> Any:
    """
    After-hook: record every dispatch on ``channel.registry``.

    * Default: ``MemoryIntentLog``
    * Multi-worker: ``redis_url=`` or ``log=RedisIntentLog(...)``

    Does not import ux-dom. Safe to call once at boot.
    """
    if log is None and redis_url:
        from ux_channel.redis_extra import RedisIntentLog

        bag: Any = RedisIntentLog(redis_url, maxlen=maxlen)
    else:
        bag = log if log is not None else MemoryIntentLog()
    reg = channel.registry
    log_ref = bag  # stable closure name

    def _intent_log_after(intent: Any, result: Any) -> Any:
        principal = None
        try:
            resolve = getattr(reg, "_resolve_principal", None)
            if callable(resolve):
                pr = resolve()
                if pr is not None:
                    principal = getattr(pr, "id", None)
        except Exception:
            principal = None
        try:
            log_ref.append(intent, result, principal=principal)
        except Exception:
            import logging
            logging.getLogger("ux_channel.devtools.intent_log").exception("intent log append failed")
        return result

    reg.after(_intent_log_after)
    channel.intent_log = bag
    return bag
