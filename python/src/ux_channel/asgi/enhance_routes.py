"""Optional FastAPI enhance routes — mount without editing core fastapi.py.

Usage (after mount_channel)::

    from ux_channel.asgi.enhance_routes import mount_enhance_routes
    mount_enhance_routes(app, registry, path="/ux-channel")

Or rely on Channel.boot + the hooks below when using the patched fastapi host.
"""
from __future__ import annotations

from typing import Any, Optional, Union


def mount_enhance_routes(
    app: Any,
    registry: Any,
    *,
    path: str = "/ux-channel",
    config: Any = None,
) -> Any:
    """Add POST {path}/hello and wrap is not required when core fastapi is patched.

    Always safe to call — registers /hello for PeerHello negotiation.
    """
    try:
        from fastapi import APIRouter, Request, Response
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise ImportError("fastapi required for enhance routes") from exc

    from ux_channel.protocol.types import Result
    from ux_channel.wire.core import MEDIA_TYPES
    from ux_channel.wire.negotiate import decode_http_body
    from ux_channel.enhance.asgi_wire import resolve_enhance, handle_hello, project_after_dispatch
    from ux_channel.enhance.attach import attach_enhance
    from ux_channel.asgi.pipeline import headers_from_starlette

    path = path.rstrip("/") or "/ux-channel"
    CHANNEL_JSON = MEDIA_TYPES["json"]
    router = APIRouter(prefix=path, tags=["ux-channel-enhance"])

    @router.post("/hello")
    async def peer_hello(request: Request) -> Response:
        try:
            raw = await request.body()
            body = decode_http_body(raw or b"{}", content_type=request.headers.get("content-type"))
        except Exception as exc:
            return JSONResponse(
                Result.failure("bad_request", f"invalid hello: {exc}").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                Result.failure("bad_request", "hello body must be an object").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )
        enh = resolve_enhance(registry=registry, app_state=getattr(request.app, "state", None))
        if enh is None:
            ch = getattr(registry, "channel", None) or getattr(request.app.state, "ux_channel", None)
            if ch is not None:
                enh = attach_enhance(ch)
        if enh is None:
            return JSONResponse(
                {"ok": False, "error": "enhance plane not attached — call attach_enhance(ch)"},
                status_code=503,
                media_type=CHANNEL_JSON,
            )
        ip = request.client.host if request.client else "unknown"
        ack = handle_hello(
            enh,
            headers=headers_from_starlette(request.headers),
            body=body,
            client_ip=ip,
        )
        return JSONResponse(ack, status_code=200, media_type=CHANNEL_JSON)

    app.include_router(router)
    return router


def project_result_for_request(
    *,
    registry: Any,
    request: Any,
    result: Any,
    intent: Any = None,
    client_ip: str | None = None,
) -> Any:
    """Helper for hosts that want post-dispatch projection without patching fastapi."""
    from ux_channel.protocol.types import Result
    from ux_channel.enhance.asgi_wire import resolve_enhance, project_after_dispatch
    from ux_channel.asgi.pipeline import headers_from_starlette

    enh = resolve_enhance(registry=registry, app_state=getattr(getattr(request, "app", None), "state", None))
    if enh is None:
        return result
    headers = headers_from_starlette(request.headers) if hasattr(request, "headers") else {}
    projected = project_after_dispatch(
        enh,
        headers=headers,
        result=result,
        intent=intent,
        client_ip=client_ip,
    )
    return Result.from_dict(projected)
