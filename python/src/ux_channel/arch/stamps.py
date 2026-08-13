"""Host-owned stamp table for invoke refs. Peer never owns authority."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Set


@dataclass
class Stamp:
    stamp_id: str
    kind: str
    methods: Set[str]
    session_id: str
    gen: int


class StampTable:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_session: Dict[str, Dict[str, Stamp]] = {}

    def grant(
        self,
        session_id: str,
        gen: int,
        kind: str,
        methods: Set[str],
        stamp_id: Optional[str] = None,
    ) -> Stamp:
        sid = stamp_id or secrets.token_urlsafe(10)
        st = Stamp(
            stamp_id=sid,
            kind=kind,
            methods=set(methods),
            session_id=session_id,
            gen=gen,
        )
        with self._lock:
            self._by_session.setdefault(session_id, {})[sid] = st
        return st

    def get(self, session_id: str, stamp_id: str, gen: int) -> Optional[Stamp]:
        with self._lock:
            st = self._by_session.get(session_id, {}).get(stamp_id)
            if st is None or st.gen != gen:
                return None
            return st

    def allows(self, session_id: str, stamp_id: str, gen: int, method: str) -> bool:
        st = self.get(session_id, stamp_id, gen)
        if st is None:
            return False
        return method in st.methods or "*" in st.methods

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._by_session.pop(session_id, None)

    def on_revoke(self, session_id: str) -> None:
        self.clear_session(session_id)
