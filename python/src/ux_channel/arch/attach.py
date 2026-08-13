"""Attach architecture plane onto Channel (power — not CHANNEL_PUBLIC_API).

Two runtimes, one law:

* ``Channel`` + ``attach_arch`` — production host (ActionRegistry, Result)
* ``HostRuntime`` — dict-level e2e / tests (no ASGI)

Classic IR 0.1 clients stay on the floor until they send ``meta.hello``.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Set

from ux_channel.arch.effects import EffectGraph
from ux_channel.arch.flow_store import FlowStore
from ux_channel.arch.modes import validate_arch_modes
from ux_channel.arch.project import project
from ux_channel.arch.proof import ProofService
from ux_channel.arch.stamps import StampTable
from ux_channel.protocol.types import ErrorObject, Result


def _cfg(ch: Any, name: str, default: Any) -> Any:
    cfg = getattr(ch, "config", None)
    if cfg is None:
        return default
    return getattr(cfg, name, default)


def _session_id(intent: Any) -> str:
    meta = getattr(intent, "meta", None) or {}
    if isinstance(meta, dict) and meta.get("session_id"):
        return str(meta["session_id"])
    return "default"


def _sanitize_hello(hello: Mapping[str, Any]) -> dict:
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


class _ArchSessions:
    """Process-local peer hello + generation, keyed by session_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.hello: dict[str, dict] = {}
        self.gen: dict[str, int] = {}

    def set_hello(self, session_id: str, hello: Mapping[str, Any]) -> None:
        with self._lock:
            self.hello[session_id] = _sanitize_hello(hello)
            self.gen.setdefault(session_id, 1)

    def get_hello(self, session_id: str) -> dict:
        with self._lock:
            return dict(self.hello.get(session_id) or {})

    def get_gen(self, session_id: str) -> int:
        with self._lock:
            return self.gen.setdefault(session_id, 1)

    def revoke(self, session_id: str) -> int:
        with self._lock:
            nxt = self.gen.get(session_id, 1) + 1
            self.gen[session_id] = nxt
            return nxt


def attach_arch(ch: Any) -> Any:
    """Bind stamps / flow_store / proofs / after-hook / power methods."""
    sessions = _ArchSessions()
    ch.stamps = StampTable()
    ch.flow_store = FlowStore()
    ch._arch_sessions = sessions
    # kept for callers that already read these names
    ch._peer_hello = sessions.hello
    ch._session_gen = sessions.gen
    ch.proofs = None
    proof_secret = _cfg(ch, "proof_secret", None)
    if proof_secret:
        ch.proofs = ProofService(proof_secret)

    effects = _cfg(ch, "effects", "auto")
    flow_mode = _cfg(ch, "flow", "auto")
    proofs_mode = _cfg(ch, "proofs", "auto")
    try:
        validate_arch_modes(effects, proofs_mode, flow_mode)
    except ValueError:
        effects, proofs_mode, flow_mode = "classic", "off", "off"

    def _need_proof(hello: Mapping[str, Any]) -> bool:
        if proofs_mode == "off":
            return False
        return bool(hello.get("effect_proof") or proofs_mode == "require")

    def before_arch(intent: Any, args: dict) -> Any:
        meta_in = getattr(intent, "meta", None) or {}
        if isinstance(meta_in, dict) and isinstance(meta_in.get("hello"), dict):
            sessions.set_hello(_session_id(intent), meta_in["hello"])
        hello = sessions.get_hello(_session_id(intent))
        if proofs_mode == "require" and not hello.get("effect_proof"):
            return Result(
                ok=False,
                ops=[],
                error=ErrorObject(
                    code="forbidden",
                    message="proofs=require needs effect_proof in hello",
                ),
            )
        return None

    def after_arch(intent: Any, result: Any) -> Any:
        if not isinstance(result, Result):
            return result
        meta_in = getattr(intent, "meta", None) or {}
        if isinstance(meta_in, dict) and isinstance(meta_in.get("hello"), dict):
            sessions.set_hello(_session_id(intent), meta_in["hello"])

        sid = _session_id(intent)
        hello = sessions.get_hello(sid)

        if result.meta and "_graph" in result.meta:
            g = result.meta.pop("_graph")
            result.ops = project(g, hello, effects=effects)
            max_ops = int(_cfg(ch, "max_ops", 256) or 256)
            if _count_ops(result.ops) > max_ops:
                result.ops = []
                result.ok = False
                result.error = ErrorObject(
                    code="budget", message="effect graph exceeds max_ops"
                )

        if flow_mode == "auto":
            args = getattr(intent, "args", None) or {}
            fid = None
            if isinstance(args, dict):
                fid = args.get("flow_id")
            if not fid and isinstance(meta_in, dict):
                fid = meta_in.get("flow_id")
            if fid and "flow_id" not in result.meta:
                result.meta["flow_id"] = str(fid)

        if _need_proof(hello):
            if ch.proofs is None:
                # fail closed: never emit unsigned ops when proofs are required
                result.ops = []
                if proofs_mode == "require":
                    result.ok = False
                    result.error = ErrorObject(
                        code="internal",
                        message="proofs=require but proof_secret is not configured",
                    )
            else:
                body = result.to_dict()
                ch.proofs.sign(body, session_id=sid, gen=sessions.get_gen(sid))
                if isinstance(body.get("meta"), dict):
                    result.meta = dict(body["meta"])
        return result

    if getattr(ch, "registry", None) is not None:
        ch.registry.before(before_arch)
        ch.registry.after(after_arch)

    def set_hello(session_id: str, hello: Mapping[str, Any]) -> None:
        sessions.set_hello(session_id, hello)

    def grant_stamp(session_id: str, kind: str, methods: Set[str]) -> str:
        gen = sessions.get_gen(session_id)
        return ch.stamps.grant(session_id, gen, kind, set(methods)).stamp_id

    def revoke_session(session_id: str) -> int:
        gen = sessions.revoke(session_id)
        ch.stamps.on_revoke(session_id)
        return gen

    def emit_graph(
        g: EffectGraph,
        *,
        session_id: str = "default",
        ok: bool = True,
        flow_id: Optional[str] = None,
        step: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> Result:
        hello = sessions.get_hello(session_id)
        ops = project(g, hello, effects=effects)
        max_ops = int(_cfg(ch, "max_ops", 256) or 256)
        if _count_ops(ops) > max_ops:
            return Result(
                ok=False,
                ops=[],
                error=ErrorObject(code="budget", message="effect graph exceeds max_ops"),
                meta=dict(meta or {}),
            )
        m = dict(meta or {})
        if flow_id and flow_mode == "auto":
            m["flow_id"] = flow_id
            if step is not None:
                m["step"] = int(step)
        result = Result(ok=ok, ops=ops, meta=m)
        if _need_proof(hello):
            if ch.proofs is None:
                result.ops = []
                if proofs_mode == "require":
                    result.ok = False
                    result.error = ErrorObject(
                        code="internal",
                        message="proofs=require but proof_secret is not configured",
                    )
                return result
            body = result.to_dict()
            ch.proofs.sign(body, session_id=session_id, gen=sessions.get_gen(session_id))
            result = Result.from_dict(body)
        return result

    ch.set_hello = set_hello
    ch.grant_stamp = grant_stamp
    ch.emit_graph = emit_graph
    ch.revoke_session = revoke_session
    return ch


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
