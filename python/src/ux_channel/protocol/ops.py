"""Ops — client apply instructions inside a Result.

* Application apps usually return ``ch.done`` / ``ch.fail`` (which emit ops).
* Wire keys are immortal: ``op``, paths, ``data-channel-*`` targets."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional, Sequence

from ux_channel.security.security import safe_href

Op = dict[str, Any]


def _op(op_type: str, **fields: Any) -> Op:
    """Build an op dict. First arg is the op kind (must not be named ``name`` —
    event dispatch ops use a field ``name`` for the event name)."""
    body: MutableMapping[str, Any] = {"op": op_type}
    for key, value in fields.items():
        if value is not None:
            body[key] = value
    return dict(body)


def _href(href: str) -> str | None:
    """Return safe href or None (caller should drop to noop — do not raise)."""
    return safe_href(href)


def morph(
    target: str,
    html: str,
    *,
    morph: str = "idiomorph",
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    if not isinstance(target, str) or not target.strip():
        raise ValueError("morph target must be a non-empty CSS selector")
    return _op("morph", target=target, html=html, morph=morph, meta=dict(meta) if meta else None)


def swap(
    target: str,
    html: str,
    *,
    swap: str = "outerHTML",
    settle_ms: int = 0,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    if not isinstance(target, str) or not target.strip():
        raise ValueError("swap target must be a non-empty CSS selector")
    return _op(
        "swap",
        target=target,
        html=html,
        swap=swap,
        settle_ms=settle_ms or None,
        meta=dict(meta) if meta else None,
    )


def remove(target: str, *, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("remove", target=target, meta=dict(meta) if meta else None)


def set_attr(
    target: str, attrs: Mapping[str, Any], *, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    return _op("set_attr", target=target, attrs=dict(attrs), meta=dict(meta) if meta else None)


def set_text(target: str, text: str, *, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("set_text", target=target, text=text, meta=dict(meta) if meta else None)


def clear_errors(
    target: Optional[str] = None, *, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    return _op("clear_errors", target=target, meta=dict(meta) if meta else None)


def bridge_mount(
    id: str,
    package: str,
    *,
    props: Any = None,
    target: Optional[str] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    return _op(
        "bridge.mount",
        id=id,
        package=package,
        props=props,
        target=target,
        meta=dict(meta) if meta else None,
    )


def bridge_update(
    id: str,
    props: Any,
    *,
    replace: bool = False,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    return _op(
        "bridge.update",
        id=id,
        props=props,
        replace=replace or None,
        meta=dict(meta) if meta else None,
    )


def bridge_call(
    id: str,
    method: str,
    args: Optional[Sequence[Any]] = None,
    *,
    package: Optional[str] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    """Client invokes adapter method by **string name** (not Python binding)."""
    return _op(
        "bridge.call",
        id=id,
        method=method,
        args=list(args) if args is not None else None,
        package=package,
        meta=dict(meta) if meta else None,
    )


def bridge_destroy(id: str, *, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("bridge.destroy", id=id, meta=dict(meta) if meta else None)


def navigate(
    href: str, *, replace: bool = False, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    """Full page navigation (should usually be last op). Blocks javascript:/data:."""
    safe = _href(href)
    if safe is None:
        return _op(
            "noop",
            meta={
                **(dict(meta) if meta else {}),
                "dropped": "navigate",
                "reason": "unsafe_href",
            },
        )
    return _op(
        "navigate",
        href=safe,
        replace=replace or None,
        meta=dict(meta) if meta else None,
    )


def reload(*, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("reload", meta=dict(meta) if meta else None)


def push_url(
    href: str, *, replace: bool = False, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    """Update history without reload. Blocks javascript:/data:."""
    safe = _href(href)
    if safe is None:
        return _op(
            "noop",
            meta={
                **(dict(meta) if meta else {}),
                "dropped": "push_url",
                "reason": "unsafe_href",
            },
        )
    return _op(
        "push_url",
        href=safe,
        replace=replace or None,
        meta=dict(meta) if meta else None,
    )


def focus(
    target: str, *, select: bool = False, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    return _op(
        "focus", target=target, select=select or None, meta=dict(meta) if meta else None
    )


def scroll(
    *,
    target: Optional[str] = None,
    top: Optional[float] = None,
    left: Optional[float] = None,
    behavior: str = "auto",
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    return _op(
        "scroll",
        target=target,
        top=top,
        left=left,
        behavior=behavior if behavior != "auto" else None,
        meta=dict(meta) if meta else None,
    )


def toast(
    message: str,
    *,
    level: str = "info",
    duration_ms: Optional[int] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    return _op(
        "toast",
        message=message,
        level=level,
        duration_ms=duration_ms,
        meta=dict(meta) if meta else None,
    )


def dispatch(
    name: str,
    *,
    target: Optional[str] = None,
    detail: Any = None,
    bubbles: bool = True,
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    return _op(
        "dispatch",
        name=name,
        target=target,
        detail=detail,
        bubbles=bubbles,
        meta=dict(meta) if meta else None,
    )


def signal_set(
    path: str, value: Any, *, meta: Optional[Mapping[str, Any]] = None
) -> Op:
    return _op("signal.set", path=path, value=value, meta=dict(meta) if meta else None)


def noop(*, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("noop", meta=dict(meta) if meta else None)


def seq(*ops: Mapping[str, Any], meta: Optional[Mapping[str, Any]] = None) -> Op:
    """Ordered nested apply. Classic floor: host project() flattens when peer lacks seq."""
    return _op(
        "seq",
        ops=[dict(o) for o in ops],
        meta=dict(meta) if meta else None,
    )


def timer_set(
    timer_id: str,
    ms: int,
    *ops: Mapping[str, Any],
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    """Schedule nested ops. Dropped by project() for classic-only peers when ms > 0."""
    return _op(
        "timer.set",
        id=str(timer_id),
        ms=int(ms),
        ops=[dict(o) for o in ops] or None,
        meta=dict(meta) if meta else None,
    )


def timer_clear(timer_id: str, *, meta: Optional[Mapping[str, Any]] = None) -> Op:
    return _op("timer.clear", id=str(timer_id), meta=dict(meta) if meta else None)


def invoke(
    ref: str,
    method: str,
    args: Optional[Mapping[str, Any]] = None,
    *ops: Mapping[str, Any],
    meta: Optional[Mapping[str, Any]] = None,
) -> Op:
    """Host-stamped surface call. Peer checks stamp; classic project drops the wrapper."""
    return _op(
        "invoke",
        ref=ref,
        method=method,
        args=dict(args or {}),
        ops=[dict(o) for o in ops] or None,
        meta=dict(meta) if meta else None,
    )
