"""Op catalog \u2014 structured composition; wire via as_wire() / to_classic()."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class Op:
    """Structured host-side op. Never sent on the wire as-is."""

    __slots__ = ("ns", "name", "payload")

    def __init__(self, ns: str, name: str, payload: dict[str, Any] | None = None):
        self.ns = ns
        self.name = name
        self.payload = dict(payload or {})

    def to_dict(self) -> dict[str, Any]:
        return {"ns": self.ns, "name": self.name, "payload": dict(self.payload)}

    def __repr__(self) -> str:
        return f"Op({self.ns}.{self.name}, {self.payload!r})"

    # ── ui / dom ──────────────────────────────────────────────────────────

    @staticmethod
    def morph(target: str, html: str, *, morph: str = "idiomorph") -> "Op":
        _ne(target, "morph target")
        return Op("ui.dom", "morph", {"target": target, "html": html, "morph": morph})

    @staticmethod
    def swap(target: str, html: str, *, mode: str = "outerHTML") -> "Op":
        _ne(target, "swap target")
        return Op("ui.dom", "swap", {"target": target, "html": html, "mode": mode})

    @staticmethod
    def remove(target: str) -> "Op":
        _ne(target, "remove target")
        return Op("ui.dom", "remove", {"target": target})

    @staticmethod
    def set_text(target: str, text: str) -> "Op":
        _ne(target, "set_text target")
        return Op("ui.dom", "set_text", {"target": target, "text": text})

    @staticmethod
    def set_attr(target: str, attrs: Mapping[str, Any]) -> "Op":
        _ne(target, "set_attr target")
        return Op("ui.dom", "set_attr", {"target": target, "attrs": dict(attrs)})

    @staticmethod
    def toast(message: str, *, level: str = "info", duration_ms: int | None = None) -> "Op":
        p: dict[str, Any] = {"message": message, "level": level}
        if duration_ms is not None:
            p["duration_ms"] = int(duration_ms)
        return Op("ui", "toast", p)

    @staticmethod
    def focus(target: str, *, select: bool = False) -> "Op":
        _ne(target, "focus target")
        return Op("ui", "focus", {"target": target, "select": select or None})

    @staticmethod
    def scroll(target: str | None = None, **kw: Any) -> "Op":
        p = {k: v for k, v in kw.items() if v is not None}
        if target is not None:
            p["target"] = target
        return Op("ui", "scroll", p)

    @staticmethod
    def busy(target: str, busy: bool = True) -> "Op":
        _ne(target, "busy target")
        return Op("ui", "busy", {"target": target, "busy": bool(busy)})

    # ── nav ───────────────────────────────────────────────────────────────

    @staticmethod
    def navigate(href: str, *, replace: bool = False) -> "Op":
        _ne(href, "navigate href")
        return Op("nav", "navigate", {"href": href, "replace": replace or None})

    @staticmethod
    def push_url(href: str, *, replace: bool = False) -> "Op":
        _ne(href, "push_url href")
        return Op("nav", "push_url", {"href": href, "replace": replace or None})

    @staticmethod
    def reload() -> "Op":
        return Op("nav", "reload", {})

    # ── signals / timers ──────────────────────────────────────────────────

    @staticmethod
    def signal_set(path: str, value: Any) -> "Op":
        _ne(path, "signal.set path")
        return Op("signal", "set", {"path": path, "value": value})

    @staticmethod
    def timer_set(timer_id: str, ms: int, *nested: "Op") -> "Op":
        _ne(timer_id, "timer.set id")
        p: dict[str, Any] = {"id": timer_id, "ms": int(ms)}
        if nested:
            p["ops"] = [o.to_dict() for o in nested]
        return Op("timer", "set", p)

    @staticmethod
    def timer_clear(timer_id: str) -> "Op":
        _ne(timer_id, "timer.clear id")
        return Op("timer", "clear", {"id": timer_id})

    @staticmethod
    def noop() -> "Op":
        return Op("sys", "noop", {})

    # ── delta (Wave F) ────────────────────────────────────────────────────

    @staticmethod
    def delta_patch(target: str, patch: Any, *, base_hash: str | None = None) -> "Op":
        _ne(target, "delta.patch target")
        p: dict[str, Any] = {"target": target, "patch": patch}
        if base_hash is not None:
            p["base_hash"] = base_hash
        return Op("delta", "patch", p)

    @staticmethod
    def delta_signal(path: str, value: Any, *, base_hash: str | None = None) -> "Op":
        _ne(path, "delta.signal path")
        p: dict[str, Any] = {"path": path, "value": value}
        if base_hash is not None:
            p["base_hash"] = base_hash
        return Op("delta", "signal", p)


def plan(*ops: Op) -> list[Op]:
    return list(ops)


def as_wire(ops: Sequence[Op]) -> list[dict[str, Any]]:
    """Structured \u2192 intermediate ns/name form (for tests / cek bridge)."""
    return [o.to_dict() for o in ops]


def _ne(v: Any, label: str) -> None:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{label} must be non-empty str")
