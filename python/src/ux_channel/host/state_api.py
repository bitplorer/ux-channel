"""Channel state façade — ``state(ch)`` for session · client · db guards.

Application: ``from ux_channel import state``. Not a database; durable stores are yours.
"""


from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.host.state_planes import (
    ClientPlane,
    ClientSafetyError,
    Db,
    RISKY_SEGMENTS,
    path_is_risky,
)
from ux_channel.host.ssr_state import Namespace, SessionVar, SsrState, ssr_state
from ux_channel.protocol.types import Result

__all__ = [
    "state",
    "attach_state",
    "ChannelState",
    "SessionVar",
    "Namespace",
    "Client",
    "Db",
    "ClientSafetyError",
    "path_is_risky",
    "RISKY_SEGMENTS",
]

# Public name: Client (not ClientPlane)
Client = ClientPlane


class ChannelState:
    """
    ``st.session`` / ``st.client`` / ``st.db`` — that is the whole application map.

    ::

        st = state(ch)
        n = st.session("n", 0)
        @st.region
        def badge(ctx): ...
        @st.action
        def inc(): n.add(1)
    """

    def __init__(
        self,
        channel: Any,
        *,
        session_bag: SsrState,
        client: ClientPlane,
        db: Db,
    ) -> None:
        self.ch = channel
        self.channel = channel
        self._bag = session_bag
        self.client = client
        self.db = db

# session

    def session(
        self,
        key: str,
        default: Any = None,
        *,
        refresh: Any = None,
    ) -> SessionVar:
        """Session value (server draft). Same key → same value."""
        return self._bag.session(key, default, refresh=refresh)

    def namespace(self, *parts: Any) -> Namespace:
        """Many independent session values (e.g. per row)."""
        return self._bag.namespace(*parts)

# regions / actions (same object — no second import)

    def region(self, uid: Any = None, **kw: Any) -> Any:
        return self._bag.region(uid, **kw)

    def action(self, fn: Any = None, **kw: Any) -> Any:
        return self._bag.action(fn, **kw)

    def bind(self, action: Any, **trust: Any) -> dict[str, str]:
        """Control attrs for any host: ``button("+", **st.bind(inc))``."""
        return self._bag.bind(action, **trust)

    def paint(self, uid: Any, **kwargs: Any) -> str:
        return self._bag.paint(uid, **kwargs)

    def done(self, *keys: str, **kw: Any) -> Result:
        """Morph dirty session regions; merges pending client ops if any."""
        client_ops = self.client.take()
        base = self._bag.done(*keys, **kw)
        if not client_ops:
            return base
        return Result(
            ok=True,
            ops=list(base.ops or []) + client_ops,
            meta=dict(base.meta or {}),
            v=getattr(base, "v", None) or "1",
        )

    def changes(self, **kw: Any):
        return self._bag.changes(**kw)

# discovery

    def help(self) -> str:
        return (
            "st = state(ch)\n"
            "  n = st.session('n', 0)          # server session value\n"
            "  row = st.namespace('line', id); q = row.session('qty', 0)\n"
            "  @st.region / @st.action / st.bind(fn)\n"
            "  st.client('ui.theme', 'dark') # browser (allow= for persist)\n"
            "  st.db.guard(args)             # block client money/secrets\n"
            "  money → your DB, not session/client\n"
        )

    def describe(self) -> dict[str, Any]:
        return {
            "api": "state(ch) → session | client | db",
            "public_api": self.help().strip().splitlines(),
            "kinds": {
                "session": "server draft — st.session / st.namespace",
                "client": "browser — st.client(path, value)",
                "db": "your database — st.db.guard / require",
            },
            "client": self.client.describe(),
            "db": self.db.describe(),
            "session_graph": self._bag.graph(),
        }

    def __repr__(self) -> str:
        return f"ChannelState({self._bag!r})"


def state(
    channel: Any,
    *,
    allow: Sequence[str] = (),
    persist_allowlist: Sequence[str] = (),
    strict: bool = True,
    client_strict: Optional[bool] = None,
) -> ChannelState:
    """
    Attach / return channel state (``ch.st``).

    ::

        st = state(ch, allow=["ui.theme"])
        n = st.session("n", 0)

    ``allow`` — client paths permitted for ``persist=True`` (localStorage).
    """
    allow_list = tuple(allow) or tuple(persist_allowlist)
    strict_flag = strict if client_strict is None else client_strict
    existing = getattr(channel, "st", None) or getattr(channel, "state_ui", None)
    if isinstance(existing, ChannelState):
        if allow_list:
            existing.client.configure(persist_allowlist=allow_list)
        existing.client.configure(strict=strict_flag)
        return existing
    return attach_state(
        channel,
        allow=allow_list,
        strict=strict_flag,
    )


def attach_state(
    channel: Any,
    *,
    allow: Sequence[str] = (),
    persist_allowlist: Sequence[str] = (),
    strict: bool = True,
    client_strict: Optional[bool] = None,
) -> ChannelState:
    from ux_channel.host.state_planes import attach_planes

    allow_list = tuple(allow) or tuple(persist_allowlist)
    strict_flag = strict if client_strict is None else client_strict
    bag = attach_planes(
        channel,
        persist_allowlist=allow_list,
        client_strict=strict_flag,
    )
    st = ChannelState(
        channel,
        session_bag=bag.session,
        client=bag.client,
        db=bag.db,
    )
    channel.st = st
    channel.state_ui = st  # stable alias used internally
    return st
