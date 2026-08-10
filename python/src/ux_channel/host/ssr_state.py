"""
``ssr_state`` — session values (server draft) that drive region re-paint.

Flat umbrella (preferred)::

    from ux_channel import state
    st = state(ch)
    n = st.session("n", 0)

Direct::

    ui = ssr_state(ch)
    n = ui.session("n", 0)
    row = ui.namespace("line", id)
    qty = row.session("qty", 0)
"""


from __future__ import annotations

import contextvars
import functools
import inspect
import re
from contextlib import contextmanager
from dataclasses import dataclass
import threading
from typing import Any, Callable, Iterator, Optional, Sequence, Union

from ux_channel.protocol.types import Result

__all__ = [
    "ssr_state",
    "attach_ssr_state",
    "SsrState",
    "SessionVar",
    "StateHandle",
    "Namespace",
]

Mutator = Callable[[Any], Any]
_KEY_PART = re.compile(r"^[A-Za-z0-9_.:@+-]+$")

_current_region: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "ux_channel_ssr_state_region", default=None
)
_dirty_keys: contextvars.ContextVar[Optional[set[str]]] = contextvars.ContextVar(
    "ux_channel_ssr_state_dirty", default=None
)
_defer_done: contextvars.ContextVar[int] = contextvars.ContextVar(
    "ux_channel_ssr_state_defer", default=0
)


def ssr_state(channel: Any, *, prefix: str = "ui.", auto_patch: bool = True) -> "SsrState":
    existing = getattr(channel, "ssr_state", None)
    if isinstance(existing, SsrState):
        return existing
    return attach_ssr_state(channel, prefix=prefix, auto_patch=auto_patch)


def attach_ssr_state(
    channel: Any, *, prefix: str = "ui.", auto_patch: bool = True
) -> "SsrState":
    state = SsrState(channel, prefix=prefix)
    channel.ssr_state = state
    if auto_patch:
        state._patch_region_html()
    return state


def stable_part(value: Any, *, what: str = "key") -> str:
    if value is None:
        raise ValueError(f"ssr_state {what} cannot be None")
    if isinstance(value, bool):
        s = "true" if value else "false"
    elif isinstance(value, (int, float)):
        s = str(value)
    else:
        s = str(value).strip()
    if not s:
        raise ValueError(f"ssr_state {what} cannot be empty")
    if ".." in s or "/" in s or "\\" in s or "\n" in s or "\0" in s:
        raise ValueError(f"ssr_state {what} contains forbidden characters: {s!r}")
    if not _KEY_PART.match(s):
        safe = re.sub(r"[^A-Za-z0-9_.:@+-]+", "_", s)
        if not safe or safe == "_":
            safe = f"id_{abs(hash(s)) % (10**12)}"
        s = safe
    return s


def join_key(*parts: Any) -> str:
    return ":".join(stable_part(p, what="key part") for p in parts if p is not None and p != "")


def _resolve_refresh(refresh: Any) -> list[str]:
    if refresh is None or refresh is False:
        return []
    from ux_channel.host.flow import resolve_uids

    if isinstance(refresh, (list, tuple)):
        return list(resolve_uids(list(refresh)))
    return list(resolve_uids([refresh]))


