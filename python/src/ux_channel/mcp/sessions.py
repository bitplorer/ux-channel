"""
Claim-bound MCP sessions.

Memory store (default) or Redis when ``redis_url`` is configured.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "McpSession",
    "McpSessionStore",
    "MemoryMcpSessionStore",
    "RedisMcpSessionStore",
    "get_session_store",
    "set_session_store",
    "build_session_store",
]


@dataclass
class McpSession:
    """
    Claim-bound MCP session (room + scopes + verticals + ticket).

    ``ticket`` authenticates tools/resources; ``exp`` is unix expiry.
    """
    session_id: str
    agent_id: str
    room: str
    sub: str
    scopes: frozenset[str]
    verticals: tuple[str, ...]
    ticket: str
    exp: float
    policy_allow: frozenset[str] = field(default_factory=frozenset)
    created_at: float = field(default_factory=time.time)

    def alive(self) -> bool:
        return time.time() < self.exp

    def to_public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "room": self.room,
            "sub": self.sub,
            "scopes": sorted(self.scopes),
            "verticals": list(self.verticals),
            "expires_at": self.exp,
            "ticket": self.ticket,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "room": self.room,
            "sub": self.sub,
            "scopes": list(self.scopes),
            "verticals": list(self.verticals),
            "ticket": self.ticket,
            "exp": self.exp,
            "policy_allow": list(self.policy_allow),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "McpSession":
        return cls(
            session_id=str(data["session_id"]),
            agent_id=str(data.get("agent_id") or ""),
            room=str(data.get("room") or ""),
            sub=str(data.get("sub") or ""),
            scopes=frozenset(data.get("scopes") or ()),
            verticals=tuple(data.get("verticals") or ()),
            ticket=str(data["ticket"]),
            exp=float(data.get("exp") or 0),
            policy_allow=frozenset(data.get("policy_allow") or ()),
            created_at=float(data.get("created_at") or time.time()),
        )


class MemoryMcpSessionStore:
    """Process-local session store (dev / single worker)."""

    def __init__(self, *, max_sessions: int = 20_000, max_revoked: int = 50_000) -> None:
        self._by_ticket: dict[str, McpSession] = {}
        self._by_id: dict[str, McpSession] = {}
        self._lock = threading.RLock()
        self._revoked: set[str] = set()
        self.max_sessions = max_sessions
        self.max_revoked = max_revoked

    def _purge_expired(self) -> None:
        dead = [tok for tok, s in self._by_ticket.items() if not s.alive()]
        for tok in dead:
            sess = self._by_ticket.pop(tok, None)
            if sess is not None:
                self._by_id.pop(sess.session_id, None)

    def create(
        self,
        *,
        agent_id: str,
        room: str,
        sub: str,
        scopes: Sequence[str],
        verticals: Sequence[str] = (),
        ttl_s: float = 900,
        policy_allow: Sequence[str] = (),
        ticket: Optional[str] = None,
    ) -> McpSession:
        sid = secrets.token_urlsafe(16)
        tok = ticket or secrets.token_urlsafe(24)
        sess = McpSession(
            session_id=sid,
            agent_id=agent_id,
            room=str(room),
            sub=str(sub or agent_id),
            scopes=frozenset(str(s) for s in scopes),
            verticals=tuple(verticals),
            ticket=tok,
            exp=time.time() + max(60.0, float(ttl_s)),
            policy_allow=frozenset(str(a) for a in policy_allow),
        )
        with self._lock:
            self._purge_expired()
            if len(self._by_ticket) >= self.max_sessions:
                raise RuntimeError(
                    "MCP session store full — reject new sessions (fail closed)"
                )
            self._by_ticket[tok] = sess
            self._by_id[sid] = sess
        return sess

    def get_by_ticket(self, ticket: str) -> Optional[McpSession]:
        with self._lock:
            if ticket in self._revoked:
                return None
            sess = self._by_ticket.get(ticket)
            if sess is None or not sess.alive():
                return None
            return sess

    def get(self, session_id: str) -> Optional[McpSession]:
        with self._lock:
            sess = self._by_id.get(session_id)
            if sess is None or not sess.alive() or sess.ticket in self._revoked:
                return None
            return sess

    def revoke(self, ticket_or_id: str) -> bool:
        with self._lock:
            sess = self._by_ticket.get(ticket_or_id) or self._by_id.get(ticket_or_id)
            if sess is None:
                self._revoked.add(ticket_or_id)
                return False
            self._revoked.add(sess.ticket)
            self._revoked.add(sess.session_id)
            self._by_ticket.pop(sess.ticket, None)
            self._by_id.pop(sess.session_id, None)
            return True


McpSessionStore = MemoryMcpSessionStore


class RedisMcpSessionStore:
    """Multi-worker MCP sessions via Redis keys + revocation set."""

    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:mcp:sess:"):
        from ux_channel.redis_extra import _client

        self.r = _client(redis_url)
        self.prefix = prefix
        self.revoked_key = f"{prefix}revoked"

    def _tkey(self, ticket: str) -> str:
        return f"{self.prefix}t:{ticket}"

    def _ikey(self, sid: str) -> str:
        return f"{self.prefix}i:{sid}"

    def create(
        self,
        *,
        agent_id: str,
        room: str,
        sub: str,
        scopes: Sequence[str],
        verticals: Sequence[str] = (),
        ttl_s: float = 900,
        policy_allow: Sequence[str] = (),
        ticket: Optional[str] = None,
    ) -> McpSession:
        sid = secrets.token_urlsafe(16)
        tok = ticket or secrets.token_urlsafe(24)
        ttl = int(max(60.0, float(ttl_s)))
        sess = McpSession(
            session_id=sid,
            agent_id=agent_id,
            room=str(room),
            sub=str(sub or agent_id),
            scopes=frozenset(str(s) for s in scopes),
            verticals=tuple(verticals),
            ticket=tok,
            exp=time.time() + ttl,
            policy_allow=frozenset(str(a) for a in policy_allow),
        )
        raw = _serde.dumps(sess.to_dict(), default=str)
        pipe = self.r.pipeline()
        pipe.set(self._tkey(tok), raw, ex=ttl)
        pipe.set(self._ikey(sid), tok, ex=ttl)
        pipe.execute()
        return sess

    def _load_ticket(self, ticket: str) -> Optional[McpSession]:
        if self.r.sismember(self.revoked_key, ticket):
            return None
        raw = self.r.get(self._tkey(ticket))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        sess = McpSession.from_dict(_serde.loads(raw))
        if not sess.alive():
            return None
        return sess

    def get_by_ticket(self, ticket: str) -> Optional[McpSession]:
        return self._load_ticket(ticket)

    def get(self, session_id: str) -> Optional[McpSession]:
        if self.r.sismember(self.revoked_key, session_id):
            return None
        tok = self.r.get(self._ikey(session_id))
        if not tok:
            return None
        if isinstance(tok, bytes):
            tok = tok.decode("utf-8")
        return self._load_ticket(tok)

    def revoke(self, ticket_or_id: str) -> bool:
        sess = self.get_by_ticket(ticket_or_id) or self.get(ticket_or_id)
        if sess is None:
            self.r.sadd(self.revoked_key, ticket_or_id)
            self.r.expire(self.revoked_key, 86400)
            return False
        pipe = self.r.pipeline()
        pipe.sadd(self.revoked_key, sess.ticket, sess.session_id)
        pipe.expire(self.revoked_key, 86400)
        pipe.delete(self._tkey(sess.ticket), self._ikey(sess.session_id))
        pipe.execute()
        return True


_store: Any = None
_store_lock = threading.Lock()


def build_session_store(redis_url: Optional[str] = None) -> Any:
    """Construct Redis store when url given, else memory (fallback on Redis errors)."""
    if redis_url:
        try:
            return RedisMcpSessionStore(redis_url)
        except Exception:
            return MemoryMcpSessionStore()
    return MemoryMcpSessionStore()


def get_session_store(*, redis_url: Optional[str] = None) -> Any:
    """
    Process-wide store. Pass redis_url on first call to select Redis backend;
    later calls ignore redis_url unless store was reset via set_session_store(None).
    """
    global _store
    with _store_lock:
        if _store is None:
            _store = build_session_store(redis_url)
        return _store


def set_session_store(store: Any) -> None:
    """Replace process-wide store (tests / boot). Pass None to rebuild on next get."""
    global _store
    with _store_lock:
        _store = store
