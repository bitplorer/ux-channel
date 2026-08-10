"""
WebSocket message helpers for uxchannel duplex channel.

Client → server
  {"type":"subscribe","topic":"public.x"}
  {"type":"unsubscribe","topic":"public.x"}
  {"type":"intent", ...Intent fields...}   # optional; caps still required
  {"type":"ping"}

Server → client
  {"type":"hello","v":"1","runtime":"0.1.0"}
  {"type":"subscribed","topic":"..."}
  {"type":"unsubscribed","topic":"..."}
  {"type":"result", ...Result...}
  {"type":"error","code":"...","message":"..."}
  {"type":"pong"}
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
from typing import Any, Mapping, Optional

from ux_channel._version import __version__


def hello_message() -> dict[str, Any]:
    return {"type": "hello", "v": "1", "runtime": __version__}


def error_message(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body = {"type": "error", "code": code, "message": message}
    body.update(extra)
    return body


def result_message(result: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        data = result.to_dict()
    else:
        data = dict(result)
    out = {"type": "result"}
    out.update(data)
    return out


def parse_client_message(raw: str | bytes, *, max_bytes: int) -> dict[str, Any]:
    if isinstance(raw, bytes):
        if len(raw) > max_bytes:
            raise ValueError("message too large")
        text = raw.decode("utf-8")
    else:
        if len(raw.encode("utf-8")) > max_bytes:
            raise ValueError("message too large")
        text = raw
    data = _serde.loads(text)
    if not isinstance(data, dict):
        raise ValueError("message must be a JSON object")
    return data
