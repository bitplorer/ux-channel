"""
Starlette host adapter — security parity with FastAPI (next steps).
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde
from ux_channel.wire.negotiate import decode_http_body, encode_http_body
from ux_channel.wire.core import MEDIA_TYPES

import json
from pathlib import Path
from typing import Any, Optional

from ux_channel.host.registry import ActionRegistry
from ux_channel.security.security import channel_header_ok, content_length_ok, origin_allowed
from ux_channel.transport.stream import ResultStream, format_sse
from ux_channel.devtools.trace import FrameKind, get_tracer
from ux_channel.protocol.types import Intent, Result

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
    from starlette.routing import Mount, Route
    from starlette.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ux_channel.asgi.starlette requires starlette. "
        "Install with: pip install 'ux-channel[starlette]'"
    ) from exc

CHANNEL_JSON = MEDIA_TYPES["json"]


def static_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "static"


class StarletteHostAdapter:
    name = "starlette"

    def mount(
        self,
        app: Any,
        registry: ActionRegistry,
        *,
        path: str = "/ux-channel",
        config: Any = None,
        **kwargs: Any,
    ) -> Any:
        mount_channel_starlette(app, registry, path=path, config=config, **kwargs)
        return app


def channel_routes(
    registry: ActionRegistry,
    *,
    path: str = "/ux-channel",
    config: Any = None,
    trusted_proxy: bool = False,
) -> list[Any]:
    path = path.rstrip("/") or "/ux-channel"
    max_request = int(getattr(config, "max_request_bytes", 256_000) or 256_000)
    allowed_origins = tuple(getattr(config, "allowed_origins", ()) or ())
    enforce_same = bool(getattr(config, "enforce_same_origin", True))
    health_list = bool(getattr(config, "health_list_actions", False))
    ip_rpm = int(getattr(config, "rate_limit_per_minute", 0) or 0)
    ip_burst = float(getattr(config, "rate_limit_burst", 30) or 30)
    ip_limiter = None
    if ip_rpm > 0:
        from ux_channel.security.ratelimit import MemoryRateLimiter

        ip_limiter = MemoryRateLimiter(rate_per_minute=ip_rpm, burst=ip_burst)

    async def uid_action(request: Request) -> Response:
        from ux_channel.asgi.pipeline import headers_from_starlette, preflight_action

        ip = request.client.host if request.client else "unknown"
        fail = preflight_action(
            headers_from_starlette(request.headers),
            config=config,
            ip_limiter=ip_limiter,
            client_ip=ip,
            trusted_proxy=trusted_proxy,
        )
        if fail is not None:
            result, status, extra = fail
            hdrs = {k.decode(): v.decode() for k, v in extra} if extra else None
            return JSONResponse(result.to_dict(), status_code=status, headers=hdrs)
        try:
            raw = await request.body()
            if len(raw) > max_request:
                return JSONResponse(
                    Result.failure("payload_too_large", "request too large").to_dict(),
                    status_code=413,
                )
            body = decode_http_body(raw or b"{}", content_type=request.headers.get("content-type"))
            intent = Intent.from_dict(body)
        except Exception as exc:
            return JSONResponse(
                Result.failure("bad_request", f"invalid intent: {exc}").to_dict(),
                status_code=400,
            )
        get_tracer().emit(
            FrameKind.HTTP,
            f"POST action {intent.action}",
            request_id=intent.request_id,
            action=intent.action,
        )
        registry.bind_request(request)
        result = await registry.async_dispatch(intent)
        accept = (request.headers.get("accept") or "").lower()
        if "text/event-stream" in accept or intent.accept_stream:
            stream = ResultStream()

            async def gen():
                yield format_sse(stream.chunk(result, done=True))

            return StreamingResponse(gen(), media_type="text/event-stream")
        if "text/html" in accept and CHANNEL_JSON not in accept:

            html = ""
            for op in result.ops:
                if op.get("op") in ("morph", "swap") and "html" in op:
                    html = str(op["html"])
                    break
            return HTMLResponse(html, status_code=200 if result.ok else 422)
        from ux_channel.protocol.error_map import ensure_error_meta, http_status_for
        from ux_channel.transport.backoff import extract_retry_after_s

        result = ensure_error_meta(result)
        status = http_status_for(result)
        headers = {}
        ra = extract_retry_after_s(result)
        if ra is not None:
            headers["Retry-After"] = str(int(max(0, round(ra))))
        elif status == 429:
            headers["Retry-After"] = "5"
        blob = encode_http_body(
            result.to_dict(),
            accept=request.headers.get("accept"),
            content_type_in=request.headers.get("content-type"),
        )
        from ux_channel.wire.negotiate import response_headers_for

        headers.update(response_headers_for(blob))
        return Response(
            content=blob.data,
            status_code=status,
            media_type=blob.media_type,
            headers=headers or None,
        )

    async def health(_: Request) -> Response:
        body: dict[str, Any] = {"ok": True, "v": "1", "package": "ux-channel", "status": "live"}
        if health_list:
            body["actions"] = registry.names()
        return JSONResponse(body)

    async def version_ep(_: Request) -> Response:
        from ux_channel.devtools.info import package_info
        return JSONResponse(package_info(registry))

    async def ready(_: Request) -> Response:
        from ux_channel.devtools.info import package_info
        body = package_info(registry)
        body["ok"] = True
        body["status"] = "ready"
        return JSONResponse(body)

    return [
        Route(f"{path}/action", uid_action, methods=["POST"]),
        Route(f"{path}/health", health, methods=["GET"]),
        Route(f"{path}/ready", ready, methods=["GET"]),
        Route(f"{path}/version", version_ep, methods=["GET"]),
        Mount(
            f"{path}/static",
            app=StaticFiles(directory=str(static_dir())),
            name="ux_channel-static",
        ),
    ]


def mount_channel_starlette(
    app: Starlette,
    registry: ActionRegistry,
    *,
    path: str = "/ux-channel",
    config: Any = None,
    trusted_proxy: bool = False,
) -> None:
    if config is not None and getattr(config, "path", None):
        path = str(config.path)
    app.routes.extend(
        channel_routes(registry, path=path, config=config, trusted_proxy=trusted_proxy)
    )
    app.state.ux_channel_registry = registry  # type: ignore[attr-defined]
    app.state.ux_channel_config = config  # type: ignore[attr-defined]


# Same mount API as FastAPI (name parity) / docs examples
def mount_channel(
    app: Starlette,
    registry: ActionRegistry,
    *,
    path: str = "/ux-channel",
    config: Any = None,
    trusted_proxy: bool = False,
    **kwargs: Any,
) -> None:
    """Alias of mount_channel_starlette for host-agnostic docs."""
    mount_channel_starlette(
        app, registry, path=path, config=config, trusted_proxy=trusted_proxy, **kwargs
    )
