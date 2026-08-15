"""Attach the enhancement plane onto a Channel instance.

Does **not** grow root public API. Call explicitly or from Channel.boot
when config.enhance is truthy.

Provides:
  - ch.enhance.handshake  — HandshakeRegistry
  - ch.enhance.recorder   — optional SessionRecorder (per session)
  - ch.enhance.mint_continuation — real attenuated Cap mint
  - ch.enhance.project_result / accept_hello helpers
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.enhance.continuations import Continuation, attach_continuations
from ux_channel.enhance.handshake import HandshakeRegistry, PeerSession
from ux_channel.enhance.negotiation import PeerHello
from ux_channel.enhance.recorder import SessionRecorder
from ux_channel.enhance.delta import region_hash

log = logging.getLogger("ux_channel.enhance.attach")


def session_id_from_headers(
    headers: Mapping[str, str],
    *,
    peer_id: str | None = None,
    client_ip: str | None = None,
) -> str:
    """Stable session key for handshake + recorder.

    Prefer explicit ``X-Channel-Session`` / ``X-Channel-Peer-Id``.
    Fall back to a short hash of IP + UA (dev only; not auth).
    """
    h = {str(k).lower(): str(v) for k, v in headers.items()}
    sid = h.get("x-channel-session") or h.get("x-channel-peer-id") or peer_id
    if sid:
        return str(sid)[:128]
    raw = f"{client_ip or 'unknown'}|{h.get('user-agent', '')}"
    return "s:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class EnhanceFacade:
    """Bound to one Channel — handshake, recorder, continuation mint."""

    channel: Any
    handshake: HandshakeRegistry = field(default_factory=HandshakeRegistry)
    recorders: dict[str, SessionRecorder] = field(default_factory=dict)
    record: bool = False

    def accept_hello(
        self,
        session_id: str,
        data: Mapping[str, Any] | PeerHello,
    ) -> PeerHello:
        hello = self.handshake.accept_hello(session_id, data)
        if self.record:
            rec = self.recorder(session_id)
            rec.record("hello", hello.to_dict(), peer=hello.peer_id)
        return hello

    def project_result(
        self,
        session_id: str,
        result: Mapping[str, Any] | Any,
        *,
        drop_unknown: bool = True,
    ) -> dict[str, Any]:
        if hasattr(result, "to_dict"):
            body = result.to_dict()
        else:
            body = dict(result)
        projected = self.handshake.project_result(
            session_id, body, drop_unknown=drop_unknown
        )
        if self.record:
            self.recorder(session_id).record_result(projected)
        return projected

    def recorder(self, session_id: str) -> SessionRecorder:
        if session_id not in self.recorders:
            self.recorders[session_id] = SessionRecorder(session_id=session_id)
        return self.recorders[session_id]

    def record_intent(
        self,
        session_id: str,
        intent: Mapping[str, Any],
        *,
        peer: str | None = None,
    ) -> None:
        if self.record:
            self.recorder(session_id).record_intent(intent, peer=peer)

    def mint_continuation(
        self,
        *,
        event: str,
        action: str,
        args: Mapping[str, Any] | None = None,
        args_from: Mapping[str, str] | None = None,
        once: bool = True,
        sub: str | None = None,
        scopes: Sequence[str] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> Continuation:
        """Mint a real host Cap for a peer continuation slot."""
        sealed = dict(args or {})
        cfg = getattr(self.channel, "config", None)
        # cek=require: compose Continuation via cek_surface; Cap still from host.
        try:
            from ux_channel.cek.surface_adapter import uses_cek_surface

            use_cek = uses_cek_surface(cfg)
        except Exception:
            use_cek = False
        reg = getattr(self.channel, "registry", None)
        if reg is None:
            raise RuntimeError("Channel has no registry — cannot mint continuation Cap")
        cap = reg.mint(
            action,
            sealed,
            sub=sub,
            once=once,
            scopes=list(scopes) if scopes else None,
        )
        if use_cek:
            from ux_channel.cek.surface_adapter import continuation_namespace

            ns = continuation_namespace(cfg)
            # cek Continuation uses store:/event: sources.
            mapped = {}
            for k, v in dict(args_from or {}).items():
                s = str(v)
                if s.startswith("store."):
                    s = "store:" + s[6:]
                elif s.startswith("event."):
                    s = "event:" + s[6:]
                mapped[str(k)] = s
            return ns.Continuation(
                event=event,
                action=action,
                cap=cap,
                args_from=mapped or None,
                static_args=dict(sealed) if sealed else None,
            )
        return Continuation(
            event=event,
            action=action,
            cap=cap,
            args_from=dict(args_from or {}),
            once=once,
            meta=dict(meta or {}),
        )

    def with_continuations(
        self,
        result_dict: dict[str, Any],
        continuations: Sequence[Continuation | Mapping[str, Any]],
    ) -> dict[str, Any]:
        return attach_continuations(result_dict, continuations)

    def region_hash(self, html_or_state: Any) -> str:
        return region_hash(html_or_state)

    def drop_session(self, session_id: str) -> None:
        self.handshake.drop(session_id)
        self.recorders.pop(session_id, None)


def attach_enhance(
    channel: Any,
    *,
    record: bool | None = None,
) -> EnhanceFacade:
    """Install ``channel.enhance`` façade. Idempotent."""
    existing = getattr(channel, "enhance", None)
    if isinstance(existing, EnhanceFacade):
        if record is not None:
            existing.record = bool(record)
        return existing

    cfg = getattr(channel, "config", None)
    if record is None:
        record = bool(getattr(cfg, "enhance_record", False)) if cfg else False

    facade = EnhanceFacade(channel=channel, record=bool(record))
    channel.enhance = facade  # type: ignore[attr-defined]
    log.debug("enhance plane attached (record=%s)", facade.record)
    return facade


def get_enhance(channel_or_registry: Any) -> EnhanceFacade | None:
    """Resolve enhance façade from Channel or registry.channel."""
    ch = channel_or_registry
    if hasattr(ch, "enhance") and isinstance(ch.enhance, EnhanceFacade):
        return ch.enhance
    # registry may hold back-ref
    ch2 = getattr(ch, "channel", None)
    if ch2 is not None and hasattr(ch2, "enhance") and isinstance(ch2.enhance, EnhanceFacade):
        return ch2.enhance
    app_state = getattr(ch, "app", None)
    return None
