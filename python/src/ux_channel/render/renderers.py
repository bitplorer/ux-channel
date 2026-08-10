"""HtmlRenderer protocol — turn *any* library's values into HTML fragments.
Actions may return framework-native objects (ux-dom trees, Jinja templates,
Markup strings, custom components). The encoder only understands Result/ops/HTML.
Renderers are the **plug-and-play adapter** from \"library object\" → \"str HTML\".
- Zero hard dependency on ux-dom/Jinja (optional classes degrade gracefully).
-…"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class HtmlRenderer(Protocol):
    """
    Protocol for plug-and-play HTML producers.

    Return:
      - str HTML fragment if this renderer handles ``value``
      - None to defer to the next renderer in a ChainRenderer
    """

    def render(self, value: Any) -> str | None:
        ...


class StringRenderer:
    """
    Built-in: pass through ``str`` / ``bytes``.

    Always include last in a chain so plain HTML fragments from actions work
    without any framework.
    """

    def render(self, value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return None


class ChainRenderer:
    """
    Try each renderer in order; first non-None HTML wins.

    Designed for multi-library apps (ux-dom + Jinja + strings) without
    ActionRegistry branching on types.
    """

    def __init__(self, *renderers: HtmlRenderer):
        self._renderers = renderers

    def render(self, value: Any) -> str | None:
        for r in self._renderers:
            html = r.render(value)
            if html is not None:
                return html
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return f"ChainRenderer({', '.join(type(r).__name__ for r in self._renderers)})"


class UxDomRenderer:
    """
    Optional ux-dom / dominate-style objects with ``__render__()``.

    Plug-and-play: if the object has a callable ``__render__``, use it.
    No import of ux_dom required — duck typing only.

    Usage: return Component/dom_tag instances from actions; provide Intent.target
    or a root data-channel-id so encode can morph.
    """

    def render(self, value: Any) -> str | None:
        render = getattr(value, "__render__", None)
        if callable(render):
            out = render()
            return out if isinstance(out, str) else str(out)
        return None


class JinjaRenderer:
    """
    Optional Jinja2 adapter — bind an Environment at construction.

    Plug-and-play with Flask/FastAPI Jinja setups::

        env = jinja2.Environment(loader=...)
        reg = ActionRegistry(..., renderer=ChainRenderer(
            JinjaRenderer(env), StringRenderer()
        ))

        @reg.action(\"rows\")
        def rows():
            return {\"__jinja__\": \"rows.html\", \"context\": {\"items\": items}}

    Or return a JinjaTemplateValue helper.
    """

    def __init__(self, env: Any):
        """
        Parameters
        ----------
        env:
            jinja2.Environment (or any object with ``get_template(name).render``).
        """
        self.env = env

    def render(self, value: Any) -> str | None:
        # Explicit dict protocol for actions that don't want a custom class
        if isinstance(value, dict) and "__jinja__" in value:
            name = value["__jinja__"]
            ctx = value.get("context") or value.get("ctx") or {}
            return self.env.get_template(name).render(**ctx)
        # Helper instance
        if isinstance(value, JinjaTemplateValue):
            return self.env.get_template(value.template).render(**value.context)
        return None


class JinjaTemplateValue:
    """
    Convenient return type for Jinja-backed actions.

    Usage::

        return JinjaTemplateValue(\"partials/row.html\", item=row)
    """

    __slots__ = ("template", "context")

    def __init__(self, template: str, **context: Any):
        self.template = template
        self.context = context


class MarkupRenderer:
    """
    Pass through objects that expose ``__html__()`` (MarkupSafe, etc.).

    Common in Flask/Jinja ecosystems — plug-and-play without importing MarkupSafe.
    """

    def render(self, value: Any) -> str | None:
        dunder = getattr(value, "__html__", None)
        if callable(dunder):
            out = dunder()
            return out if isinstance(out, str) else str(out)
        return None
