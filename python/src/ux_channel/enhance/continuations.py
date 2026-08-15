"""Wave B — Continuations: pre-minted attenuated Caps on Result.

Peer fills declared slots and re-submits. Host still verifies.
No Peer Cap mint. No Peer policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass
class Continuation:
    event: str
    action: str
    cap: str
    args_from: dict[str, str] = field(default_factory=dict)
    once: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "event": self.event,
            "action": self.action,
            "cap": self.cap,
            "args_from": dict(self.args_from),
        }
        if self.once:
            body["once"] = True
        if self.meta:
            body["meta"] = dict(self.meta)
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Continuation":
        return cls(
            event=str(data["event"]),
            action=str(data["action"]),
            cap=str(data["cap"]),
            args_from=dict(data.get("args_from") or {}),
            once=bool(data.get("once", True)),
            meta=dict(data.get("meta") or {}),
        )


def attach_continuations(
    result_dict: dict[str, Any],
    continuations: Sequence[Continuation | Mapping[str, Any]],
) -> dict[str, Any]:
    """Attach continuations envelope to a Result dict (additive)."""
    out = dict(result_dict)
    bag: list[dict[str, Any]] = []
    for c in continuations:
        if isinstance(c, Continuation):
            bag.append(c.to_dict())
        else:
            bag.append(dict(c))
    if bag:
        out["continuations"] = bag
    return out


def match_continuation(
    continuations: Sequence[Continuation | Mapping[str, Any]],
    event: Mapping[str, Any],
) -> Continuation | None:
    """Pick the first continuation whose event type matches."""
    et = str(event.get("type") or event.get("event") or "")
    if not et:
        return None
    for raw in continuations:
        c = raw if isinstance(raw, Continuation) else Continuation.from_dict(raw)
        if c.event == et:
            return c
    return None


def resolve_args(
    cont: Continuation,
    *,
    store: Mapping[str, Any] | None = None,
    event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill args_from slots from event / store. Fail closed on missing required."""
    store = store or {}
    event = event or {}
    detail = event.get("detail") if isinstance(event.get("detail"), Mapping) else event
    args: dict[str, Any] = {}
    for key, path in cont.args_from.items():
        val = _resolve_path(path, store=store, event=detail)
        if val is not None:
            args[key] = val
    return args


def _resolve_path(
    path: str,
    *,
    store: Mapping[str, Any],
    event: Mapping[str, Any],
) -> Any:
    if path.startswith("event."):
        return _dig(event, path[len("event.") :].split("."))
    if path.startswith("store."):
        return _dig(store, path[len("store.") :].split("."))
    if path in event:
        return event[path]
    return store.get(path)


def _dig(obj: Any, parts: list[str]) -> Any:
    cur = obj
    for p in parts:
        if not isinstance(cur, Mapping) or p not in cur:
            return None
        cur = cur[p]
    return cur
