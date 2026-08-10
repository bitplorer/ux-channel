"""
Ticket revocation — logout / ban kills live push tickets.

WHY
---
HMAC tickets cannot be "deleted" cryptographically. A process-local or Redis
denylist (by jti / raw token hash) makes logout meaningful for SSE/WS.

USAGE
-----
::

    from ux_channel.devtools.ticket_revoke import get_revocation_list
    get_revocation_list().revoke(ticket)
    assert get_revocation_list().is_revoked(ticket)
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Optional, Protocol


def _token_id(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()[:32]


class RevocationStore(Protocol):
    def revoke(self, token_id: str, *, ttl_s: float = 3600) -> None: ...
    def is_revoked(self, token_id: str) -> bool: ...


class MemoryRevocationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._until: dict[str, float] = {}

    def revoke(self, token_id: str, *, ttl_s: float = 3600) -> None:
        with self._lock:
            self._until[token_id] = time.time() + max(1.0, float(ttl_s))

    def is_revoked(self, token_id: str) -> bool:
        now = time.time()
        with self._lock:
            exp = self._until.get(token_id)
            if exp is None:
                return False
            if exp < now:
                del self._until[token_id]
                return False
            return True


class RedisRevocationStore:
    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:revoke:") -> None:
        from ux_channel.redis_extra import _client

        self.r = _client(redis_url)
        self.prefix = prefix

    def revoke(self, token_id: str, *, ttl_s: float = 3600) -> None:
        self.r.set(f"{self.prefix}{token_id}", "1", ex=int(max(1, ttl_s)))

    def is_revoked(self, token_id: str) -> bool:
        return bool(self.r.get(f"{self.prefix}{token_id}"))


class TicketRevocationList:
    def __init__(self, store: Optional[RevocationStore] = None) -> None:
        self.store: RevocationStore = store or MemoryRevocationStore()

    def revoke(self, ticket: str, *, ttl_s: float = 3600) -> None:
        if not ticket:
            return
        self.store.revoke(_token_id(ticket), ttl_s=ttl_s)

    def is_revoked(self, ticket: str) -> bool:
        if not ticket:
            return False
        return self.store.is_revoked(_token_id(ticket))


_list: Optional[TicketRevocationList] = None
_lock = threading.Lock()


def get_revocation_list() -> TicketRevocationList:
    global _list
    with _lock:
        if _list is None:
            _list = TicketRevocationList()
        return _list


def set_revocation_list(lst: TicketRevocationList) -> None:
    global _list
    with _lock:
        _list = lst