@dataclass
class SessionVar:
    """
    One UI cell.

    Read: ``n()`` / ``n.value`` · ``n.peek()``
    Write: ``n.set`` · ``n.add`` · ``n.toggle`` · ``n.merge`` · ``n.map``
    Wire: ``n.feeds`` · ``n.done``
    """

    _ui: "SsrState"
    key: str
    default: Any = None

    def _full_key(self) -> str:
        return self._ui._key(self.key)

    def peek(self, default: Any = None) -> Any:
        d = self.default if default is None else default
        return self._ui.ch.draft.get(self._full_key(), d)

    def get(self, default: Any = None) -> Any:
        self._ui._track(self.key)
        return self.peek(default)

    def __call__(self, default: Any = None) -> Any:
        return self.get(default)

    @property
    def value(self) -> Any:
        return self.get()

    def set(self, value: Union[Any, Mutator]) -> Any:
        """Set value, or ``set(fn)`` as mutator. Prefer ``map(fn)`` for transforms."""
        full = self._full_key()
        if not (callable(value) and not isinstance(value, type)):
            try:
                from ux_channel.foundations.quantity import refuse_session_quantity
                refuse_session_quantity(self.key, value)
            except Exception as exc:
                from ux_channel.foundations.quantity import QuantityError
                if isinstance(exc, QuantityError):
                    raise
                pass
        if callable(value) and not isinstance(value, type):
            new = self._ui.ch.draft.change(
                full, value, default=self.default  # type: ignore[arg-type]
            )
        else:
            self._ui.ch.draft.set(full, value)
            new = value
        self._ui._mark_dirty(self.key)
        return new

    def map(self, mutator: Mutator) -> Any:
        if not callable(mutator) or isinstance(mutator, type):
            raise TypeError("session.map(fn) requires a callable mutator")
        return self.set(mutator)

    def update(self, mutator: Mutator) -> Any:
        return self.map(mutator)

    def add(self, delta: float = 1) -> Any:
        def _mut(cur: Any) -> Any:
            base = self.default if cur is None else cur
            if base is None:
                base = 0
            try:
                return base + delta
            except TypeError as e:
                raise TypeError(
                    f"session.add on {self.key!r}: value {base!r} is not numeric"
                ) from e

        return self.map(_mut)

    def toggle(self) -> bool:
        return bool(self.map(lambda v: not bool(v if v is not None else self.default)))

    def reset(self) -> None:
        """Drop stored value; next read returns ``default``."""
        self._ui.ch.draft.clear(self._full_key())
        self._ui._mark_dirty(self.key)


    def merge(self, **fields: Any) -> Any:
        def _mut(cur: Any) -> Any:
            if cur is None:
                base: dict[str, Any] = {}
            elif isinstance(cur, dict):
                base = dict(cur)
            else:
                raise TypeError(
                    f"session.merge on {self.key!r}: expected dict, got {type(cur).__name__}"
                )
            base.update(fields)
            return base

        return self.map(_mut)

    def feeds(self, *regions: Any) -> "SessionVar":
        self._ui._link(self.key, *regions)
        return self

    def done(self, *, notice: Optional[str] = None, go: Optional[str] = None) -> Result:
        return self._ui.done(self.key, notice=notice, go=go)

    def __repr__(self) -> str:
        try:
            v = self.peek()
        except Exception:
            v = "<?>"
        return f"SessionVar({self.key!r}, value={v!r})"


@dataclass
class StateHandle:
    """React unpack: ``n, set_n = ui.use("n", 0)``. Prefer ``ui.session``."""

    cell: SessionVar

    def __iter__(self):
        yield self.get
        yield self.set

    def get(self, default: Any = None) -> Any:
        return self.cell.get(default)

    def set(self, value: Union[Any, Mutator]) -> Any:
        return self.cell.set(value)

    def __call__(self, default: Any = None) -> Any:
        return self.cell.get(default)

    @property
    def value(self) -> Any:
        return self.cell.value

    def add(self, delta: float = 1) -> Any:
        return self.cell.add(delta)

    def toggle(self) -> bool:
        return self.cell.toggle()

    def map(self, mutator: Mutator) -> Any:
        return self.cell.map(mutator)

    def merge(self, **fields: Any) -> Any:
        return self.cell.merge(**fields)

    def reset(self) -> None:
        self.cell.reset()

    def done(self, **kw: Any) -> Result:
        return self.cell.done(**kw)

    def feeds(self, *regions: Any) -> "StateHandle":
        self.cell.feeds(*regions)
        return self


class Namespace:
    """
    Isolated key prefix for many cells (lists, per-user chrome, wizards).

    ::

        row = ui.namespace("line", line_id)
        qty = row.session("qty", 0)       # feeds row.uid by default
        @row.region
        def view(ctx):
            return str(qty())
    """

    def __init__(self, ui: "SsrState", *parts: Any) -> None:
        if not parts:
            raise ValueError(
                "namespace needs parts, e.g. ui.namespace('line', line_id)"
            )
        self._ui = ui
        self.parts = tuple(stable_part(p) for p in parts)
        self.path = join_key(*self.parts)

