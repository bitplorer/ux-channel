"""Host runtime: session, registry, project, proof, stamps, flow.

Uses production ``CapService`` (itsdangerous) + MemoryNonceStore.
Cap key must differ from proof key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional

from ux_channel.arch.dispatch import ArchRegistry, RegistryConfig
from ux_channel.arch.effects import EffectGraph
from ux_channel.arch.flow_store import FlowStore, attach_flow_meta
from ux_channel.arch.project import project
from ux_channel.arch.proof import ProofService
from ux_channel.arch.stamps import StampTable
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.protocol.capability import CapService


@dataclass
class HostConfig:
    effects: str = "auto"
    proofs: str = "auto"  # auto | require | off
    flow: str = "auto"
    demo_mode: bool = False
    require_cap: bool = True


@dataclass
class Session:
    session_id: str
    gen: int = 1
    peer_hello: Dict[str, Any] = field(default_factory=dict)


class HostRuntime:
    def __init__(
        self,
        *,
        cap_secret: str,
        proof_secret: str,
        config: Optional[HostConfig] = None,
    ) -> None:
        if not config:
            config = HostConfig()
        if not config.demo_mode and "conformance-oracle" in cap_secret:
            raise RuntimeError("prod refuse: oracle/demo secret")
        if cap_secret == proof_secret:
            raise RuntimeError("Cap secret must differ from proof secret")

        self.config = config
        self.nonce = MemoryNonceStore()
        self.caps = CapService(cap_secret, nonce_store=self.nonce)
        self.proofs = ProofService(proof_secret)
        self.stamps = StampTable()
        self.flows = FlowStore()
        self.registry = ArchRegistry(
            self.caps,
            RegistryConfig(
                require_cap=config.require_cap,
                open_actions=set(),
            ),
        )
        self.sessions: Dict[str, Session] = {}

    def register(self, action: str, handler: Callable) -> None:
        self.registry.register(action, handler)

    def set_hello(self, session_id: str, hello: Mapping[str, Any]) -> None:
        s = self.sessions.setdefault(session_id, Session(session_id=session_id))
        s.peer_hello = dict(hello)

    def revoke(self, session_id: str) -> None:
        s = self.sessions.get(session_id)
        if s:
            s.gen += 1
            self.stamps.on_revoke(session_id)

    def grant_stamp(self, session_id: str, kind: str, methods: set[str]) -> str:
        s = self.sessions.setdefault(session_id, Session(session_id=session_id))
        st = self.stamps.grant(session_id, s.gen, kind, methods)
        return st.stamp_id

    def emit_from_graph(
        self,
        g: EffectGraph,
        *,
        session_id: str = "default",
        ok: bool = True,
        flow_id: Optional[str] = None,
        step: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> dict:
        s = self.sessions.setdefault(session_id, Session(session_id=session_id))
        ops = project(g, s.peer_hello, effects=self.config.effects)
        result: dict[str, Any] = {"ok": ok, "ops": ops, "meta": dict(meta or {})}
        if flow_id and self.config.flow == "auto":
            attach_flow_meta(result, flow_id=flow_id, step=step, flow_mode="auto")
        need_proof = self.config.proofs in ("auto", "require") and (
            s.peer_hello.get("effect_proof") or self.config.proofs == "require"
        )
        if need_proof:
            self.proofs.sign(result, session_id=session_id, gen=s.gen)
        return result

    def handle_intent(self, intent: Mapping[str, Any], *, session_id: str = "default") -> dict:
        self.sessions.setdefault(session_id, Session(session_id=session_id))
        hello = (intent.get("meta") or {}).get("hello")
        if isinstance(hello, dict):
            self.set_hello(session_id, hello)
        result = self.registry.dispatch(intent)
        if "_graph" in result:
            g = result.pop("_graph")
            projected = self.emit_from_graph(
                g,
                session_id=session_id,
                ok=bool(result.get("ok", True)),
                flow_id=(result.get("meta") or {}).get("flow_id"),
                step=(result.get("meta") or {}).get("step"),
                meta=result.get("meta"),
            )
            projected["ok"] = result.get("ok", True)
            if result.get("error"):
                projected["error"] = result["error"]
            return projected
        s = self.sessions[session_id]
        need_proof = self.config.proofs in ("auto", "require") and (
            s.peer_hello.get("effect_proof") or self.config.proofs == "require"
        )
        if need_proof and result.get("ops") is not None:
            self.proofs.sign(result, session_id=session_id, gen=s.gen)
        if self.config.flow == "auto":
            fid = (intent.get("args") or {}).get("flow_id") or (intent.get("meta") or {}).get(
                "flow_id"
            )
            if fid and "flow_id" not in (result.get("meta") or {}):
                attach_flow_meta(result, flow_id=str(fid), flow_mode="auto")
        return result

    def health(self) -> dict:
        return {
            "demo_mode": self.config.demo_mode,
            "effects": self.config.effects,
            "proofs": self.config.proofs,
            "flow": self.config.flow,
            "sessions": len(self.sessions),
        }
