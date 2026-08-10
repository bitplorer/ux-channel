"""
FastAPI / Starlette HTML responses — ux-dom-compatible.

ux_dom.response.HTMLResponse calls ``__render__()`` on tag trees.
We do the same for ``HtmlFragment``, SafeHtml, Region, and str.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def render_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8")
    if isinstance(content, str):
        return content
    if hasattr(content, "__render__"):
        try:
            return str(content.__render__())
        except TypeError:
            return str(content.__render__)  # unlikely
    if hasattr(content, "__html__"):
        return str(content.__html__())
    if getattr(content, "uid", None) is not None:
        for meth in ("html", "ssr"):
            fn = getattr(content, meth, None)
            if callable(fn):
                try:
                    return str(fn())
                except Exception:
                    continue
    return str(content)


try:
    from starlette.responses import HTMLResponse as _StarletteHTMLResponse

    class HTMLResponse(_StarletteHTMLResponse):
        """Like ux_dom.response.HTMLResponse — renders ``__render__`` / ``__html__``."""

        media_type = "text/html"

        def render(self, content: Any) -> bytes:
            return super().render(render_content(content))  # type: ignore[return-value]

    def html_response(endpoint: Optional[F] = None) -> Callable[..., Any]:
        """Decorator: wrap return value in HTMLResponse if not already a Response."""

        def deco(fn: F) -> F:
            import asyncio
            from functools import wraps

            if asyncio.iscoroutinefunction(fn):

                @wraps(fn)
                async def async_inner(*args: Any, **kwargs: Any) -> Any:
                    out = await fn(*args, **kwargs)
                    if hasattr(out, "body") and hasattr(out, "status_code"):
                        return out
                    return HTMLResponse(out)

                return async_inner  # type: ignore[return-value]

            @wraps(fn)
            def inner(*args: Any, **kwargs: Any) -> Any:
                out = fn(*args, **kwargs)
                if hasattr(out, "body") and hasattr(out, "status_code"):
                    return out
                return HTMLResponse(out)

            return inner  # type: ignore[return-value]

        if endpoint is not None:
            return deco(endpoint)
        return deco

except ImportError:  # pragma: no cover
    HTMLResponse = None  # type: ignore[misc, assignment]

    def html_response(endpoint=None):  # type: ignore[misc, no-redef]
        raise ImportError("starlette required for ux_channel.response")