# identity

    @property
    def uid(self) -> str:
        """Conventional region uid for this namespace (= path)."""
        return self.path

    def key(self, name: str) -> str:
        """Full session key: ``{path}:{name}``."""
        return join_key(self.path, name)

    def namespace(self, *parts: Any) -> "Namespace":
        """Nest further: ``row.namespace('meta').session('note', '')``."""
        return Namespace(self._ui, *self.parts, *parts)

# cells

    def session(
        self,
        name: str,
        default: Any = None,
        *,
        refresh: Any = None,
        feed: bool = True,
    ) -> SessionVar:
        """
        Session value under this namespace.

        * ``feed=True`` (default) → morph ``self.uid`` when this session value changes.
          Root ``ui.session`` never auto-feeds; only namespaces do (list-safe).
        * ``feed=False`` → manual ``refresh=`` / ``feeds`` only.
        """
        if refresh is None and feed:
            refresh = self.uid
        return self._ui.session(self.key(name), default, refresh=refresh)

    def __call__(
        self,
        name: str,
        default: Any = None,
        *,
        refresh: Any = None,
        feed: bool = True,
    ) -> SessionVar:
        """Same as ``session`` — ``row("qty", 0)``."""
        return self.session(name, default, refresh=refresh, feed=feed)

    def use(
        self,
        name: str,
        default: Any = None,
        *,
        refresh: Any = None,
        feed: bool = True,
    ) -> StateHandle:
        if refresh is None and feed:
            refresh = self.uid
        return self._ui.use(self.key(name), default, refresh=refresh)

# region

    def region(self, fn: Optional[Callable[..., Any]] = None, **kw: Any) -> Any:
        """
        Register a region whose uid is this namespace path.

        ::

            @row.region
            def view(ctx):
                return f"{qty()}"
        """
        if callable(fn):
            return self._ui.region(self.uid, **kw)(fn)

        def deco(f: Callable[..., Any]) -> Callable[..., Any]:
            return self._ui.region(self.uid, **kw)(f)

        return deco

    def paint(self, **kwargs: Any) -> str:
        """SSR paint this namespace's region."""
        return self._ui.paint(self.uid, **kwargs)

    def bind(self, action: Any, **trust: Any) -> dict[str, str]:
        """Control attrs (same as ``ui.bind``)."""
        return self._ui.bind(action, **trust)

    def __repr__(self) -> str:
        return f"Namespace({self.path!r})"


class SsrState:
    """
    Server UI state bag (one per Channel).

    Application:  ``local`` · ``@region`` · ``@action`` · ``bind``
    Many:   ``namespace``
    Power:  ``changes`` · ``map`` · ``refresh=`` · ``feeds``
    """

    def __init__(self, channel: Any, *, prefix: str = "ui.") -> None:
        self.ch = channel
        self.prefix = prefix if prefix.endswith(".") or prefix == "" else prefix + "."
        self._subs: dict[str, set[str]] = {}
        self._vars: dict[str, SessionVar] = {}
        self._patched = False
        self._lock = threading.RLock()

    def _key(self, key: str) -> str:
        k = str(key).strip()
        if not k:
            raise ValueError("session key cannot be empty")
        if ":" not in k:
            k = stable_part(k, what="session key")
        if self.prefix and not k.startswith(self.prefix):
            return f"{self.prefix}{k}"
        return k

    def _logical_key(self, key: str) -> str:
        return str(key).strip()

    def _track(self, key: str) -> None:
        rid = _current_region.get()
        if not rid:
            return
        with self._lock:
            self._subs.setdefault(self._logical_key(key), set()).add(str(rid))

    def _link(self, key: str, *regions: Any) -> None:
        logical = self._logical_key(key)
        with self._lock:
            for uid in _resolve_refresh(list(regions) if regions else None):
                self._subs.setdefault(logical, set()).add(str(uid))

    def _mark_dirty(self, key: str) -> None:
        bag = _dirty_keys.get()
        if bag is None:
            bag = set()
            _dirty_keys.set(bag)
        bag.add(self._logical_key(key))

    def take_dirty(self) -> set[str]:
        bag = _dirty_keys.get() or set()
        _dirty_keys.set(set())
        return set(bag)

    def dependents(self, *keys: str) -> list[str]:
        with self._lock:
            out: set[str] = set()
            for k in keys:
                out |= set(self._subs.get(self._logical_key(k), set()))
            return sorted(out)

    @contextmanager
    def rendering(self, region_uid: str) -> Iterator[None]:
        tok = _current_region.set(str(region_uid))
        try:
            yield
        finally:
            _current_region.reset(tok)

    def _patch_region_html(self) -> None:
        if self._patched:
            return
        book = getattr(self.ch, "regions", None)
        if book is None:
            return
        orig = book.__class__.html
        ui = self

        def html(uid: Any, *args: Any, **kwargs: Any) -> Any:
            from ux_channel.host.regions import _id_str

            with ui.rendering(_id_str(uid)):
                return orig(book, uid, *args, **kwargs)

        book.html = html  # type: ignore[method-assign]
        self.ch.html = html  # type: ignore[method-assign]
        self._patched = True

