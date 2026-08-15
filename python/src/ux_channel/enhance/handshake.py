"""Host-side PeerHello session + negotiate_ops integration.

Stores the last PeerHello per session and projects Result.ops to
surfaces the peer actually advertised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ux_channel.enhance.negotiation import (
    PeerHello,
    SurfaceSet,
    negotiate_ops,
)


@dataclass
class PeerSession:
    """One peer connection's negotiated surface set."""

    peer_id: str | None = None
    hello: PeerHello | None = None
    surfaces: SurfaceSet = field(default_factory=SurfaceSet)
    warnings: list[str] = field(default_factory=list)

    def accept_hello(self, data: Mapping[str, Any] | PeerHello) -> PeerHello:
        if isinstance(data, PeerHello):
            hello = data
        else:
            hello = PeerHello.from_dict(dict(data))
        self.hello = hello
        self.surfaces = hello.surface_set()
        if hello.peer_id:
            self.peer_id = hello.peer_id
        return hello

    def project_ops(
        self,
        ops: list[dict[str, Any]],
        *,
        drop_unknown: bool = True,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        emitted, warnings = negotiate_ops(ops, self.surfaces, drop_unknown=drop_unknown)
        self.warnings = warnings
        return emitted, warnings

    def project_result(
        self,
        result: Mapping[str, Any],
        *,
        drop_unknown: bool = True,
    ) -> dict[str, Any]:
        out = dict(result)
        ops = list(out.get("ops") or [])
        if ops:
            emitted, _ = self.project_ops(ops, drop_unknown=drop_unknown)
            out["ops"] = emitted
        return out


@dataclass
class HandshakeRegistry:
    """Map session_id \u2192 PeerSession."""

    sessions: dict[str, PeerSession] = field(default_factory=dict)

    def session(self, session_id: str) -> PeerSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = PeerSession()
        return self.sessions[session_id]

    def accept_hello(self, session_id: str, data: Mapping[str, Any] | PeerHello) -> PeerHello:
        return self.session(session_id).accept_hello(data)

    def project_result(
        self,
        session_id: str,
        result: Mapping[str, Any],
        *,
        drop_unknown: bool = True,
    ) -> dict[str, Any]:
        return self.session(session_id).project_result(result, drop_unknown=drop_unknown)

    def drop(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
