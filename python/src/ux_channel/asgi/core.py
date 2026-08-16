"""Pure ASGI Channel endpoint — framework-agnostic host core."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ux_channel.host.registry import ActionRegistry
from ux_channel.security.security import content_length_ok, origin_allowed
from ux_channel.transport.stream import ResultStream, format_sse
from ux_channel.devtools.trace import FrameKind, get_tracer
from ux_channel.protocol.types import Intent, Result
from ux_channel.wire.core import MEDIA_TYPES
from ux_channel.wire.negotiate import decode_http_body, encode_http_body, response_headers_for

CHANNEL_JSON = MEDIA_TYPES["json"]


async def read_body(receive: Callable, max_bytes: int) -> bytes:
    body = b""
    more = True
    while more:
        message = await receive()
        if message["type"] != "http.request":
            break
        body += message.get("body", b"")
        if len(body) > max_bytes:
            raise ValueError("payload_too_large")
        more = message.get("more_body", False)
    return body


def status_for(result: Result) -> int:
    from ux_channel.protocol.error_map import ensure_error_meta, http_status_for

    return http_status_for(ensure_error_meta(result))


async def handle_action_asgi(
    scope: dict,
    receive: Callable,
    send: Callable,
    registry: ActionRegistry,
    *,
    config: Any = None,
    ip_limiter: Any = None,
    trusted_proxy: bool = False,
) -> None:
    """
    ASGI HTTP handler for POST /action (and path already matched by router).
    """
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    max_request = int(getattr(config, "max_request_bytes", 256_000) or 256_000)
    allowed_origins = tuple(getattr(config, "allowed_origins", ()) or ())
    enforce_same = bool(getattr(config, "enforce_same_origin", True))

    cl = headers.get("content-length")
    if not content_length_ok(cl, max_request):
        await _send_result(send, Result.failure("payload_too_large", "request too large"), 413, headers)
        return

    origin = headers.get("origin")
    host = headers.get("host")
    if not origin_allowed(
        origin,
        allowed_origins=allowed_origins,
        enforce_same_origin=enforce_same,
        request_host=host,
    ):
        try:
            from ux_channel.security.security_events import emit_security

            emit_security("http_origin_deny", reason="origin not allowed")
        except Exception:
            pass
        await _send_result(send, Result.failure("forbidden", "origin not allowed"), 403, headers)
        return

    if ip_limiter is not None:
        ip = "unknown"
        if scope.get("client"):
            ip = scope["client"][0]
        if trusted_proxy and headers.get("x-forwarded-for"):
            ip = headers["x-forwarded-for"].split(",")[0].strip()
        if not ip_limiter.allow(f"ip:{ip}"):
            await _send_result(
                send,
                Result.failure("rate_limited", "Too many requests", retryable=True, retry_after=5),
                429,
                headers,
                extra_headers=[(b"retry-after", b"5")],
            )
            return

    ctype = headers.get("content-type", "")
    try:
        raw = await read_body(receive, max_request)
        body = decode_http_body(raw or b"{}", content_type=ctype)
        intent = Intent.from_dict(body)
    except ValueError as exc:
        if str(exc) == "payload_too_large":
            await _send_result(
                send, Result.failure("payload_too_large", "request too large"), 413, headers
            )
            return
        await _send_result(
            send, Result.failure("bad_request", f"invalid intent: {exc}"), 400, headers
        )
        return
    except Exception:
        await _send_result(
            send, Result.failure("bad_request", "invalid request body"), 400, headers
        )
        return

    get_tracer().emit(
        FrameKind.HTTP,
        f"POST action {intent.action}",
        request_id=intent.request_id,
        action=intent.action,
    )

    accept = headers.get("accept", "")
    want_stream = "text/event-stream" in accept or intent.accept_stream
    want_html = "text/html" in accept and CHANNEL_JSON not in accept and not want_stream

    result = await registry.async_dispatch(intent)

    if want_stream:
        stream = ResultStream()
        payload = format_sse(stream.chunk(result, done=True))
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream"),
                    (b"cache-control", b"no-cache"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
        return

    if want_html:
        html = ""
        for op in result.ops:
            if op.get("op") in ("morph", "swap") and "html" in op:
                html = str(op["html"])
                break
        data = html.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200 if result.ok else 422,
                "headers": [(b"content-type", b"text/html; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": data})
        return

    await _send_result(send, result, status_for(result), headers)


async def _send_result(
    send: Callable,
    result: Result,
    status: int,
    request_headers: Optional[dict] = None,
    extra_headers: Optional[list] = None,
) -> None:
    """Encode Result with negotiated wire format (JSON default; msgpack/cbor opt-in)."""
    req = request_headers or {}
    blob = encode_http_body(
        result.to_dict(),
        accept=req.get("accept"),
        content_type_in=req.get("content-type"),
    )
    headers = [
        (b"content-type", blob.media_type.encode()),
        (b"content-length", str(len(blob.data)).encode()),
        (b"x-channel-wire", blob.format.encode()),
    ]
    if blob.fallback:
        headers.append((b"x-channel-wire-fallback", b"1"))
        if blob.preferred_format:
            headers.append(
                (b"x-channel-wire-preferred", blob.preferred_format.encode())
            )
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": blob.data})


# Historic name used by older adapters
_send_json = _send_result
