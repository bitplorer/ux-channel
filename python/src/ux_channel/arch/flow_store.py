"""Flow correlation + optional durable store (host/app). Not authority."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, MutableMapping, Optional


class FlowError(KeyError):
    """Unknown or closed flow. Never treat flow_id as a capability."""


def new_flow_id(prefix: str = "flow") -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def attach_flow_meta(
    result: MutableMapping[str, Any],
    *,
    flow_id: str,
    step: Optional[int] = None,
    flow_mode: str = "auto",
) -> MutableMapping[str, Any]:
    if flow_mode == "off":
        return result
    if flow_mode != "auto":
        raise ValueError('flow_mode must be "auto" or "off"')
    meta = dict(result.get("meta") or {})
    meta["flow_id"] = flow_id
    if step is not None:
        meta["step"] = int(step)
    result["meta"] = meta
    return result


@dataclass
class FlowRecord:
    flow_id: str
    kind: str
    step: int = 1
    status: str = "open"
    data: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class FlowStore:
    def __init__(self, *, max_rows: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._rows: Dict[str, FlowRecord] = {}
        self.max_rows = max_rows

    def start(self, kind: str, *, flow_id: Optional[str] = None, data: Optional[dict] = None) -> FlowRecord:
        fid = flow_id or new_flow_id()
        rec = FlowRecord(flow_id=fid, kind=kind, step=1, data=dict(data or {}))
        with self._lock:
            if fid not in self._rows and len(self._rows) >= self.max_rows:
                raise FlowError("flow store full")
            self._rows[fid] = rec
        return rec

    def get(self, flow_id: str) -> Optional[FlowRecord]:
        with self._lock:
            return self._rows.get(flow_id)

    def advance(self, flow_id: str, *, step: Optional[int] = None, data: Optional[dict] = None) -> FlowRecord:
        with self._lock:
            rec = self._rows.get(flow_id)
            if rec is None:
                raise FlowError(f"unknown flow {flow_id}")
            if rec.status != "open":
                raise FlowError(f"flow not open ({rec.status})")
            if step is not None:
                rec.step = step
            else:
                rec.step += 1
            if data:
                rec.data.update(data)
            rec.updated_at = time.time()
            return rec

    def complete(self, flow_id: str) -> FlowRecord:
        with self._lock:
            rec = self._rows.get(flow_id)
            if rec is None:
                raise FlowError(f"unknown flow {flow_id}")
            rec.status = "complete"
            rec.updated_at = time.time()
            return rec