# namespace (only multi-cell API)

    def namespace(self, *parts: Any) -> Namespace:
        """
        Isolate keys so N widgets never share one cell.

        ::

            row = ui.namespace("line", line_id)
            qty = row.session("qty", 0)
            @row.region
            def view(ctx):
                return str(qty())
        """
        return Namespace(self, *parts)

# cells

    def session(
        self,
        key: str,
        default: Any = None,
        *,
        refresh: Any = None,
    ) -> SessionVar:
        """
        Global cell (page-level). Same key → same cell.

        For N independent values: ``ui.namespace(...).session(...)``.
        """
        raw = str(key).strip()
        if not raw:
            raise ValueError("session key cannot be empty")
        k = self._logical_key(raw if ":" in raw else join_key(raw))
        with self._lock:
            if k in self._vars:
                a = self._vars[k]
                if default is not None and a.default is None:
                    a.default = default
            else:
                a = SessionVar(self, k, default)
                self._vars[k] = a
        if refresh is not None:
            if isinstance(refresh, (list, tuple)):
                a.feeds(*refresh)
            else:
                a.feeds(refresh)
        return a

    def use(
        self,
        key: str,
        default: Any = None,
        *,
        refresh: Any = None,
    ) -> StateHandle:
        return StateHandle(cell=self.session(key, default, refresh=refresh))

    def get(self, key: str, default: Any = None) -> Any:
        return self.session(key, default).get(default)

    def set(self, key: str, value: Union[Any, Mutator]) -> Any:
        return self.session(key).set(value)

    def merge(self, key: str, **fields: Any) -> Any:
        return self.session(key, {}).merge(**fields)

    def snapshot(self, *keys: str) -> dict[str, Any]:
        if not keys:
            keys = tuple(self._subs.keys()) or tuple(self._vars.keys())
        return {str(k): self.session(k).peek() for k in keys}

# batch

    @contextmanager
    def changes(self, *, auto_done: bool = True) -> Iterator["SsrState"]:
        """Batch writes; one ``done()`` on exit when ``auto_done``."""
        depth = _defer_done.get()
        _defer_done.set(depth + 1)
        if depth == 0:
            _dirty_keys.set(set())
        try:
            yield self
        finally:
            _defer_done.set(depth)
            if depth == 0 and auto_done:
                self.done()

# regions / paint

    def region(self, uid: Any = None, **region_kwargs: Any) -> Any:
        if callable(uid) and not isinstance(uid, str):
            fn = uid
            return self.ch.region(fn.__name__, **region_kwargs)(fn)

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            name = uid if isinstance(uid, str) else fn.__name__
            return self.ch.region(name, **region_kwargs)(fn)

        return decorator

    def paint(self, uid: Any, **kwargs: Any) -> str:
        return self.ch.html(uid, **kwargs)

