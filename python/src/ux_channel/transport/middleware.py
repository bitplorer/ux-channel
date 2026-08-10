"""
ASGI middleware helpers for production Developer tooling (request IDs, optional client version).

Modular: does not depend on FastAPI at import time.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Optional


class RequestIdMiddleware:
    """
    Ensure every request has ``X-Request-Id`` (propagate or generate).

    Usage (Starlette/FastAPI)::

        app.add_middleware(RequestIdMiddleware)
    """

    header = b"x-request-id"

    def __init__(self, app: Any, *, header_name: str = "x-request-id"):
        self.app = app
        self.header_name = header_name.lower().encode("latin-1")

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_id = None
        for k, v in scope.get("headers") or []:
            if k == self.header_name:
                req_id = v.decode("latin-1", "ignore")
                break
        if not req_id:
            req_id = "req_" + uuid.uuid4().hex[:16]
            # inject into scope headers for downstream
            headers = list(scope.get("headers") or [])
            headers.append((self.header_name, req_id.encode("latin-1")))
            scope = dict(scope)
            scope["headers"] = headers

        scope.setdefault("state", {})
        if not isinstance(scope.get("state"), dict):
            # Starlette may use a State object later; store on scope key
            pass
        scope["uid_request_id"] = req_id

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((self.header_name, req_id.encode("latin-1")))
                message = dict(message)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


def check_client_version(
    client_version: Optional[str],
    *,
    min_version: str = "1.0.0",
) -> Optional[str]:
    """
    Return error message if client runtime is too old, else None.

    Loose semver major.minor.patch compare (numeric parts only).
    """
    if not client_version:
        return None

    def parts(v: str) -> tuple[int, int, int]:
        segs = []
        for p in v.strip().split(".")[:3]:
            try:
                segs.append(int("".join(c for c in p if c.isdigit()) or "0"))
            except ValueError:
                segs.append(0)
        while len(segs) < 3:
            segs.append(0)
        return segs[0], segs[1], segs[2]

    if parts(client_version) < parts(min_version):
        return f"client runtime {client_version} < minimum {min_version}"
    return None
