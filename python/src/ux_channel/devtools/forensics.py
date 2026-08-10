"""Forensic frames — reconstruct what was painted after an Intent.

* **Prefer product façade:** ``attach_audit(ch)``.
* Frames may include morph HTML snippets for support replay."""


from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence

from ux_channel.render.morph_ir import MorphNode, lower_html, project_agent, project_json
from ux_channel.protocol.types import Intent, Result

__all__ = [
    "ForensicFrame",
    "ForensicStore",
    "MemoryForensicStore",
    "attach_forensics",
    "replay_html",
    "replay_agent",
]


@dataclass
class ForensicFrame:
    seq: int
    ts: float
    action: str
    ok: bool
    request_id: Optional[str]
    principal: Optional[str]
    ir: Optional[dict[str, Any]] = None  # project_json
    html: Optional[str] = None
    op_kinds: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "action": self.action,
            "ok": self.ok,
            "request_id": self.request_id,
            "principal": self.principal,
            "ir": self.ir,
            "html": self.html,
            "op_kinds": list(self.op_kinds),
            "meta": dict(self.meta),
        }


class ForensicStore(Protocol):
    def record(self, frame: ForensicFrame) -> ForensicFrame: ...
    def get(self, seq: int) -> Optional[ForensicFrame]: ...
    def since(self, seq: int = 0) -> list[ForensicFrame]: ...


class MemoryForensicStore:
    def __init__(self, *, maxlen: int = 2000) -> None:
        self._maxlen = max(50, int(maxlen))
        self._frames: list[ForensicFrame] = []
        self._seq = 0
        self._lock = threading.RLock()

    def record(self, frame: ForensicFrame) -> ForensicFrame:
        with self._lock:
            self._seq += 1
            frame.seq = self._seq
            self._frames.append(frame)
            if len(self._frames) > self._maxlen:
                self._frames = self._frames[-self._maxlen :]
            return frame

    def get(self, seq: int) -> Optional[ForensicFrame]:
        with self._lock:
            for f in self._frames:
                if f.seq == seq:
                    return f
            return None

    def since(self, seq: int = 0) -> list[ForensicFrame]:
        with self._lock:
            return [f for f in self._frames if f.seq > seq]

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)


def replay_html(frame: ForensicFrame) -> Optional[str]:
    if frame.html:
        return frame.html
    if frame.ir:
        # best-effort: IR dump is not MorphNode — return agent text
        return _serde.dumps(frame.ir, pretty=True)
    return None


def replay_agent(frame: ForensicFrame) -> dict[str, Any]:
    return {
        "seq": frame.seq,
        "action": frame.action,
        "ok": frame.ok,
        "ir": frame.ir,
        "op_kinds": list(frame.op_kinds),
        "ts": frame.ts,
    }


def snapshot_ir(node: MorphNode) -> dict[str, Any]:
    return project_json(node)


def attach_forensics(
    channel: Any,
    store: Optional[ForensicStore] = None,
    *,
    capture_html_ops: bool = True,
) -> ForensicStore:
    """
    After each action, record a forensic frame (op kinds + optional morph HTML).
    """
    bag: ForensicStore = store or MemoryForensicStore()
    reg = channel.registry

    def _after(intent: Any, result: Any) -> Any:
        try:
            if isinstance(intent, Intent):
                action = intent.action
                rid = intent.request_id
            else:
                action = str(intent.get("action", "?"))
                rid = intent.get("request_id")
            ops = list(getattr(result, "ops", None) or [])
            kinds = tuple(str(o.get("op", "?")) for o in ops if isinstance(o, dict))
            html = None
            if capture_html_ops:
                for o in ops:
                    if isinstance(o, dict) and o.get("op") == "morph" and o.get("html"):
                        html = str(o.get("html"))
                        break
            bag.record(
                ForensicFrame(
                    seq=0,
                    ts=time.time(),
                    action=action,
                    ok=bool(getattr(result, "ok", True)),
                    request_id=rid,
                    principal=None,
                    html=html,
                    op_kinds=kinds,
                )
            )
        except Exception:
            pass
        return result

    reg.after(_after)
    channel.forensics = bag
    return bag