# commit

    def regions_for_dirty(self, *extra_keys: str) -> list[str]:
        dirty = self.take_dirty()
        dirty |= {self._logical_key(k) for k in extra_keys}
        if not dirty:
            return []
        return self.dependents(*sorted(dirty))

    def done(
        self,
        *keys: str,
        notice: Optional[str] = None,
        go: Optional[str] = None,
        refresh: Optional[Sequence[Any]] = None,
        notice_level: str = "info",
    ) -> Result:
        if (
            _defer_done.get() > 0
            and not keys
            and refresh is None
            and notice is None
            and go is None
        ):
            return Result.success()
        uids = list(self.regions_for_dirty(*keys))
        if refresh is not None:
            uids = list(dict.fromkeys(uids + _resolve_refresh(list(refresh))))
        if not uids and not notice and not go:
            return self.ch.done(notice=notice, go=go, notice_level=notice_level)
        return self.ch.done(
            notice=notice,
            go=go,
            notice_level=notice_level,
            refresh=uids if uids else [],
        )

# actions

    def action(
        self,
        fn: Optional[Callable[..., Any]] = None,
        *,
        name: Optional[str] = None,
        refresh: Optional[Sequence[Any]] = None,
        **on_kwargs: Any,
    ) -> Any:
        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            action_name = name or f.__name__
            on_kw = {k: v for k, v in on_kwargs.items() if k != "refresh"}

            if inspect.iscoroutinefunction(f):

                @functools.wraps(f)
                async def wrapped(*args: Any, **kwargs: Any) -> Any:
                    _dirty_keys.set(set())
                    out = await f(*args, **kwargs)
                    return self._finish_action(out, refresh=refresh)

                return self.ch.on(action_name, **on_kw)(wrapped)

            @functools.wraps(f)
            def wrapped_sync(*args: Any, **kwargs: Any) -> Any:
                _dirty_keys.set(set())
                out = f(*args, **kwargs)
                return self._finish_action(out, refresh=refresh)

            return self.ch.on(action_name, **on_kw)(wrapped_sync)

        if fn is not None:
            return decorator(fn)
        return decorator

    def _finish_action(
        self, out: Any, *, refresh: Optional[Sequence[Any]]
    ) -> Any:
        if isinstance(out, Result):
            extra = self.regions_for_dirty()
            if not extra or not out.ok:
                return out
            more = self.ch.done(refresh=extra)
            return Result(
                ok=True,
                ops=list(out.ops or []) + list(more.ops or []),
                meta={**(out.meta or {}), **(more.meta or {})},
                v=getattr(out, "v", None) or "1",
            )
        if out is None:
            return self.done(refresh=refresh)
        if isinstance(out, str):
            return self.done(notice=out, refresh=refresh)
        return out

    def control(self, action: Any, **trust: Any) -> Any:
        return self.ch.control(action, **trust)

    def bind(self, action: Any, **trust: Any) -> dict[str, str]:
        return self.ch.control(action, **trust).as_ux_dom()

    def bind_dict(self, action: Any, **trust: Any) -> dict[str, str]:
        return self.ch.control(action, **trust).as_dict()

    def graph(self) -> dict[str, list[str]]:
        with self._lock:
            return {k: sorted(v) for k, v in self._subs.items()}

    def describe(self) -> dict[str, Any]:
        return {
            "prefix": self.prefix,
            "subscriptions": self.graph(),
            "snapshot": self.snapshot(),
            "public_api": [
                'ui = ssr_state(ch)',
                'n = ui.session("n", 0)',
                "@ui.region / @ui.action / n.add(1) / ui.bind",
            ],
            "many": [
                'row = ui.namespace("line", line_id)',
                'qty = row.session("qty", 0)   # feeds row.uid',
                "@row.region",
                "def view(ctx): return str(qty())",
            ],
            "power": [
                'n = ui.session("n", 0, refresh="badge")',
                "n.map(lambda x: x * 2)",
                "with ui.changes(): a.add(1); b.add(1)",
                'ui.namespace("wizard", user).namespace("step")',
            ],
        }

    def __repr__(self) -> str:
        return f"SsrState(prefix={self.prefix!r}, vars={list(self._vars.keys())[:12]})"
