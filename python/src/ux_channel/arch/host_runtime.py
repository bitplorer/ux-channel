"""Standalone host runtime for architecture e2e / tests.

Production apps should prefer ``Channel`` + ``attach_arch``. This class
speaks dict Intent/Result so gate tests do not need FastAPI.

Uses production ``CapService`` (itsdangerous) + MemoryNonceStore.
Cap key must differ from proof key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
import threading

from ux_channel.arch.dispatch import ArchRegistry, RegistryConfig
from ux_channel.arch.effects import EffectGraph
from ux_channel.arch.flow_store import FlowStore, attach_flow_meta
from ux_channel.arch.modes import validate_arch_modes
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
    max_nodes: int = 256

    def __post_init__(self) -> None:
        validate_arch_modes(self.effects, self.proofs, self.flow)


@dataclass
class Session:
    session_id: str
    gen: int = 1
    peer_hello: Dict[str, Any] = field(default_factory=dict)


class _Idempotency:
    """request_id dedupe — separate from once/jti (SPEC concurrency.md)."""

    def __init__(self, *, max_rows: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._rows: Dict[Tuple[str, str], dict] = {}
        self.max_rows = max_rows

    def get(self, session_id: str, request_id: str) -> Optional[dict]:
        with self._lock:
            return self._rows.get((session_id, request_id))

    def full(self) -> bool:
        with self._lock:
            return len(self._rows) >= self.max_rows

    def put(self, session_id: str, request_id: str, result: dict) -> Optional[str]:
        with self._lock:
            if (session_id, request_id) not in self._rows and len(self._rows) >= self.max_rows:
                return "full"
            self._rows[(session_id, request_id)] = result
            return None



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
        else:
            validate_arch_modes(config.effects, config.proofs, config.flow)
        if not config.demo_mode and "conformance-oracle" in cap_secret:
            raise RuntimeError("prod refuse: oracle/demo secret")
        if cap_secret == proof_secret:
            raise RuntimeError("Cap secret must differ from proof secret")
        if config.proofs == "require" and not proof_secret:
            raise RuntimeError("proofs=require needs a proof_secret")

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
        self.idem = _Idempotency()

    def register(self, action: str, handler: Callable) -> None:
        self.registry.register(action, handler)

    def set_hello(self, session_id: str, hello: Mapping[str, Any]) -> None:
        s = self.sessions.setdefault(session_id, Session(session_id=session_id))
        s.peer_hello = _sanitize_hello(hello)

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
        if _count_ops(ops) > int(self.config.max_nodes):
            return {
                "ok": False,
                "ops": [],
                "error": {"code": "budget", "message": "effect graph exceeds max_nodes"},
                "meta": dict(meta or {}),
            }
        result: dict[str, Any] = {"ok": ok, "ops": ops, "meta": dict(meta or {})}
        if flow_id and self.config.flow == "auto":
            attach_flow_meta(result, flow_id=flow_id, step=step, flow_mode="auto")
        if self._need_proof(s):
            if not s.peer_hello.get("effect_proof") and self.config.proofs == "require":
                return {
                    "ok": False,
                    "ops": [],
                    "error": {
                        "code": "forbidden",
                        "message": "proofs=require needs effect_proof in hello",
                    },
                    "meta": dict(meta or {}),
                }
            self.proofs.sign(result, session_id=session_id, gen=s.gen)
        return result

    def handle_intent(self, intent: Mapping[str, Any], *, session_id: str = "default") -> dict:
        self.sessions.setdefault(session_id, Session(session_id=session_id))
        hello = (intent.get("meta") or {}).get("hello")
        if isinstance(hello, dict):
            self.set_hello(session_id, hello)
        s = self.sessions[session_id]
        if self.config.proofs == "require" and not s.peer_hello.get("effect_proof"):
            return {
                "ok": False,
                "ops": [],
                "error": {
                    "code": "forbidden",
                    "message": "proofs=require needs effect_proof in hello",
                },
                "meta": {"action": intent.get("action")},
            }
        rid = intent.get("request_id")
        if rid:
            cached = self.idem.get(session_id, str(rid))
            if cached is not None:
                return dict(cached)
            if self.idem.full():
                return {
                    "ok": False,
                    "ops": [],
                    "error": {"code": "unavailable", "message": "idempotency store full"},
                    "meta": {"action": intent.get("action")},
                }
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
            result = projected
        else:
            if self._need_proof(s) and result.get("ops") is not None:
                self.proofs.sign(result, session_id=session_id, gen=s.gen)
            if self.config.flow == "auto":
                fid = (intent.get("args") or {}).get("flow_id") or (intent.get("meta") or {}).get(
                    "flow_id"
                )
                if fid and "flow_id" not in (result.get("meta") or {}):
                    attach_flow_meta(result, flow_id=str(fid), flow_mode="auto")
        if rid:
            if self.idem.put(session_id, str(rid), dict(result)) == "full":
                return dict(result)
        return result

    def _need_proof(self, session: Session) -> bool:
        mode = self.config.proofs
        if mode == "off":
            return False
        return bool(session.peer_hello.get("effect_proof") or mode == "require")

    def health(self) -> dict:
        return {
            "demo_mode": self.config.demo_mode,
            "effects": self.config.effects,
            "proofs": self.config.proofs,
            "flow": self.config.flow,
            "sessions": len(self.sessions),
            "once_jti_enforced": self.caps.nonce_store is not None,
            "stores_ok": self.caps.nonce_store is not None,
            "proof_kid": getattr(self.proofs, "kid", "p1"),
        }


def _sanitize_hello(hello: Mapping[str, Any]) -> dict:
    """Keep only list/bool fields peers are allowed to advertise."""
    out: dict[str, Any] = {}
    profiles = hello.get("profiles")
    features = hello.get("features")
    if isinstance(profiles, (list, tuple)):
        out["profiles"] = [str(p) for p in profiles]
    if isinstance(features, (list, tuple)):
        out["features"] = [str(f) for f in features]
    if "effect_proof" in hello:
        out["effect_proof"] = bool(hello.get("effect_proof"))
    return out


def _count_ops(ops: list) -> int:
    n = 0

    def walk(lst: list) -> None:
        nonlocal n
        for op in lst:
            n += 1
            if isinstance(op, dict) and isinstance(op.get("ops"), list):
                walk(op["ops"])

    walk(list(ops or []))
    return n
