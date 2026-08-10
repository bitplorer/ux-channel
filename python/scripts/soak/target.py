"""
Target adapters: inline TestClient, live HTTP, optional spawn.

Design: scenarios only see get/post/mint_ticket/close (+ optional .app/.channel).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any


class _Resp:
    """Normalize Starlette/httpx response to .status_code / .json()."""

    def __init__(self, r: Any) -> None:
        self._r = r
        self.status_code = getattr(r, "status_code", 0)

    def json(self) -> Any:
        return self._r.json()

    @property
    def text(self) -> str:
        return getattr(self._r, "text", "") or ""


@dataclass
class InlineTarget:
    """In-process FastAPI via Starlette TestClient."""

    app: Any
    channel: Any
    _client: Any

    @classmethod
    def create(cls, **app_kwargs: Any) -> "InlineTarget":
        from starlette.testclient import TestClient

        from scripts.soak.app_factory import build_soak_app

        app, ch = build_soak_app(**app_kwargs)
        client = TestClient(app)
        return cls(app=app, channel=ch, _client=client)

    def get(self, path: str, **kwargs: Any) -> _Resp:
        params = kwargs.pop("params", None)
        headers = kwargs.pop("headers", None)
        return _Resp(self._client.get(path, params=params, headers=headers))

    def post(self, path: str, **kwargs: Any) -> _Resp:
        json_body = kwargs.pop("json", None)
        headers = kwargs.pop("headers", None)
        content = kwargs.pop("content", None)
        return _Resp(
            self._client.post(
                path, json=json_body, headers=headers, content=content
            )
        )

    def mint_ticket(self, room: str, sub: str = "") -> str:
        return self.channel.webrtc.sign_ticket(room, sub=sub)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


@dataclass
class HttpTarget:
    """Live base URL (staging / multi-worker)."""

    base_url: str
    secret: str
    _client: Any

    @classmethod
    def create(cls, base_url: str, secret: str | None = None) -> "HttpTarget":
        import httpx

        secret = secret or os.environ.get(
            "SOAK_SECRET", "soak-test-secret-key-32chars-min!!"
        )
        base = base_url.rstrip("/")
        return cls(
            base_url=base,
            secret=secret,
            _client=httpx.Client(base_url=base, timeout=30.0),
        )

    def get(self, path: str, **kwargs: Any) -> _Resp:
        return _Resp(self._client.get(path, **kwargs))

    def post(self, path: str, **kwargs: Any) -> _Resp:
        return _Resp(self._client.post(path, **kwargs))

    def mint_ticket(self, room: str, sub: str = "") -> str:
        from ux_channel.config import ChannelConfig
        from ux_channel.webrtc import sign_rtc_ticket

        cfg = ChannelConfig.development(
            secret=self.secret, allow_memory_stores=True
        )
        return sign_rtc_ticket(cfg, room, sub=sub)

    def close(self) -> None:
        self._client.close()


@dataclass
class SpawnTarget:
    """Spawn local uvicorn; clients speak HTTP."""

    http: HttpTarget
    procs: list = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        workers: int = 1,
        port: int = 8765,
        secret: str | None = None,
        redis_url: str | None = None,
    ) -> "SpawnTarget":
        secret = secret or os.environ.get(
            "SOAK_SECRET", "soak-test-secret-key-32chars-min!!"
        )
        redis_url = redis_url or os.environ.get("REDIS_URL")
        env = os.environ.copy()
        env["SOAK_SECRET"] = secret
        if redis_url:
            env["REDIS_URL"] = redis_url
        env["PYTHONPATH"] = (
            env.get("PYTHONPATH", "")
            + os.pathsep
            + str(__import__("pathlib").Path(__file__).resolve().parents[2])
            + os.pathsep
            + str(
                __import__("pathlib").Path(__file__).resolve().parents[2] / "src"
            )
        )
        code = (
            "import uvicorn\n"
            "from scripts.soak.app_factory import build_soak_app\n"
            f"app,_=build_soak_app(secret={secret!r}, redis_url={redis_url!r})\n"
            f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='warning')\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            env=env,
            cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        )
        http = HttpTarget.create(f"http://127.0.0.1:{port}", secret=secret)
        deadline = time.time() + 20
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = http.get("/health")
                if r.status_code == 200:
                    return cls(http=http, procs=[proc])
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(0.25)
        proc.terminate()
        raise RuntimeError(f"spawn target failed to boot: {last_err}")

    def get(self, path: str, **kwargs: Any) -> _Resp:
        return self.http.get(path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> _Resp:
        return self.http.post(path, **kwargs)

    def mint_ticket(self, room: str, sub: str = "") -> str:
        return self.http.mint_ticket(room, sub=sub)

    def close(self) -> None:
        self.http.close()
        for p in self.procs:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
