"""ASGI wiring for the enhancement plane — pure helpers, no framework types.

Used by FastAPI/Starlette adapters so host and peer stay aligned:

  1. POST /hello  → accept PeerHello, store surfaces
  2. POST /action → after dispatch, project Result.ops to peer surfaces
  3. optional SessionRecorder on intent/result
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from ux_channel.enhance.attach import (
    EnhanceFacade,
    attach_enhance,
    session_id_from_headers,
)
from ux_channel.enhance.negotiation import PeerHello


def resolve_enhance(
    *,
    registry: Any = None,
    channel: Any = None,
    app_state: Any = None,
) -> EnhanceFacade | None:
    """Find or create enhance façade from common ASGI binding points."""
    ch = channel
    if ch is None and app_state is not None:
        ch = getattr(app_state, "ux_channel", None)
    if ch is None and registry is not None:
        ch = getattr(registry, "channel", None)
    if ch is None:
        return None
    existing = getattr(ch, "enhance", None)
    if existing is not None:
        return existing
    # Auto-attach if channel is present (cheap, opt-out via config.enhance=False)
    cfg = getattr(ch, "config", None)
    if cfg is not None and getattr(cfg, "enhance", True) is False:
        return None
    return attach_enhance(ch)


def handle_hello(
    enhance: EnhanceFacade,
    *,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    client_ip: str | None = None,
) -> dict[str, Any]:
    """Accept PeerHello; return ack with session_id + surface count."""
    sid = session_id_from_headers(
        headers,
        peer_id=body.get("peer_id") if isinstance(body, Mapping) else None,
        client_ip=client_ip,
    )
    if isinstance(body, Mapping) and body.get("session_id"):
        sid = str(body["session_id"])[:128]
    hello = enhance.accept_hello(sid, body)
    return {
        "ok": True,
        "v": "1",
        "session_id": sid,
        "peer_id": hello.peer_id,
        "surfaces": len(hello.surfaces),
        "features": list(hello.features),
        "ir_version": hello.ir_version,
    }


def project_after_dispatch(
    enhance: EnhanceFacade | None,
    *,
    headers: Mapping[str, str],
    result: Any,
    intent: Any = None,
    client_ip: str | None = None,
    drop_unknown: bool = True,
) -> dict[str, Any]:
    """Project Result through peer surfaces; record if enabled.

    Classic peers (no hello) keep full ops — SurfaceSet defaults to CLASSIC.
    """
    if hasattr(result, "to_dict"):
        body = result.to_dict()
    else:
        body = dict(result)

    if enhance is None:
        return body

    sid = session_id_from_headers(headers, client_ip=client_ip)
    if intent is not None:
        intent_dict = intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
        enhance.record_intent(sid, intent_dict)

    return enhance.project_result(sid, body, drop_unknown=drop_unknown)
