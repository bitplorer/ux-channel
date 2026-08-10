"""
ChannelComponent — optional channel-side UI blocks.

First principles
----------------
ux-dom (or any HTML library) is the default for markup. This package is an
**optional kit** of server-driven blocks that speak regions + actions when
you want drop-in channel patterns without ux-dom.

Naming: **ChannelComponent** never ``Component`` — avoids clashing with ux-dom.

Not part of the core import surface::

    from ux_channel.components import Badge, Modal, Form

Prefer ux-dom + ``ch.control`` for product apps. See docs/COMPONENTS.md,
docs/COURSE.md.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ux_channel.components.primitive import (
    as_host,
    region_morph,
    region_root,
    to_html,
    uid_sel,
)
from ux_channel.protocol.types import Result


class ChannelComponent(ABC):
    """
    Drop-in channel region.

    Parameters
    ----------
    host:
        ``Channel``, ``ActionRegistry``, or ``RegistryHost``.
    uid:
        Stable ``data-channel-id`` (default ``{name}:root``).
    name:
        Action prefix (default ``kind``), e.g. ``Qty`` → ``Qty.inc``.
    """

    kind: ClassVar[str] = "ChannelComponent"
    #: Documented stable lifecycle — do not add required abstract methods lightly.
    __slots_api__: ClassVar[tuple[str, ...]] = (
        "install",
        "render",
        "refresh",
        "morph",
        "html",
        "wrap",
        "btn",
    )

    def __init__(
        self,
        host: Any,
        *,
        uid: str | None = None,
        name: str | None = None,
        **kwargs: Any,
    ):
        self.host = as_host(host)
        self.name = name or self.kind
        self.uid = uid or f"{self.name}:root"
        self._installed = False
        self._opts = kwargs

    # --- aliases (stable) -------------------------------------------------

    @property
    def ch(self) -> Any:
        """Alias of ``host`` — preferred in short widget code."""
        return self.host

    @property
    def registry(self) -> Any:
        return self.host.registry

    @property
    def target(self) -> str:
        """CSS selector for this region root."""
        return uid_sel(self.uid)

    def action_name(self, verb: str) -> str:
        """``{Name}.{verb}`` — stable action id for caps + client."""
        return f"{self.name.replace(' ', '')}.{verb}"

    # --- core API ---------------------------------------------------------

    @abstractmethod
    def render(self, **state: Any) -> str:
        """Pure: return HTML root including ``data-channel-id``. No registration."""

    def html(self, **state: Any) -> str:
        """Alias of ``render`` for embedding beside ux-dom trees."""
        return self.render(**state)

    def __call__(self, **state: Any) -> str:
        return self.render(**state)

    def install(self) -> "ChannelComponent":
        """Register actions once. Idempotent and re-entrant."""
        if not self._installed:
            self._register()
            self._installed = True
        return self

    def _register(self) -> None:
        """Override: bind ``@self.host.action(...)`` handlers only."""

    def refresh(
        self,
        *,
        notice: str | None = None,
        notice_level: str = "info",
        **state: Any,
    ) -> Result:
        """
        Morph this region to ``render(**state)``.

            return self.refresh(n=1, notice="Saved", notice_level="success")
        """
        html = to_html(self.render(**state))
        return self.host.patch(  # type: ignore[attr-defined]
            self.uid, html, notice=notice, notice_level=notice_level
        )


    def morph(self, html: str | Any, **kwargs: Any) -> Result:
        """Morph this uid to arbitrary HTML (ux-dom fragment, Markup, str)."""
        return region_morph(self.uid, to_html(html), **kwargs)

    # --- HTML helpers -----------------------------------------------------

    def wrap(self, inner: str | Any, *, tag: str = "div", **attrs: str) -> str:
        if "class_" in attrs:
            attrs = dict(attrs)
            attrs["class"] = attrs.pop("class_")
        return region_root(self.uid, to_html(inner), tag=tag, **attrs)

    def btn(
        self,
        label: str,
        verb: str,
        *,
        trust: dict | None = None,
        once: bool = False,
        class_name: str = "",
        **attrs: Any,
    ) -> str:
        from ux_channel.components.primitive import region_button

        return region_button(
            self.registry,
            label,
            self.action_name(verb),
            trust=trust or {},
            target=self.uid,
            once=once,
            class_name=class_name,
            **attrs,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{type(self).__name__}(uid={self.uid!r}, name={self.name!r}, "
            f"installed={self._installed})"
        )

    def describe(self) -> dict[str, Any]:
        """Introspection for DX / inspector (no secrets)."""
        return {
            "kind": self.kind,
            "name": self.name,
            "uid": self.uid,
            "target": self.target,
            "installed": self._installed,
            "class": type(self).__name__,
            "mro": [c.__name__ for c in type(self).__mro__ if c not in (object,)],
        }



class ChannelKit:
    """
    Install many regions in one call (no ux-dom naming clash).

    ::

        ChannelKit(host).add(counter, flash, cart).install_all()
    """

    def __init__(self, host: Any):
        self.host = as_host(host)
        self.items: list[ChannelComponent] = []

    def add(self, *comps: ChannelComponent) -> "ChannelKit":
        self.items.extend(comps)
        return self

    def install_all(self) -> "ChannelKit":
        for c in self.items:
            c.install()
        return self

    def __iter__(self):
        return iter(self.items)
