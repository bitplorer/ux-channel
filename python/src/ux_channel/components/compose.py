"""
Composition — Block + Composite on top of ChannelComponent (still 1 MRO step).

MRO remains shallow::

    object → ChannelComponent → Composite|Block → AppShell|…

Slots compose **content**, not base classes — that is the decades-stable choice.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from ux_channel.components.base import ChannelComponent
from ux_channel.components.primitive import as_host, region_attrs, region_root
from ux_channel.components.slots import (
    Slot,
    SlotContext,
    SlotList,
    Slots,
    choose_slot,
    map_slot,
    nest,
    render_fragment,
)
from ux_channel.protocol.types import Result

Fragment = Any


def fragment(value: Fragment, **state: Any) -> str:
    return render_fragment(value, **state)


def join_fragments(*parts: Fragment, sep: str = "", **state: Any) -> str:
    return nest(*parts, sep=sep, **state)


class Block(ChannelComponent):
    """Morph root around foreign HTML (ux-dom / Jinja / str)."""

    kind = "Block"

    def __init__(
        self,
        host: Any,
        *,
        uid: str | None = None,
        name: str = "Block",
        body: Fragment = "",
        body_factory: Callable[..., Fragment] | None = None,
        tag: str = "div",
        class_name: str = "ux-block",
        actions: Sequence[str] | None = None,
    ):
        super().__init__(host, uid=uid, name=name)
        self._body = body
        self.body_factory = body_factory
        self.tag = tag
        self.class_name = class_name
        self.actions = list(actions or ())

    def render(self, **state: Any) -> str:
        if self.body_factory is not None:
            body = fragment(self.body_factory(**state), **state)
        else:
            body = fragment(state.get("body", self._body), **state)
        return region_root(self.uid, body, tag=self.tag, class_=self.class_name)

    def swap(self, body: Fragment, *, notice: str | None = None, **state: Any) -> Result:
        self._body = body
        return self.refresh(body=body, notice=notice, **state)

    def _register(self) -> None:
        if not self.body_factory:
            return
        comp = self

        @self.host.action(self.action_name("refresh"))
        def refresh(**kwargs: Any) -> Result:
            return comp.refresh(**kwargs)


class Composite(ChannelComponent):
    """
    Named slots + ``layout`` — composition without deeper inheritance.

    Class attrs
    -----------
    slot_names:
        Declared holes (order used in default layout).
    slot_defaults:
        Fallback fragments per name.
    slot_required:
        Names that must be filled.
    """

    kind = "Composite"
    slot_names: tuple[str, ...] = ()
    slot_defaults: Mapping[str, Fragment] = {}
    slot_required: tuple[str, ...] = ()

    def __init__(
        self,
        host: Any,
        *,
        uid: str | None = None,
        name: str | None = None,
        slots: Mapping[str, Fragment] | None = None,
        class_name: str = "ux-composite",
        **kwargs: Any,
    ):
        super().__init__(host, uid=uid, name=name, **kwargs)
        self.class_name = class_name
        self._slot_bag = self._build_slots(slots or {})
        self._slot_bag.install_nested()

    def _build_slots(self, slots: Mapping[str, Fragment]) -> "Slots":
        bag = Slots()
        names = set(self.slot_names) | set(slots) | set(self.slot_defaults)
        for n in names:
            bag.set(
                n,
                slots.get(n, ""),
                default=self.slot_defaults.get(n, ""),
                required=n in self.slot_required,
            )
        return bag

    # --- public slot API (no private bag leakage) -------------------------

    @property
    def slots(self) -> Slots:
        """Stable access to the slot bag."""
        return self._slot_bag


    def fill(self, **slots: Fragment) -> "Composite":
        self._slot_bag.fill(**slots)
        return self

    def slot(self, name: str) -> Slot:
        return self._slot_bag.get(name)

    def slot_html(self, name: str, **state: Any) -> str:
        return self._slot_bag.render(name, **state)

    def slot_scoped(self, name: str, props: Mapping[str, Any], **state: Any) -> str:
        return self._slot_bag.get(name).html_scoped(props, **state)

    def slots_html(self, **state: Any) -> dict[str, str]:
        return self._slot_bag.render_all(**state)

    def layout(self, slots: Mapping[str, str], **state: Any) -> str:
        order = list(self.slot_names) + [n for n in slots if n not in self.slot_names]
        return "".join(slots.get(n, "") for n in order)

    def render(self, **state: Any) -> str:
        rendered = self.slots_html(**state)
        for k, v in state.items():
            if k.startswith("slot_"):
                rendered[k[5:]] = fragment(v, **state)
        inner = self.layout(rendered, **state)
        return region_root(self.uid, inner, class_=self.class_name)

    def _register(self) -> None:
        return None


def stamp_attrs(html: str, *, action: str | None = None, **kwargs: Any) -> str:
    if not action:
        return html
    attrs = region_attrs(action, **kwargs)
    if html.lstrip().startswith("<"):
        i = html.find(">")
        if i != -1 and not html.startswith("</"):
            if html[i - 1] == "/":
                return html[: i - 1] + " " + attrs + " />" + html[i + 1 :]
            return html[:i] + " " + attrs + html[i:]
    return f"<span {attrs}>{html}</span>"


def plug(
    host: Any,
    uid: str,
    body: Fragment,
    *,
    name: str = "Plug",
) -> Block:
    return Block(as_host(host), uid=uid, name=name, body=body).install()  # type: ignore[return-value]
