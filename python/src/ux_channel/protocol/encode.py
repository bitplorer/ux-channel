"""
encode_result — lift Python return values into Result.

First principles
----------------
Handlers should return whatever is natural: ``Result``, ``None``, an op
dict, a list of ops, HTML (with target), ``Go("/path")``, or ``ActionError``.

This module is the **adapter** that normalizes those into one Result so the
registry finalize path stays simple.

Wire-shape dicts ``{"ok": false, "error": {...}}`` are accepted (footgun fix).
Arbitrary mappings without ``ok``/``op`` are not silently treated as success
(except toast/revalidate config via RegionBook.command coerce).

See: docs/RESULT.md.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.protocol.errors import ActionError
from ux_channel.protocol.ops import morph, navigate
from ux_channel.protocol.types import Result


from ux_channel.protocol.navigate_markers import Go, Navigate  # re-export


def encode_result(
    value: Any,
    *,
    renderer: Any = None,
    default_target: Optional[str] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Result:
    """Convert an action return value into a Result."""
    base_meta = dict(meta or {})

    if isinstance(value, Result):
        if base_meta:
            merged = {**base_meta, **value.meta}
            return Result(
                v=value.v,
                ok=value.ok,
                ops=list(value.ops),
                error=value.error,
                meta=merged,
            )
        return value

    # Architecture EffectGraph — project in Channel after-hook (classic floor otherwise)
    if isinstance(value, Mapping) and "_graph" in value:
        data = {k: v for k, v in value.items() if k != "_graph"}
        data.setdefault("ok", True)
        data.setdefault("ops", [])
        try:
            rebuilt = Result.from_dict(data)  # type: ignore[arg-type]
        except Exception:
            rebuilt = Result(
                ok=bool(value.get("ok", True)),
                ops=list(value.get("ops") or []),
            )
        rebuilt.meta = {
            **base_meta,
            **dict(value.get("meta") or {}),
            "_graph": value["_graph"],
        }
        return rebuilt

    # Accidental Result.to_dict() / wire-shape return — common footgun
    if (
        isinstance(value, Mapping)
        and "ok" in value
        and "op" not in value
        and ("ops" in value or "error" in value)
    ):
        try:
            data = dict(value)
            data.setdefault("ops", [])
            rebuilt = Result.from_dict(data)  # type: ignore[arg-type]
            if base_meta:
                rebuilt.meta = {**base_meta, **(rebuilt.meta or {})}
            return rebuilt
        except Exception:
            pass  # fall through to TypeError below

    if isinstance(value, ActionError):
        return Result.failure(
            value.code,
            value.message,
            *value.ops,
            fields=value.fields,
            **base_meta,
        )

    if isinstance(value, Navigate):
        # navigate() soft-blocks unsafe hrefs as noop; Go/Navigate return path
        # stays fail-closed as an error Result (clearer than silent noop).
        op = navigate(value.href, replace=value.replace)
        d = op if isinstance(op, dict) else getattr(op, "to_dict", lambda: op)()
        if isinstance(d, dict) and d.get("op") == "noop" and (d.get("meta") or {}).get(
            "reason"
        ) == "unsafe_href":
            return Result.failure(
                "bad_request",
                "unsafe navigation href blocked",
                **base_meta,
            )
        return Result.success(op, **base_meta)

    if isinstance(value, Mapping) and "op" in value:
        return Result.success(dict(value), **base_meta)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        # list of ops
        if value and all(isinstance(x, Mapping) and "op" in x for x in value):
            return Result.success(*[dict(x) for x in value], **base_meta)
        # empty list → ok noop
        if len(value) == 0:
            return Result.success(**base_meta)

    # None → successful no-op
    if value is None:
        return Result(ok=True, ops=[], meta=base_meta)

    if renderer is None:
        from ux_channel.render.renderers import ChainRenderer, StringRenderer
        renderer = ChainRenderer(StringRenderer())
    r = renderer
    html = r.render(value)
    if html is not None:
        target = default_target
        if not target:
            # Try to extract data-channel-id from fragment root
            target = _guess_target_from_html(html)
        if not target:
            raise ValueError(
                "HTML return requires Intent.target, morph(...), "
                "or a root element with data-channel-id"
            )
        return Result.success(morph(target=target, html=html), **base_meta)

    raise TypeError(
        f"cannot encode action return type {type(value)!r} as Result; "
        "return Result, Op, HTML str with target, Navigate/Go, or None"
    )


def _guess_target_from_html(html: str) -> Optional[str]:
    """Best-effort: first data-channel-id=\"...\" in fragment."""
    import re

    m = re.search(r'data-channel-id=["\']([^"\']+)["\']', html)
    if m:
        return f'[data-channel-id="{m.group(1)}"]'
    m = re.search(r'\bid=["\']([^"\']+)["\']', html)
    if m:
        return f"#{m.group(1)}"
    return None
