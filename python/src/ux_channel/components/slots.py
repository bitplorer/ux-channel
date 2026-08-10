"""
Slot composition patterns for Channel Components.

Maps UI-framework slot ideas onto server-driven HTML without a client VDOM.

Patterns
--------
| Pattern | Framework analogue | Channel API |
|---------|-------------------|-------------|
| Named slot | Vue ``#header`` / WC ``<slot name>`` | ``Slot("header", …)`` |
| Default slot | Vue default / WC unnamed | ``Slot.DEFAULT`` / ``"default"`` |
| Fallback content | slot fallback children | ``default=`` |
| Scoped slot | Vue ``v-slot="{ row }"`` | ``content=lambda ctx: …`` |
| Conditional | ``v-if`` on slot | ``when=`` predicate |
| List / repeat | ``v-for`` + slot | ``SlotList`` / ``map_slot`` |
| Nested compose | components in slots | ``ChannelComponent`` as content |
| Multi-fill | multiple providers | ``fill()`` / ``Slots`` bag |

All content is reduced to HTML via ``fragment()`` / ``to_html()`` so ux-dom,
Jinja Markup, strings, and callables plug in equally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Union

from ux_channel.components.base import ChannelComponent
from ux_channel.components.primitive import to_html
from ux_channel.render.html_safe import esc

# Avoid circular import of fragment from compose — define render pipeline here
# and let compose.fragment re-export / call into slots.render_fragment.

Fragment = Any
WhenPred = Callable[[Mapping[str, Any]], bool]
ScopeFn = Callable[..., Any]  # scoped slot: receives SlotContext


@dataclass(frozen=True)
class SlotContext:
    """
    Props bag passed into **scoped** slots (Vue-style).

    ::

        Slot("row", lambda ctx: f\"<td>{ctx['name']}</td>\")
        # or
        Slot("row", lambda ctx: ctx.props["name"])
    """

    name: str
    props: Mapping[str, Any] = field(default_factory=dict)
    state: Mapping[str, Any] = field(default_factory=dict)
    index: Optional[int] = None

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.props:
            return self.props[key]
        return self.state.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key in self.props:
            return self.props[key]
        return self.state[key]

    def __contains__(self, key: object) -> bool:
        return key in self.props or key in self.state


def render_fragment(value: Fragment, *, ctx: SlotContext | None = None, **state: Any) -> str:
    """
    Core reducer: Fragment → HTML string.

    Resolution order:
      1. None / empty → \"\"
      2. ChannelComponent → render(**state)
      3. Scoped callable → value(ctx) or value(**props)
      4. Plain callable → value(**state)
      5. to_html (str / __html__ / __render__)
    """
    if value is None or value is False:
        return ""
    if isinstance(value, ChannelComponent):
        try:
            return value.render(**state) if state else value.render()
        except TypeError:
            return value.render()
    if callable(value) and not isinstance(value, type):
        if ctx is not None:
            try:
                return to_html(value(ctx))
            except TypeError:
                try:
                    return to_html(value(**dict(ctx.props)))
                except TypeError:
                    pass
        try:
            return to_html(value(**state) if state else value())
        except TypeError:
            try:
                return to_html(value())
            except TypeError:
                return to_html(value)
    return to_html(value)


@dataclass
class Slot:
    """
    One named composition hole.

    Parameters
    ----------
    name:
        Slot name (``\"default\"`` for the default slot).
    content:
        Static fragment, ChannelComponent, or scoped callable.
    default:
        Fallback when content is empty (same types as content).
    fallback:
        Alias of ``default``.
    required:
        Raise if empty after fallbacks.
    when:
        Optional predicate ``(state) -> bool``; if False, render \"\".
    scope:
        Extra props always merged into SlotContext for scoped content.
    """

    DEFAULT = "default"

    name: str = DEFAULT
    content: Fragment = ""
    default: Fragment = ""
    required: bool = False
    when: Optional[WhenPred] = None
    scope: Mapping[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        c = self.content
        return c is None or c is False or c == ""

    def resolve_content(self) -> Fragment:
        if not self.is_empty():
            return self.content
        if self.default not in ("", None, False):
            return self.default
        return ""

    def html(
        self,
        **state: Any,
    ) -> str:
        if self.when is not None and not self.when(state):
            return ""
        body = self.resolve_content()
        if body in ("", None, False):
            if self.required:
                raise ValueError(f"slot {self.name!r} is required and empty")
            return ""
        ctx = SlotContext(name=self.name, props=dict(self.scope), state=state)
        # Allow state keys as scope props for convenience
        return render_fragment(body, ctx=ctx, **state)

    def html_scoped(self, props: Mapping[str, Any], **state: Any) -> str:
        """Render with explicit scoped props (list rows, table cells, …)."""
        if self.when is not None and not self.when(state):
            return ""
        body = self.resolve_content()
        if body in ("", None, False):
            if self.required:
                raise ValueError(f"slot {self.name!r} is required and empty")
            return ""
        merged = {**dict(self.scope), **dict(props)}
        ctx = SlotContext(name=self.name, props=merged, state=state)
        return render_fragment(body, ctx=ctx, **state)


@dataclass
class SlotList:
    """
    Repeat a scoped slot over items (``v-for`` + slot).

    ::

        rows = SlotList(
            \"row\",
            lambda ctx: f\"<li>{ctx['title']}</li>\",
            key=\"id\",
        )
        html = rows.render(items, state)
    """

    name: str
    content: Fragment
    default: Fragment = ""
    key: Optional[str] = None
    wrapper_tag: str = ""
    wrapper_class: str = ""
    empty: Fragment = ""

    def render(
        self,
        items: Sequence[Any],
        state: Optional[Mapping[str, Any]] = None,
        *,
        item_props: Callable[[Any, int], Mapping[str, Any]] | None = None,
    ) -> str:
        state = dict(state or {})
        if not items:
            return render_fragment(self.empty, **state)
        slot = Slot(self.name, content=self.content, default=self.default)
        parts: list[str] = []
        for i, item in enumerate(items):
            if item_props:
                props = dict(item_props(item, i))
            elif isinstance(item, Mapping):
                props = dict(item)
            else:
                props = {"item": item, "value": item}
            props.setdefault("index", i)
            if self.key and isinstance(item, Mapping) and self.key in item:
                props.setdefault("key", item[self.key])
            parts.append(slot.html_scoped(props, **state))
        inner = "".join(parts)
        if self.wrapper_tag:
            cls = f' class="{esc(self.wrapper_class)}"' if self.wrapper_class else ""
            return f"<{self.wrapper_tag}{cls}>{inner}</{self.wrapper_tag}>"
        return inner


class Slots:
    """
    Ordered bag of slots with dict-like and attribute access.

    ::

        s = (Slots()
             .set(\"header\", \"<h1>Hi</h1>\")
             .set(\"body\", my_ux_dom, default=\"<p>empty</p>\")
             .required(\"main\"))
        html = s.render_all(state)
    """

    def __init__(self, *slots: Slot, **named: Fragment):
        self._map: dict[str, Slot] = {}
        for s in slots:
            self._map[s.name] = s
        for k, v in named.items():
            self._map[k] = Slot(k, v)

    def set(
        self,
        name: str,
        content: Fragment = "",
        *,
        default: Fragment = "",
        required: bool = False,
        when: Optional[WhenPred] = None,
        scope: Optional[Mapping[str, Any]] = None,
    ) -> "Slots":
        self._map[name] = Slot(
            name,
            content=content,
            default=default,
            required=required,
            when=when,
            scope=dict(scope or {}),
        )
        return self

    def required(self, name: str) -> "Slots":
        s = self._map.get(name) or Slot(name)
        s.required = True
        self._map[name] = s
        return self

    def get(self, name: str) -> Slot:
        return self._map.get(name) or Slot(name)

    def __contains__(self, name: object) -> bool:
        return name in self._map

    def __getitem__(self, name: str) -> Slot:
        return self.get(name)

    def names(self) -> list[str]:
        return list(self._map.keys())

    def fill(self, **content: Fragment) -> "Slots":
        for k, v in content.items():
            prev = self._map.get(k)
            if prev:
                prev.content = v
            else:
                self._map[k] = Slot(k, v)
            if isinstance(v, ChannelComponent):
                v.install()
        return self

    def render(self, name: str, **state: Any) -> str:
        return self.get(name).html(**state)

    def render_all(self, **state: Any) -> dict[str, str]:
        return {n: s.html(**state) for n, s in self._map.items()}

    def install_nested(self) -> "Slots":
        for s in self._map.values():
            if isinstance(s.content, ChannelComponent):
                s.content.install()
            if isinstance(s.default, ChannelComponent):
                s.default.install()
        return self


def map_slot(
    items: Sequence[Any],
    content: Fragment,
    *,
    name: str = "item",
    empty: Fragment = "",
    **state: Any,
) -> str:
    """Functional helper: map items through a scoped slot body."""
    return SlotList(name, content, empty=empty).render(items, state)


def choose_slot(
    state: Mapping[str, Any],
    *candidates: tuple[WhenPred | bool, Fragment],
    default: Fragment = "",
) -> str:
    """
    Conditional composition (switch-style).

    ::

        choose_slot(state,
            (lambda s: s.get(\"error\"), \"<p class=err>…</p>\"),
            (lambda s: s.get(\"ok\"), success_ux_dom),
            default=\"<p>idle</p>\",
        )
    """
    for pred, body in candidates:
        ok = pred(state) if callable(pred) else bool(pred)
        if ok:
            return render_fragment(body, **dict(state))
    return render_fragment(default, **dict(state))


def nest(*parts: Fragment, sep: str = "", **state: Any) -> str:
    """Join fragments; skip empties. Nested composition helper."""
    out = []
    for p in parts:
        html = render_fragment(p, **state)
        if html:
            out.append(html)
    return sep.join(out)
