"""Wave G \u2014 Deterministic session recorder / replay."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass
class SessionEvent:
    kind: str  # "intent" | "result" | "event" | "hello" | "note"
    at: float
    payload: dict[str, Any]
    peer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "kind": self.kind,
            "at": self.at,
            "payload": self.payload,
        }
        if self.peer:
            body["peer"] = self.peer
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionEvent":
        return cls(
            kind=str(data["kind"]),
            at=float(data.get("at") or 0),
            payload=dict(data.get("payload") or {}),
            peer=data.get("peer"),
        )


@dataclass
class SessionRecorder:
    session_id: str
    events: list[SessionEvent] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def record(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        peer: str | None = None,
        at: float | None = None,
    ) -> None:
        self.events.append(
            SessionEvent(
                kind=kind,
                at=at if at is not None else time.time(),
                payload=dict(payload),
                peer=peer,
            )
        )

    def record_intent(self, intent: Mapping[str, Any], *, peer: str | None = None) -> None:
        self.record("intent", intent, peer=peer)

    def record_result(self, result: Mapping[str, Any], *, peer: str | None = None) -> None:
        self.record("result", result, peer=peer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": "1",
            "session_id": self.session_id,
            "meta": dict(self.meta),
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionRecorder":
        return cls(
            session_id=str(data.get("session_id") or "unknown"),
            events=[SessionEvent.from_dict(e) for e in (data.get("events") or [])],
            meta=dict(data.get("meta") or {}),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "SessionRecorder":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def iter_intents(self) -> Iterable[dict[str, Any]]:
        for e in self.events:
            if e.kind == "intent":
                yield e.payload

    def iter_results(self) -> Iterable[dict[str, Any]]:
        for e in self.events:
            if e.kind == "result":
                yield e.payload
