"""Attach architecture plane onto Channel (power — not CHANNEL_PUBLIC_API).

Wires EffectGraph project, optional proofs, flow_id correlation, stamps.
Classic IR 0.1 clients stay on the floor until they send meta.hello.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Set

from ux_channel.arch.effects import EffectGraph
from ux_channel.arch.flow_store import FlowStore
from ux_channel.arch.project import project
from ux_channel.arch.proof import ProofService
from ux_channel.arch.stamps import StampTable
from ux_channel.protocol.types import Result


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


def attach_arch(ch: Any) -> Any:
    """Bind stamps / flow_store / proofs / after-hook / power methods."""
    ch.stamps = StampTable()
    ch.flow_store = FlowStore()
    ch._peer_hello: dict[str, dict] = {}
    ch._session_gen: dict[str, int] = {}
    ch.proofs = None
    proof_secret = _cfg(ch, "proof_secret", None)
    if proof_secret:
        ch.proofs = ProofService(proof_secret)

    def after_arch(intent: Any, result: Any) -> Any:
        if not isinstance(result, Result):
            return result
        meta_in = getattr(intent, "meta", None) or {}
        if isinstance(meta_in, dict) and isinstance(meta_in.get("hello"), dict):
            ch._peer_hello[_session_id(intent)] = dict(meta_in["hello"])

        sid = _session_id(intent)
        effects = _cfg(ch, "effects", "auto")
        flow_mode = _cfg(ch, "flow", "auto")
        proofs_mode = _cfg(ch, "proofs", "auto")

        g = None
        if result.meta and "_graph" in result.meta:
            g = result.meta.pop("_graph")
        if g is not None:
            hello = ch._peer_hello.get(sid) or {}
            result.ops = project(g, hello, effects=effects)

        if flow_mode == "auto":
            args = getattr(intent, "args", None) or {}
            fid = None
            if isinstance(args, dict):
                fid = args.get("flow_id")
            if not fid and isinstance(meta_in, dict):
                fid = meta_in.get("flow_id")
            if fid and "flow_id" not in result.meta:
                result.meta["flow_id"] = str(fid)

        hello = ch._peer_hello.get(sid) or {}
        need_proof = proofs_mode in ("auto", "require") and (
            hello.get("effect_proof") or proofs_mode == "require"
        )
        if need_proof and ch.proofs is not None:
            gen = ch._session_gen.get(sid, 1)
            body = result.to_dict()
            ch.proofs.sign(body, session_id=sid, gen=gen)
            if isinstance(body.get("meta"), dict):
                result.meta = dict(body["meta"])
        return result

    if getattr(ch, "registry", None) is not None:
        ch.registry.after(after_arch)

    def set_hello(session_id: str, hello: Mapping[str, Any]) -> None:
        ch._peer_hello[session_id] = dict(hello)
        ch._session_gen.setdefault(session_id, 1)

    def grant_stamp(session_id: str, kind: str, methods: Set[str]) -> str:
        gen = ch._session_gen.setdefault(session_id, 1)
        return ch.stamps.grant(session_id, gen, kind, set(methods)).stamp_id

    def emit_graph(
        g: EffectGraph,
        *,
        session_id: str = "default",
        ok: bool = True,
        flow_id: Optional[str] = None,
        step: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> Result:
        hello = ch._peer_hello.get(session_id) or {}
        effects = _cfg(ch, "effects", "auto")
        flow_mode = _cfg(ch, "flow", "auto")
        ops = project(g, hello, effects=effects)
        m = dict(meta or {})
        if flow_id and flow_mode == "auto":
            m["flow_id"] = flow_id
            if step is not None:
                m["step"] = int(step)
        result = Result(ok=ok, ops=ops, meta=m)
        proofs_mode = _cfg(ch, "proofs", "auto")
        need_proof = proofs_mode in ("auto", "require") and (
            hello.get("effect_proof") or proofs_mode == "require"
        )
        if need_proof and ch.proofs is not None:
            gen = ch._session_gen.get(session_id, 1)
            body = result.to_dict()
            ch.proofs.sign(body, session_id=session_id, gen=gen)
            result = Result.from_dict(body)
        return result

    ch.set_hello = set_hello
    ch.grant_stamp = grant_stamp
    ch.emit_graph = emit_graph
    return ch
