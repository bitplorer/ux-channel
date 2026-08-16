"""FastAPI host adapter — production-capable Channel HTTP surface.
Optional FastAPI host that mounts:
  - POST {path}/action   — Intent → Result
  - GET  {path}/health   — liveness (safe by default)
  - GET  {path}/ready    — readiness (registry present)
  - GET  {path}/static/* — client JS
Production extras (via ChannelConfig):
  - Content-Length / body size guards
  - Origin / same-origin…"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde
from ux_channel.wire.negotiate import decode_http_body, encode_http_body
from ux_channel.wire.core import MEDIA_TYPES

import json

from pathlib import Path
from typing import Any, Optional, Union

from ux_channel.host.registry import ActionRegistry
from ux_channel.security.security import (
    channel_header_ok,
    content_length_ok,
    origin_allowed,
    warn_trusted_proxy,
)
from ux_channel.protocol.types import Intent, Result
from ux_channel.devtools.trace import FrameKind, get_tracer

try:
    from fastapi import APIRouter, FastAPI, Request, Response, WebSocket
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ux_channel.asgi.fastapi requires FastAPI. "
        "Install with: pip install 'ux-channel[fastapi]'"
    ) from exc

CHANNEL_JSON = MEDIA_TYPES["json"]  # default; binary via Accept/Content-Type

def _trace_authorized(request: Request, config: Any) -> bool:
    """Require Bearer or ?token= when config.trace_token is set."""
    token = getattr(config, "trace_token", None) if config is not None else None
    if not token:
        # production without token: deny trace HTTP if environment is production
        env = getattr(config, "environment", "development") if config else "development"
        if env == "production":
            return False
        return True
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer ") and auth.split(" ", 1)[1].strip() == token:
        return True
    if request.query_params.get("token") == token:
        return True
    return False


def static_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "static"


class FastAPIHostAdapter:
    name = "fastapi"

    def mount(
        self,
        app: Any,
        registry: ActionRegistry,
        *,
        path: str = "/ux-channel",
        **kwargs: Any,
    ) -> Any:
        return mount_channel(app, registry, path=path, **kwargs)


def mount_channel(
    app: Union[FastAPI, Any],
    registry: ActionRegistry,
    *,
    path: str = "/ux-channel",
    static_path: Optional[str] = None,
    config: Any = None,
    trusted_proxy: bool = False,
    include_bridge_js: bool = True,
    mount_agent_mcp: bool = False,
    **kwargs: Any,
) -> APIRouter:
    """
    Mount Channel routes + static assets.

    Parameters
    ----------
    config:
        Optional ChannelConfig — enables body limits, origin checks, IP limits.
    trusted_proxy:
        Honor X-Forwarded-For only when behind a known reverse proxy.
    """
    path = path.rstrip("/") or "/ux-channel"
    if config is not None and getattr(config, "path", None):
        path = str(config.path).rstrip("/") or path
    static_path = static_path or f"{path}/static"
    _ = include_bridge_js

    max_request = int(getattr(config, "max_request_bytes", 256_000) or 256_000)
    allowed_origins = tuple(getattr(config, "allowed_origins", ()) or ())
    enforce_same = bool(getattr(config, "enforce_same_origin", True))
    health_list = bool(getattr(config, "health_list_actions", False))
    ip_rpm = int(getattr(config, "rate_limit_per_minute", 0) or 0)
    ip_burst = float(getattr(config, "rate_limit_burst", 30) or 30)
    trace_http = bool(getattr(config, "trace_http", False))
    require_ch = bool(getattr(config, "require_channel_header", True))
    if trusted_proxy:
        warn_trusted_proxy(True)

    ip_limiter = None
    if ip_rpm > 0:
        from ux_channel.security.ratelimit import MemoryRateLimiter

        ip_limiter = MemoryRateLimiter(rate_per_minute=ip_rpm, burst=ip_burst)

    router = APIRouter(prefix=path, tags=["ux-channel"])

    @router.post("/action")
    async def uid_action(request: Request) -> Response:
        from ux_channel.asgi.pipeline import headers_from_starlette, preflight_action

        ip = request.client.host if request.client else "unknown"
        if trusted_proxy:
            from ux_channel.security.ratelimit import client_ip_from_scope

            ip = client_ip_from_scope(request.headers, trusted_proxy=True) or ip

        live_config = getattr(registry, "config", None) or config
        fail = preflight_action(
            headers_from_starlette(request.headers),
            config=live_config,
            ip_limiter=ip_limiter,
            client_ip=ip,
            trusted_proxy=trusted_proxy,
        )
        if fail is not None:
            result, status, extra = fail
            hdrs = {k.decode(): v.decode() for k, v in extra} if extra else None
            return JSONResponse(
                result.to_dict(),
                status_code=status,
                media_type=CHANNEL_JSON,
                headers=hdrs,
            )

        accept = (request.headers.get("accept") or "").lower()
        want_html = "text/html" in accept and CHANNEL_JSON not in accept
        ctype = (request.headers.get("content-type") or "").lower()

        try:
            if "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
                form = await request.form()
                action = form.get("_ux_action") or form.get("action")
                if not action:
                    return JSONResponse(
                        Result.failure(
                            "bad_request", "missing _ux_action in form"
                        ).to_dict(),
                        status_code=400,
                        media_type=CHANNEL_JSON,
                    )
                form_obj = {k: v for k, v in form.items() if not str(k).startswith("_")}
                body = {
                    "v": "1",
                    "action": str(action),
                    "form": form_obj,
                    "cap": form.get("_ux_cap") or form.get("cap"),
                    "target": form.get("_ux_target") or form.get("target"),
                }
            else:
                raw = await request.body()
                if len(raw) > max_request:
                    return JSONResponse(
                        Result.failure("payload_too_large", "request too large").to_dict(),
                        status_code=413,
                        media_type=CHANNEL_JSON,
                    )
                import json

                body = decode_http_body(raw or b"{}", content_type=request.headers.get("content-type"))
        except Exception:
            return JSONResponse(
                Result.failure("bad_request", "invalid request body").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )

        try:
            intent = Intent.from_dict(body)
        except Exception as exc:
            return JSONResponse(
                Result.failure("bad_request", f"invalid intent: {exc}").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )

        tr = get_tracer()
        tr.emit(
            FrameKind.HTTP,
            f"POST action {intent.action}",
            request_id=intent.request_id,
            action=intent.action,
            detail={"path": str(request.url.path), "client": request.client.host if request.client else None},
        )
        registry.bind_request(request)
        result = await registry.async_dispatch(intent)
        if result.meta is not None and intent.request_id:
            result.meta.setdefault("request_id", intent.request_id)

        # SSE progressive / single-chunk stream
        if "text/event-stream" in accept or getattr(intent, "accept_stream", False):
            from ux_channel.transport.stream import ResultStream, format_sse
            from fastapi.responses import StreamingResponse

            async def gen():
                stream = ResultStream()
                yield format_sse(stream.chunk(result, done=True))

            return StreamingResponse(gen(), media_type="text/event-stream")

        if want_html:
            html = _primary_html(result)
            status = 200 if result.ok else 422
            return HTMLResponse(html or "", status_code=status)

        status = _status_for(result)
        headers: dict[str, str] = {}
        ra_h = _retry_after_header(result, status)
        if ra_h is not None:
            headers["Retry-After"] = ra_h
        blob = encode_http_body(
            result.to_dict(),
            accept=accept,
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

    @router.post("/batch")
    async def batch_action(request: Request):
        """Dispatch multiple Intents in one round-trip (max 16 by default)."""
        from ux_channel.transport.batch import dispatch_batch_async, DEFAULT_MAX_BATCH

        headers = request.headers
        cl = headers.get("content-length")
        if not content_length_ok(cl, max_request):
            return JSONResponse(
                Result.failure("payload_too_large", "request too large").to_dict(),
                status_code=413,
                media_type=CHANNEL_JSON,
            )
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
                emit_security("http_origin_deny", reason="origin not allowed", client=str(origin or ""))
            except Exception:
                pass
            return JSONResponse(
                Result.failure("forbidden", "origin not allowed").to_dict(),
                status_code=403,
                media_type=CHANNEL_JSON,
            )
        ctype = headers.get("content-type") or ""
        if not channel_header_ok(headers, required=require_ch, content_type=ctype):
            try:
                from ux_channel.security.security_events import emit_security
                emit_security("http_csrf_deny", reason="missing X-Channel header")
            except Exception:
                pass
            return JSONResponse(
                Result.failure("forbidden", "missing X-Channel header").to_dict(),
                status_code=403,
                media_type=CHANNEL_JSON,
            )
        try:
            raw = await request.body()
            if len(raw) > max_request:
                return JSONResponse(
                    Result.failure("payload_too_large", "request too large").to_dict(),
                    status_code=413,
                    media_type=CHANNEL_JSON,
                )
            body = decode_http_body(raw or b"{}", content_type=request.headers.get("content-type"))
        except Exception as exc:
            return JSONResponse(
                Result.failure("bad_request", f"invalid batch: {exc}").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )
        items = body.get("batch") or body.get("intents") or []
        if not isinstance(items, list):
            return JSONResponse(
                Result.failure("bad_request", "batch must be a list").to_dict(),
                status_code=400,
                media_type=CHANNEL_JSON,
            )
        max_items = int(getattr(config, "max_batch_items", DEFAULT_MAX_BATCH) or DEFAULT_MAX_BATCH)
        registry.bind_request(request)
        out = await dispatch_batch_async(
            registry,
            items,
            max_items=max_items,
            merge_ops=bool(body.get("merge_ops", True)),
            stop_on_error=bool(body.get("stop_on_error", False)),
            retry_retryable=bool(body.get("retry_retryable", False)),
            max_retries=int(body.get("max_retries", 1) or 1),
            retry_backoff_ms=float(body.get("retry_backoff_ms", 50) or 0),
            retry_backoff_max_ms=float(body.get("retry_backoff_max_ms", 5000) or 5000),
            retry_backoff_strategy=str(body.get("retry_backoff_strategy", "fixed") or "fixed"),
            retry_backoff_factor=float(body.get("retry_backoff_factor", 2.0) or 2.0),
            retry_after_mode=str(body.get("retry_after_mode", "max") or "max"),
            retry_require_idempotent=bool(body.get("retry_require_idempotent", True)),
        )
        from ux_channel.protocol.error_map import batch_http_status

        status = batch_http_status(out)
        # Prefer meta.http_status when enrich already set it
        meta = out.get("meta") if isinstance(out.get("meta"), dict) else None
        if meta and isinstance(meta.get("http_status"), int):
            status = int(meta["http_status"])
        resp_headers: dict[str, str] = {}
        # Prefer worst item / envelope meta.retry_after; else 429 default
        ra_h = None
        try:
            from ux_channel.transport.backoff import extract_retry_after_s, parse_retry_after

            meta = out.get("meta") if isinstance(out, dict) else None
            if isinstance(meta, dict) and meta.get("retry_after") is not None:
                ra_h = parse_retry_after(meta.get("retry_after"))
            if ra_h is None and isinstance(out.get("batch"), list):
                for item in out["batch"]:
                    s = extract_retry_after_s(item)
                    if s is not None:
                        ra_h = max(ra_h or 0.0, s)
            if ra_h is not None:
                resp_headers["Retry-After"] = str(int(max(0, round(ra_h))))
            elif status == 429:
                resp_headers["Retry-After"] = "5"
        except Exception:
            if status == 429:
                resp_headers["Retry-After"] = "5"
        return JSONResponse(
            out, status_code=status, media_type=CHANNEL_JSON, headers=resp_headers or None
        )

    @router.get("/metrics")
    async def metrics_endpoint():
        """Prometheus text if app.state.ux_channel_metrics is set."""
        m = getattr(app.state, "ux_channel_metrics", None)
        if m is None or not hasattr(m, "render_prometheus"):
            return Response("# no metrics configured\n", media_type="text/plain")
        return Response(m.render_prometheus(), media_type="text/plain; version=0.0.4")

    @router.get("/catalog")
    async def action_catalog_endpoint(request: Request):
        """List registered actions (disabled in production unless health_list_actions)."""
        if not health_list and getattr(config, "environment", "") == "production":
            return JSONResponse({"ok": False, "error": "catalog disabled"}, status_code=404)
        from ux_channel.host.action_catalog import action_catalog
        return {"ok": True, "actions": action_catalog(registry)}

    @router.get("/docs/howto")
    async def docs_howto_pointer():
        """Pointer for humans — full docs live in the package docs/ tree."""
        return {
            "ok": True,
            "message": "See repository docs/HOW_TO.md, docs/API.md, docs/COOKBOOK.md, docs/README.md",
            "docs": [
                "docs/README.md",
                "docs/HOW_TO.md",
                "docs/API.md",
                "docs/COOKBOOK.md",
                "docs/PRODUCTION.md",
                "docs/RESULT.md",
                "docs/INSPECTOR.md",
            ],
        }

    @router.get("/version")
    async def version_endpoint():
        """Package + protocol version (safe for probes and client skew checks)."""
        from ux_channel.devtools.info import package_info
        return package_info(registry)

    @router.get("/health")
    async def health() -> dict[str, Any]:
        """Liveness — safe for public probes (no secrets, optional action list)."""
        body: dict[str, Any] = {
            "ok": True,
            "v": "1",
            "package": "ux-channel",
            "status": "live",
        }
        if health_list:
            body["actions"] = registry.names()
        return body

    @router.get("/push/{topic}")
    async def push_stream(topic: str, request: Request):
        """SSE subscribe for server-push Results.

        Authorization (see ux_channel.push_security)::

          - public topic prefixes (default ``public.*``) when push_allow_public
          - signed push ticket (?ticket= or X-Channel-Push-Ticket)
          - shared push_token (Bearer or ?token=)
          - if push_require_auth is False (dev default): open

        Production defaults fail closed unless public / ticket / token.
        """
        import asyncio
        from ux_channel.transport.push import get_push_bus
        from ux_channel.security.push_security import (
            authorize_push_subscribe,
            extract_push_credentials,
        )
        from fastapi.responses import StreamingResponse

        creds = extract_push_credentials(
            headers=dict(request.headers),
            query=dict(request.query_params),
        )
        ok, reason = authorize_push_subscribe(
            config,
            topic,
            token=creds.get("token"),
            ticket=creds.get("ticket"),
            bearer=creds.get("bearer"),
        )
        if not ok:
            return JSONResponse(
                Result.failure("unauthorized", reason or "push authorization required").to_dict(),
                status_code=401,
            )

        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        bus = get_push_bus()
        bus.subscribe(topic, q)

        async def gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=15.0)
                        import json
                        yield f"data: {_serde.dumps(item, default=str)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                bus.unsubscribe(topic, q)

        return StreamingResponse(gen(), media_type="text/event-stream")


    @router.websocket("/ws")
    async def uid_websocket(websocket: WebSocket):
        """
        Production WebSocket: topic subscribe (push bus) + optional Intent dispatch.

        Query: ``token``, ``ticket``, ``topics`` (comma-separated initial subs).
        Auth: SSE-equivalent policy (tickets / push_token / public.*) + Origin check.
        Actions over WS still require normal capability verification on the registry.
        """
        import asyncio
        from ux_channel.transport.push import get_push_bus
        from ux_channel.security.push_security import extract_push_credentials
        from ux_channel.security.ws_security import (
            authorize_ws_connect,
            authorize_ws_subscribe,
            check_ws_origin,
            parse_topics_param,
        )
        from ux_channel.transport.ws_protocol import (
            error_message,
            hello_message,
            parse_client_message,
            result_message,
        )

        live_config = getattr(registry, "config", None) or config
        if live_config is not None and getattr(live_config, "ws_enabled", True) is False:
            await websocket.close(code=1008)
            return

        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        ok_o, why_o = check_ws_origin(origin, config=live_config, request_host=host)
        if not ok_o:
            try:
                from ux_channel.security.security_events import emit_security
                emit_security("ws_origin_deny", reason=why_o or "origin")
            except Exception:
                pass
            await websocket.close(code=1008, reason=(why_o or "origin")[:120])
            return

        # Wave 1: connect rate limit (client host / IP key)
        client_key = (websocket.client.host if websocket.client else None) or "unknown"
        try:
            from ux_channel.transport.ws_limits import get_ws_limiter
            lim = get_ws_limiter()
            if lim is not None:
                ok_c, why_c = lim.allow_connect(client_key)
                if not ok_c:
                    from ux_channel.security.security_events import emit_security
                    emit_security("ws_rate_connect", reason=why_c, client=client_key)
                    await websocket.close(code=1008, reason=(why_c or "rate")[:120])
                    return
        except Exception:
            pass

        header_map: dict[str, str] = {}
        for k, v in websocket.scope.get("headers", []):
            header_map[k.decode("latin-1")] = v.decode("latin-1")
        q = {str(k): str(v) for k, v in websocket.query_params.items()}
        creds = extract_push_credentials(headers=header_map, query=q)
        if not creds.get("bearer"):
            auth = header_map.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                creds["bearer"] = auth[7:].strip()

        initial = parse_topics_param(q.get("topics"))
        ok, reason = authorize_ws_connect(
            live_config,
            token=creds.get("token"),
            ticket=creds.get("ticket"),
            bearer=creds.get("bearer"),
            initial_topics=initial,
        )
        if not ok:
            try:
                from ux_channel.security.security_events import emit_security
                emit_security("ws_connect_deny", reason=reason or "unauthorized", client=client_key)
            except Exception:
                pass
            await websocket.close(code=1008, reason=(reason or "unauthorized")[:120])
            return

        await websocket.accept()
        await websocket.send_json(hello_message())

        bus = get_push_bus()
        # fan-in: each topic queue drained into conn_q by helper tasks
        conn_q: asyncio.Queue = asyncio.Queue(maxsize=128)
        topic_queues: dict[str, asyncio.Queue] = {}
        drain_tasks: dict[str, asyncio.Task] = {}
        max_subs = int(getattr(live_config, "ws_max_subscriptions", 16) or 16) if live_config else 16
        max_msg = int(getattr(live_config, "ws_max_message_bytes", 256_000) or 256_000) if live_config else 256_000
        allow_actions = bool(getattr(live_config, "ws_allow_actions", True)) if live_config else True

        async def _drain(topic: str, tq: asyncio.Queue) -> None:
            try:
                while True:
                    item = await tq.get()
                    await conn_q.put(item)
            except asyncio.CancelledError:
                return

        async def _subscribe(topic: str) -> None:
            ok_s, why_s = authorize_ws_subscribe(
                live_config,
                topic,
                token=creds.get("token"),
                ticket=creds.get("ticket"),
                bearer=creds.get("bearer"),
            )
            if not ok_s:
                try:
                    from ux_channel.security.security_events import emit_security
                    emit_security("ws_subscribe_deny", topic=topic, reason=why_s or "subscribe denied", client=client_key)
                except Exception:
                    pass
                await websocket.send_json(
                    error_message("unauthorized", why_s or "subscribe denied", topic=topic)
                )
                return
            if topic in topic_queues:
                await websocket.send_json({"type": "subscribed", "topic": topic})
                return
            if len(topic_queues) >= max_subs:
                await websocket.send_json(error_message("limit", "too many subscriptions"))
                return
            tq: asyncio.Queue = asyncio.Queue(maxsize=64)
            bus.subscribe(topic, tq)
            topic_queues[topic] = tq
            drain_tasks[topic] = asyncio.create_task(_drain(topic, tq))
            # Wave integrity: presence is process-wide (see live.touch_presence)
            try:
                from ux_channel.host.live import touch_presence
                cid = f"{client_key}:{id(websocket)}"
                touch_presence(topic, cid)
            except Exception:
                pass
            await websocket.send_json({"type": "subscribed", "topic": topic})

        async def _unsubscribe(topic: str) -> None:
            tq = topic_queues.pop(topic, None)
            task = drain_tasks.pop(topic, None)
            if task:
                task.cancel()
            if tq is not None:
                bus.unsubscribe(topic, tq)
            await websocket.send_json({"type": "unsubscribed", "topic": topic})

        for t0 in initial:
            await _subscribe(t0)

        async def pump_out() -> None:
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(conn_q.get(), timeout=20.0)
                        await websocket.send_json(result_message(item))
                    except asyncio.TimeoutError:
                        # keepalive-style ping as JSON
                        try:
                            await websocket.send_json({"type": "ping"})
                        except Exception:
                            return
            except asyncio.CancelledError:
                return
            except Exception:
                return

        out_task = asyncio.create_task(pump_out())
        try:
            while True:
                try:
                    raw = await websocket.receive_text()
                    try:
                        from ux_channel.transport.ws_limits import get_ws_limiter
                        lim = get_ws_limiter()
                        if lim is not None:
                            ok_m, why_m = lim.allow_message(client_key)
                            if not ok_m:
                                await websocket.send_json(error_message("rate", why_m or "rate limit"))
                                continue
                    except Exception:
                        pass
                except Exception:
                    break
                try:
                    msg = parse_client_message(raw, max_bytes=max_msg)
                except Exception as exc:
                    await websocket.send_json(error_message("bad_message", str(exc)))
                    continue
                mtype = str(msg.get("type") or "")
                if mtype == "ping":
                    await websocket.send_json({"type": "pong"})
                elif mtype == "subscribe":
                    await _subscribe(str(msg.get("topic") or ""))
                elif mtype == "unsubscribe":
                    await _unsubscribe(str(msg.get("topic") or ""))
                elif mtype == "intent":
                    if not allow_actions:
                        await websocket.send_json(
                            error_message("forbidden", "actions over websocket disabled")
                        )
                        continue
                    payload = {k: v for k, v in msg.items() if k != "type"}
                    try:
                        intent = Intent.from_dict(payload)
                    except Exception as exc:
                        await websocket.send_json(error_message("bad_intent", str(exc)))
                        continue
                    if not intent.action:
                        await websocket.send_json(error_message("bad_intent", "action required"))
                        continue
                    try:
                        if hasattr(registry, "async_dispatch"):
                            result = await registry.async_dispatch(intent)
                        else:
                            result = await asyncio.to_thread(registry.dispatch, intent)
                    except Exception as exc:
                        await websocket.send_json(
                            error_message("dispatch_error", str(exc)[:200])
                        )
                        continue
                    await websocket.send_json(result_message(result))
                else:
                    await websocket.send_json(
                        error_message("unknown_type", f"unknown type {mtype!r}")
                    )
        finally:
            out_task.cancel()
            for topic in list(topic_queues.keys()):
                try:
                    await _unsubscribe(topic)
                except Exception:
                    tq = topic_queues.pop(topic, None)
                    task = drain_tasks.pop(topic, None)
                    if task:
                        task.cancel()
                    if tq is not None:
                        try:
                            bus.unsubscribe(topic, tq)
                        except Exception:
                            pass


    @router.get("/ready")
    async def ready() -> Response:
        """Readiness — registry importable; light package diagnostics."""
        ok = registry is not None and hasattr(registry, "async_dispatch")
        from ux_channel.devtools.info import package_info
        payload = package_info(registry if ok else None)
        payload["ok"] = ok
        payload["status"] = "ready" if ok else "not_ready"
        return JSONResponse(payload, status_code=200 if ok else 503)

    if trace_http:
        
        @router.get("/dx")
        async def ux_dashboard():
            """Development DX dashboard HTML (disabled feel in production via config)."""
            from fastapi.responses import HTMLResponse

            from ux_channel.devtools.dashboard import build_dashboard_model, render_dashboard_html

            cfg_env = str(getattr(config, "environment", "production") or "production")
            if cfg_env == "production" and not bool(getattr(config, "inspect_enabled", False)):
                return HTMLResponse(
                    "<!doctype html><title>dx off</title><p>DX dashboard is off in production.</p>",
                    status_code=404,
                )
            doc = {}
            try:
                # registry-bound channel may not exist; lightweight model
                doc = {
                    "ok": True,
                    "diagnose": {
                        "environment": cfg_env,
                        "path": path,
                        "actions": len(getattr(registry, "_actions", {}) or {}),
                    },
                    "hints": ["Use uxchannel dashboard for full offline report with p95 graphs."],
                }
            except Exception:
                doc = {"ok": False}
            model = build_dashboard_model(doctor=doc, latencies=[])
            return HTMLResponse(render_dashboard_html(model))


        @router.get("/trace")
        async def trace_dump(request: Request, request_id: str | None = None, limit: int = 200):
            """Wireshark-like dump of recent action/bridge frames (dev only)."""
            if not _trace_authorized(request, config):
                return JSONResponse({"ok": False, "error": "trace unauthorized"}, status_code=401)
            tr = get_tracer()
            if not tr.enabled:
                return JSONResponse({"enabled": False, "frames": [], "conversations": []})
            frames = tr.frames(request_id=request_id, limit=limit)
            return {
                "enabled": True,
                "count": len(frames),
                "frames": [f.to_dict() for f in frames],
                "conversations": tr.conversations(),
            }

        @router.get("/trace/conversations")
        async def trace_conversations(request: Request):
            if not _trace_authorized(request, config):
                return JSONResponse({"ok": False, "error": "trace unauthorized"}, status_code=401)
            tr = get_tracer()
            return {"enabled": tr.enabled, "conversations": tr.conversations()}

        @router.delete("/trace")
        async def trace_clear(request: Request):
            if not _trace_authorized(request, config):
                return JSONResponse({"ok": False, "error": "trace unauthorized"}, status_code=401)
            get_tracer().clear()
            return {"ok": True}

        @router.post("/trace/client")
        async def trace_client(request: Request):
            """Ingest browser-side frames (inspector) into the same ring buffer."""
            if not _trace_authorized(request, config):
                return JSONResponse({"ok": False, "error": "trace unauthorized"}, status_code=401)
            tr = get_tracer()
            if not tr.enabled:
                return JSONResponse({"ok": False, "reason": "trace disabled"}, status_code=403)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"ok": False}, status_code=400)
            events = body if isinstance(body, list) else body.get("frames") or body.get("events") or []
            for ev in events[:100]:
                if not isinstance(ev, dict):
                    continue
                tr.emit(
                    ev.get("kind") or "client",
                    ev.get("summary") or "client event",
                    request_id=ev.get("request_id"),
                    action=ev.get("action"),
                    duration_ms=ev.get("duration_ms"),
                    ok=ev.get("ok"),
                    detail=ev.get("detail") or {},
                    trace_id=ev.get("trace_id"),
                )
            return {"ok": True, "ingested": min(len(events), 100)}


    # --- Agent / MCP modular surface (opt-in) ---
    if getattr(config, "mount_agent_mcp", False) or kwargs.get("mount_agent_mcp"):
        agent_token = getattr(config, "agent_token", None) if config else None
        confirm_secret = getattr(config, "agent_confirmation_secret", None) if config else None
        mcp_verticals = tuple(getattr(config, "mcp_verticals", ()) or ()) if config else ()
        mcp_regions = tuple(getattr(config, "mcp_resource_regions", ()) or ()) if config else ()
        mcp_ttl = int(getattr(config, "mcp_session_ttl_s", 900) or 900) if config else 900
        from ux_channel.agent_runtime.policy import AgentPolicy
        from ux_channel.mcp.asgi_routes import create_mcp_adapter, resolve_mcp_auth
        from ux_channel.mcp.sessions import get_session_store
        from ux_channel.mcp.verticals import register_builtin_verticals

        try:
            register_builtin_verticals(replace=True)
        except Exception:
            pass

        # P7: prefer Redis session store when redis_url set
        from ux_channel.mcp.sessions import get_session_store, set_session_store, build_session_store
        _ru = getattr(config, "redis_url", None) if config else None
        if _ru:
            try:
                set_session_store(build_session_store(_ru))
            except Exception:
                pass

        def _agent_policy() -> AgentPolicy:
            p = getattr(app.state, "uid_agent_policy", None)
            if p is not None:
                return p
            env = getattr(config, "environment", "production") if config else "production"
            if env == "development":
                return AgentPolicy.development()
            return AgentPolicy(allow_actions=frozenset(), allow_all=False)

        def _channel():
            return getattr(app.state, "ux_channel", None) or getattr(registry, "channel", None)

        def _adapter_for(request: Request, sess=None):
            verts = mcp_verticals
            room = ""
            scopes: tuple = ()
            sub = request.headers.get("x-channel-agent-id") or "http-mcp"
            sid = None
            if sess is not None:
                verts = sess.verticals or verts
                room = sess.room
                scopes = tuple(sess.scopes)
                sub = sess.sub or sub
                sid = sess.session_id
            return create_mcp_adapter(
                registry,
                policy=_agent_policy(),
                agent_id=sub,
                confirmation_secret=confirm_secret,
                only_marked=True,
                verticals=verts,
                resource_regions=mcp_regions,
                room=room,
                scopes=scopes,
                sub=sub,
                channel=_channel(),
                session_id=sid,
            )

        @router.get("/mcp/tools")
        async def mcp_tools_list(request: Request):
            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return _adapter_for(request, sess).list_tools()

        @router.post("/mcp/tools/call")
        async def mcp_tools_call(request: Request):
            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"error": "bad_request"}, status_code=400)
            adapter = _adapter_for(request, sess)
            if body.get("jsonrpc") or body.get("method"):
                return await adapter.handle_jsonrpc(body)
            name = body.get("name") or body.get("action")
            if not name:
                return JSONResponse({"error": "name required"}, status_code=400)
            out = await adapter.call_tool(
                name,
                body.get("arguments") or body.get("args") or {},
                confirmation=body.get("confirmation"),
                dry_run=body.get("dry_run"),
                call_id=body.get("id") or body.get("call_id"),
            )
            status = 200 if not out.get("isError") else 422
            return JSONResponse(out, status_code=status)

        @router.post("/mcp/rpc")
        async def mcp_jsonrpc(request: Request):
            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            body = await request.json()
            return await _adapter_for(request, sess).handle_jsonrpc(body)

        @router.get("/mcp/resources")
        async def mcp_resources_list(request: Request):
            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return _adapter_for(request, sess).list_resources()

        @router.get("/mcp/resources/read")
        async def mcp_resources_read(request: Request):
            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            uri = request.query_params.get("uri") or ""
            if not uri:
                return JSONResponse({"error": "uri required"}, status_code=400)
            try:
                return _adapter_for(request, sess).read_resource(uri)
            except PermissionError as exc:
                return JSONResponse({"error": str(exc)}, status_code=403)
            except ValueError as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)

        @router.post("/mcp/session")
        async def mcp_session_create(request: Request):
            """Bootstrap agent_token → claim-bound session ticket."""
            ok, sess, mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok or mode != "token":
                return JSONResponse(
                    {"error": "unauthorized", "detail": "agent_token required to mint session"},
                    status_code=401,
                )
            try:
                body = await request.json()
            except Exception:
                body = {}
            room = str(body.get("room") or "default")
            sub = str(body.get("sub") or request.headers.get("x-channel-agent-id") or "mcp-bot")
            scopes = body.get("scopes") or []
            if isinstance(scopes, str):
                scopes = [s.strip() for s in scopes.split(",") if s.strip()]
            verts = body.get("verticals") or list(mcp_verticals)
            if isinstance(verts, str):
                verts = [s.strip() for s in verts.split(",") if s.strip()]
            ttl = float(body.get("ttl_s") or mcp_ttl)
            # optional workplace ticket co-issue
            wp_ticket = None
            ch = _channel()
            if ch is not None:
                try:
                    from ux_channel.workplace import sign_workplace_ticket

                    wp_ticket = sign_workplace_ticket(
                        ch.config if hasattr(ch, "config") else config,
                        room,
                        sub=sub,
                        scopes=list(scopes) or None,
                    )
                except Exception:
                    wp_ticket = None
            session = get_session_store().create(
                agent_id=sub,
                room=room,
                sub=sub,
                scopes=scopes,
                verticals=verts,
                ttl_s=ttl,
                ticket=wp_ticket,
            )
            pub = session.to_public()
            if wp_ticket:
                pub["workplace_ticket"] = wp_ticket
            return pub

        @router.post("/mcp/session/revoke")
        async def mcp_session_revoke(request: Request):
            ok, sess, mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            try:
                body = await request.json()
            except Exception:
                body = {}
            tid = body.get("ticket") or body.get("session_id") or ""
            if not tid and sess is not None:
                tid = sess.ticket
            if not tid:
                return JSONResponse({"error": "ticket required"}, status_code=400)
            gone = get_session_store().revoke(str(tid))
            # also workplace revoke when possible
            try:
                from ux_channel.workplace import revoke_workplace_ticket

                revoke_workplace_ticket(str(tid))
            except Exception:
                pass
            return {"revoked": bool(gone), "ticket": tid}


        @router.get("/mcp/resources/subscribe")
        async def mcp_resources_subscribe(request: Request):
            """
            SSE resource invalidation stream (P8).

            Query: topic=mcp.resource.{room} | mcp.resource.session.{id}
            Auth: agent_token or MCP session ticket (same as other MCP routes).
            """
            import asyncio
            import json
            from fastapi.responses import StreamingResponse
            from ux_channel.transport.push import get_push_bus
            from ux_channel.mcp.subscribe import (
                resource_topic_for_room,
                resource_topic_for_session,
            )

            ok, sess, _mode = resolve_mcp_auth(request, agent_token=agent_token)
            if not ok:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            topic = (request.query_params.get("topic") or "").strip()
            if not topic:
                if sess is not None:
                    topic = resource_topic_for_session(sess.session_id)
                else:
                    topic = resource_topic_for_room("default")
            # only allow mcp.resource.* topics
            if not topic.startswith("mcp.resource."):
                return JSONResponse({"error": "topic must be mcp.resource.*"}, status_code=400)
            # session-bound clients may only subscribe their room/session topics
            if sess is not None:
                allowed = {
                    resource_topic_for_room(sess.room),
                    resource_topic_for_session(sess.session_id),
                }
                if topic not in allowed:
                    return JSONResponse({"error": "topic not allowed for session"}, status_code=403)

            q: asyncio.Queue = asyncio.Queue(maxsize=64)
            bus = get_push_bus()
            bus.subscribe(topic, q)

            async def gen():
                try:
                    # hello
                    yield f"data: {_serde.dumps({'event': 'subscribed', 'topic': topic})}\n\n"
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            item = await asyncio.wait_for(q.get(), timeout=15.0)
                            yield f"data: {_serde.dumps(item, default=str)}\n\n"
                        except asyncio.TimeoutError:
                            yield ": keepalive\n\n"
                finally:
                    bus.unsubscribe(topic, q)

            return StreamingResponse(gen(), media_type="text/event-stream")


# WebRTC signaling (HTTP poll + WebSocket trickle)
    if config is None or getattr(config, "webrtc_enabled", True):

        def _rtc_auth(request: Request, room: str, ticket: str | None = None):
            from ux_channel.realtime.webrtc import authorize_rtc

            live_config = getattr(registry, "config", None) or config
            return authorize_rtc(
                live_config,
                room,
                ticket=ticket
                or request.query_params.get("ticket")
                or request.headers.get("x-channel-rtc-ticket"),
                origin=request.headers.get("origin"),
                host=request.headers.get("host"),
            )

        @router.get("/rtc/ice")
        async def uid_rtc_ice(request: Request):
            """Authenticated ICE (STUN + short-lived TURN). Query: room, ticket, sub."""
            from ux_channel.realtime.webrtc_http import extract_rtc_ticket, handle_rtc_ice

            live_config = getattr(registry, "config", None) or config
            room = request.query_params.get("room") or "default"
            sub = request.query_params.get("sub") or "uid"
            try:
                ttl = request.query_params.get("ttl")
                ttl_s = int(ttl) if ttl else None
            except ValueError:
                ttl_s = None
            status, body = handle_rtc_ice(
                live_config,
                room=room,
                ticket=extract_rtc_ticket(
                    query=dict(request.query_params),
                    headers={k: v for k, v in request.headers.items()},
                ),
                origin=request.headers.get("origin"),
                host=request.headers.get("host"),
                sub=sub,
                ttl_s=ttl_s,
            )
            return JSONResponse(
                body,
                status_code=status,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        @router.get("/rtc")
        async def uid_rtc_poll(request: Request):
            """Poll WebRTC signaling: join/heartbeat + roster + inbox."""
            from ux_channel.realtime.webrtc_http import extract_rtc_ticket, handle_rtc_poll

            live_config = getattr(registry, "config", None) or config
            room = request.query_params.get("room") or "default"
            try:
                since = int(request.query_params.get("since") or 0)
            except ValueError:
                since = 0
            try:
                from ux_channel.security.ratelimit import client_ip_from_scope
                _ck = client_ip_from_scope(request.scope) or ""
            except Exception:
                _ck = ""
            status, body = handle_rtc_poll(
                live_config,
                room=room,
                peer=request.query_params.get("peer") or "",
                name=request.query_params.get("name") or "",
                since=since,
                ticket=extract_rtc_ticket(
                    query=dict(request.query_params),
                    headers={k: v for k, v in request.headers.items()},
                ),
                origin=request.headers.get("origin"),
                host=request.headers.get("host"),
                client_key=_ck,
            )
            return JSONResponse(
                body,
                status_code=status,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        @router.post("/rtc")
        async def uid_rtc_post(request: Request):
            """Post WebRTC signal, ice-done, or leave."""
            from ux_channel.realtime.webrtc_http import extract_rtc_ticket, handle_rtc_post

            live_config = getattr(registry, "config", None) or config
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
            if not isinstance(body, dict):
                return JSONResponse({"ok": False, "error": "object required"}, status_code=400)
            try:
                from ux_channel.security.ratelimit import client_ip_from_scope
                _ck = client_ip_from_scope(request.scope) or ""
            except Exception:
                _ck = ""
            status, out = handle_rtc_post(
                live_config,
                body,
                ticket=extract_rtc_ticket(
                    query=dict(request.query_params),
                    headers={k: v for k, v in request.headers.items()},
                    body=body,
                ),
                origin=request.headers.get("origin"),
                host=request.headers.get("host"),
                client_key=_ck,
            )
            return JSONResponse(
                out,
                status_code=status,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        @router.websocket("/rtc/ws")
        async def uid_rtc_ws(websocket: WebSocket):
            """
            WebRTC signaling over WebSocket (faster trickle ICE).

            Query: room, peer, name, ticket
            Client JSON: {op: signal|leave|ping|hello, ...}
            Server JSON: {type: hello|roster|signal|peer_left|pong|error, ...}
            """
            import asyncio
            import queue as queue_mod

            from ux_channel.realtime.webrtc import (
                _peer_id_ok,
                _sanitize_id,
                allow_rtc_traffic,
                authorize_rtc,
                get_rtc_store,
            )

            live_config = getattr(registry, "config", None) or config
            q = {str(k): str(v) for k, v in websocket.query_params.items()}
            room = q.get("room") or "default"
            peer = q.get("peer") or ""
            name = q.get("name") or ""
            ticket = q.get("ticket") or websocket.headers.get("x-channel-rtc-ticket")

            origin = websocket.headers.get("origin")
            host = websocket.headers.get("host")
            ok, reason = authorize_rtc(
                live_config,
                room,
                ticket=ticket,
                origin=origin,
                host=host,
            )
            peer_s = _sanitize_id(peer)
            if ok and (not peer_s or not _peer_id_ok(peer_s, live_config)):
                ok, reason = False, "invalid peer id"
            if ok:
                try:
                    from ux_channel.security.ratelimit import client_ip_from_scope
                    _ck = client_ip_from_scope(websocket.scope) or ""
                except Exception:
                    _ck = ""
                ok, reason = allow_rtc_traffic(
                    live_config, peer=peer_s or "x", room=room, client_key=_ck, cost=1.0
                )
            if not ok:
                try:
                    from ux_channel.realtime.webrtc_metrics import note_auth_fail, note_ws
                    note_auth_fail()
                    note_ws("deny")
                except Exception:
                    pass
                await websocket.close(code=1008, reason=(reason or "unauthorized")[:120])
                return
            if not peer:
                await websocket.close(code=1008, reason="peer required")
                return

            await websocket.accept()
            try:
                from ux_channel.realtime.webrtc_metrics import note_ws
                note_ws("accept")
            except Exception:
                pass
            store = get_rtc_store(live_config)
            try:
                snap = store.poll(room, peer, name=name, since=0)
            except Exception as exc:
                await websocket.send_json({"type": "error", "error": str(exc)})
                await websocket.close()
                return

            await websocket.send_json(
                {
                    "type": "hello",
                    "room": room,
                    "peer": peer,
                    "peers": snap.get("peers") or [],
                    "signals": snap.get("signals") or [],
                }
            )

            inbox: queue_mod.Queue = queue_mod.Queue(maxsize=256)
            store.subscribe(room, peer, inbox)
            since = 0
            for s in snap.get("signals") or []:
                if isinstance(s, dict) and s.get("id"):
                    since = max(since, int(s["id"]))

            async def pump_in() -> None:
                nonlocal since
                try:
                    while True:
                        raw = await websocket.receive_text()
                        try:
                            body = _serde.loads(raw)
                        except Exception:
                            await websocket.send_json(
                                {"type": "error", "error": "invalid json"}
                            )
                            continue
                        op = (body.get("op") or "").lower()
                        if op == "ping":
                            await websocket.send_json({"type": "pong"})
                            continue
                        if op == "hello" or op == "poll":
                            try:
                                out = store.poll(
                                    room,
                                    peer,
                                    name=name,
                                    since=int(body.get("since") or since),
                                )
                                for s in out.get("signals") or []:
                                    if s.get("id", 0) > since:
                                        since = int(s["id"])
                                    await websocket.send_json(
                                        {
                                            "type": "signal",
                                            "id": s.get("id"),
                                            "from": s.get("from"),
                                            "kind": s.get("kind"),
                                            "payload": s.get("payload"),
                                            "room": room,
                                        }
                                    )
                                await websocket.send_json(
                                    {
                                        "type": "roster",
                                        "peers": out.get("peers") or [],
                                        "room": room,
                                    }
                                )
                            except Exception as exc:
                                await websocket.send_json(
                                    {"type": "error", "error": str(exc)}
                                )
                            continue
                        if op == "leave":
                            store.leave(room, peer)
                            await websocket.close()
                            return
                        if op == "signal":
                            try:
                                out = store.signal(
                                    body.get("room") or room,
                                    from_peer=body.get("from") or peer,
                                    to_peer=body.get("to") or "",
                                    kind=body.get("kind") or "",
                                    payload=body.get("payload"),
                                )
                                if out.get("id"):
                                    since = max(since, int(out["id"]))
                                await websocket.send_json(
                                    {"type": "ack", "id": out.get("id")}
                                )
                            except Exception as exc:
                                await websocket.send_json(
                                    {"type": "error", "error": str(exc)}
                                )
                            continue
                        await websocket.send_json(
                            {"type": "error", "error": "unknown op"}
                        )
                except Exception:
                    return

            async def pump_out() -> None:
                try:
                    while True:
                        try:
                            msg = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: inbox.get(timeout=20.0)
                            )
                        except Exception:
                            # keepalive
                            try:
                                await websocket.send_json({"type": "pong"})
                            except Exception:
                                return
                            # heartbeat poll to refresh presence TTL
                            try:
                                store.poll(room, peer, name=name, since=since)
                            except Exception:
                                pass
                            continue
                        if isinstance(msg, dict) and msg.get("id"):
                            try:
                                since = max(since, int(msg["id"]))
                            except Exception:
                                pass
                        try:
                            await websocket.send_json(msg)
                        except Exception:
                            return
                except Exception:
                    return

            t_in = asyncio.create_task(pump_in())
            t_out = asyncio.create_task(pump_out())
            try:
                done, pending = await asyncio.wait(
                    {t_in, t_out}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
            finally:
                store.unsubscribe(room, peer, inbox)
                try:
                    store.leave(room, peer)
                except Exception:
                    pass


# WebRTC metrics + WHIP/WHEP (optional)
    @router.get("/rtc/metrics")
    async def uid_rtc_metrics():
        """JSON snapshot of WebRTC signaling counters (P1)."""
        from ux_channel.realtime.webrtc_metrics import rtc_metrics

        return JSONResponse(rtc_metrics.snapshot())

    if config is not None and getattr(config, "whip_enabled", False):

        @router.post("/whip/{room}")
        async def uid_whip_publish(room: str, request: Request):
            """
            WHIP-like publish: store SDP offer for room publisher slot.

            Body: raw SDP or JSON {sdp, type}. Returns 201 with answer placeholder
            when a subscriber has posted via /whep; otherwise 202 + Location.
            """
            from ux_channel.realtime.webrtc import get_rtc_store
            from ux_channel.realtime.whip import is_sdp_offer, parse_sdp_body

            live_config = getattr(registry, "config", None) or config
            raw = await request.body()
            ctype = (request.headers.get("content-type") or "").lower()
            if "json" in ctype:
                try:
                    body = decode_http_body(raw or b"{}", content_type=request.headers.get("content-type"))
                    sdp = str(body.get("sdp") or "")
                except Exception:
                    return JSONResponse({"error": "invalid json"}, status_code=400)
            else:
                sdp = parse_sdp_body(raw)
            if not is_sdp_offer(sdp):
                return JSONResponse({"error": "SDP offer required"}, status_code=400)
            store = get_rtc_store(live_config)
            # publisher peer id fixed slot
            pub = "whip-pub"
            sub = "whip-sub"
            try:
                store.poll(room, pub, name="whip-publisher", since=0)
                store.signal(
                    room,
                    from_peer=pub,
                    to_peer=sub,
                    kind="offer",
                    payload={"type": "offer", "sdp": sdp},
                )
            except Exception as exc:
                return JSONResponse({"error": str(exc)}, status_code=409)
            # look for answer in publisher inbox
            inbox = store.poll(room, pub, since=0)
            for s in inbox.get("signals") or []:
                if s.get("kind") == "answer":
                    ans = s.get("payload") or {}
                    body = ans.get("sdp") if isinstance(ans, dict) else str(ans)
                    return Response(
                        content=body or "",
                        status_code=201,
                        media_type="application/sdp",
                        headers={"Location": f"{path}/whip/{room}"},
                    )
            return Response(
                status_code=202,
                headers={"Location": f"{path}/whip/{room}"},
                content=b"",
            )

        @router.post("/whep/{room}")
        async def uid_whep_play(room: str, request: Request):
            """WHEP-like play: consumer posts offer; receives publisher offer as answer path."""
            from ux_channel.realtime.webrtc import get_rtc_store
            from ux_channel.realtime.whip import is_sdp_offer, parse_sdp_body

            live_config = getattr(registry, "config", None) or config
            raw = await request.body()
            sdp = parse_sdp_body(raw)
            store = get_rtc_store(live_config)
            pub, sub = "whip-pub", "whip-sub"
            store.poll(room, sub, name="whip-subscriber", since=0)
            # if publisher offer exists, return it as SDP body (viewer applies as remote)
            inbox = store.poll(room, sub, since=0)
            for s in inbox.get("signals") or []:
                if s.get("kind") == "offer":
                    off = s.get("payload") or {}
                    body = off.get("sdp") if isinstance(off, dict) else str(off)
                    # also store viewer offer for publisher
                    if is_sdp_offer(sdp):
                        store.signal(
                            room,
                            from_peer=sub,
                            to_peer=pub,
                            kind="offer",
                            payload={"type": "offer", "sdp": sdp},
                        )
                    return Response(
                        content=body or "",
                        status_code=201,
                        media_type="application/sdp",
                    )
            return JSONResponse(
                {"error": "no publisher offer yet"},
                status_code=404,
            )

    # SFU token mint (optional) — gated like RTC (origin/ticket/rate)
    @router.post("/sfu/token")
    async def uid_sfu_token(request: Request):
        """Mint external SFU join token when sfu_provider configured."""
        from ux_channel.realtime.sfu import handle_sfu_token

        live_config = getattr(registry, "config", None) or config
        try:
            body = await request.json()
        except Exception:
            body = {}
        ticket = request.query_params.get("ticket") or request.headers.get("x-channel-rtc-ticket")
        origin = request.headers.get("origin")
        host = request.headers.get("host")
        client = request.client.host if request.client else ""
        status, payload = handle_sfu_token(
            live_config,
            body if isinstance(body, dict) else {},
            ticket=ticket or (body.get("ticket") if isinstance(body, dict) else None),
            origin=origin,
            host=host,
            client_key=client or "",
        )
        return JSONResponse(payload, status_code=status)


    app.include_router(router)
    app.mount(
        static_path,
        StaticFiles(directory=str(static_dir())),
        name="ux_channel-static",
    )
    app.state.ux_channel_registry = registry  # type: ignore[attr-defined]
    app.state.ux_channel_config = config  # type: ignore[attr-defined]
    return router


def _status_for(result: Result) -> int:
    from ux_channel.protocol.error_map import ensure_error_meta, http_status_for

    return http_status_for(ensure_error_meta(result))


def _retry_after_header(result: Result, status: int) -> str | None:
    """RFC 7231 Retry-After seconds from Result meta, else default for 429."""
    from ux_channel.transport.backoff import extract_retry_after_s
    from ux_channel.protocol.error_map import ensure_error_meta

    ensure_error_meta(result)
    ra = extract_retry_after_s(result)
    if ra is not None:
        return str(int(max(0, round(ra))))
    if status == 429:
        return "5"
    return None


def _primary_html(result: Result) -> str:
    for op in result.ops:
        if op.get("op") in ("morph", "swap") and "html" in op:
            return str(op["html"])
    if not result.ok and result.error:
        return f"<pre>{result.error.code}: {result.error.message}</pre>"
    return ""
