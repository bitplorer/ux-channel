"""Wave E — Causal spine (optional Result.trace)."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass
class Hop:
    peer: str
    at: float
    cap_fingerprint: str
    signature: str = ""
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "peer": self.peer,
            "at": self.at,
            "cap_fingerprint": self.cap_fingerprint,
        }
        if self.signature:
            body["signature"] = self.signature
        if self.note:
            body["note"] = self.note
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Hop":
        return cls(
            peer=str(data["peer"]),
            at=float(data.get("at") or 0),
            cap_fingerprint=str(data.get("cap_fingerprint") or ""),
            signature=str(data.get("signature") or ""),
            note=data.get("note"),
        )


@dataclass
class Trace:
    intent_id: str
    hops: list[Hop] = field(default_factory=list)
    caused_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "intent_id": self.intent_id,
            "hops": [h.to_dict() for h in self.hops],
        }
        if self.caused_by:
            body["caused_by"] = self.caused_by
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Trace":
        return cls(
            intent_id=str(data["intent_id"]),
            hops=[Hop.from_dict(h) for h in (data.get("hops") or [])],
            caused_by=data.get("caused_by"),
        )

    def append_hop(
        self,
        peer: str,
        cap: str | None = None,
        *,
        signature: str = "",
        note: str | None = None,
    ) -> "Trace":
        fp = _fingerprint(cap or "")
        self.hops.append(
            Hop(
                peer=peer,
                at=time.time(),
                cap_fingerprint=fp,
                signature=signature,
                note=note,
            )
        )
        return self


def attach_trace(
    result_dict: dict[str, Any],
    trace: Trace | Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(result_dict)
    if isinstance(trace, Trace):
        out["trace"] = trace.to_dict()
    else:
        out["trace"] = dict(trace)
    return out


def new_trace(intent_id: str | None = None, *, caused_by: str | None = None) -> Trace:
    if not intent_id:
        intent_id = hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16]
    return Trace(intent_id=intent_id, caused_by=caused_by)


def _fingerprint(cap: str) -> str:
    if not cap:
        return ""
    return hashlib.sha256(cap.encode("utf-8")).hexdigest()[:16]
