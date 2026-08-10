"""Extreme usage + pentest corner cases (1.6.0 hardening)."""

from __future__ import annotations

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.testclient import TestClient as StarletteClient

from ux_channel import ActionRegistry, Go, Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.asgi.starlette import mount_channel as mount_starlette
from ux_channel.protocol.capability import CapService
from ux_channel.host.config import ChannelConfig
from ux_channel.protocol.encode import encode_result
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.protocol.ops import navigate, push_url
from ux_channel.security.security import safe_href, sanitize_op_hrefs
from ux_channel.protocol.types import Intent

SECRET = "test-secret-key-32chars-minimum!!"


def test_once_cap_concurrent_single_winner():
    reg = ActionRegistry(secret=SECRET, require_cap=True, nonce_store=MemoryNonceStore())
    hits: list[int] = []

    @reg.action("Once.x")
    def once_x():
        hits.append(1)
        return Result.success(toast("ok"))

    cap = reg.mint("Once.x", {}, once=True)

    def run(_: int) -> bool:
        return reg.dispatch(Intent(action="Once.x", args={}, cap=cap)).ok

    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(run, range(40)))
    assert sum(1 for x in results if x) == 1
    assert len(hits) == 1


def test_malformed_intent_returns_result_not_raise():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    r = reg.dispatch({"v": "1", "args": {}})  # no action
    assert not r.ok
    assert r.error and r.error.code == "bad_request"


def test_async_before_hook_runs_on_sync_dispatch_without_loop():
    """No running event loop → async before-hooks are awaited via asyncio.run."""
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    reg.register("A", lambda: Result.success(toast("a")))
    seen = []

    async def bhook(intent, args):
        seen.append(1)
        return None

    reg.before(bhook)
    r = reg.dispatch(Intent(action="A", args={}))
    assert r.ok
    assert seen == [1]


@pytest.mark.asyncio
async def test_async_before_hook_works_on_dispatch_async():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    reg.register("A", lambda: Result.success(toast("a")))
    seen = []

    async def bhook(intent, args):
        seen.append(1)
        return None

    reg.before(bhook)
    r = await reg.dispatch_async(Intent(action="A", args={}))
    assert r.ok
    assert seen == [1]


def test_go_javascript_encodes_to_failure_not_throw():
    r = encode_result(Go("javascript:alert(1)"))
    assert not r.ok
    assert r.error and "unsafe" in r.error.message


def test_sanitize_protocol_relative_and_js():
    out = sanitize_op_hrefs(
        [navigate("https://ok.example/"), {"op": "navigate", "href": "//evil.com"}]
    )
    # second becomes noop
    assert out[0]["href"] == "https://ok.example/"
    assert out[1]["op"] == "noop"
    assert safe_href("//evil.com") is None
    assert safe_href("\\\\evil") is None


def test_starlette_mount_channel_alias_and_version():
    app = Starlette()
    cfg = ChannelConfig.development(
        secret=SECRET, rate_limit_per_minute=0, enforce_same_origin=False
    )
    reg = ActionRegistry.from_config(cfg)
    mount_starlette(app, reg, config=cfg)
    c = StarletteClient(app)
    v = c.get("/ux-channel/version").json()
    assert v["package"] == "ux-channel"
    assert "version" in v


def test_starlette_client_version_gate():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(
        sec,
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        require_channel_header=True,
        min_client_version="1.5.0",
    )
    app = Starlette()
    reg = ActionRegistry.from_config(cfg)
    reg.register("Ping", lambda: Result.success(toast("p")))
    mount_starlette(app, reg, config=cfg)
    cap = reg.mint("Ping", {})
    r = StarletteClient(app).post(
        "/ux-channel/action",
        json={"v": "1", "action": "Ping", "args": {}, "cap": cap},
        headers={"X-Channel": "1", "X-Channel-Client-Version": "1.0.0"},
    )
    assert r.status_code == 426


def test_runtime_meta_matches_package_version():
    from ux_channel import __version__

    reg = ActionRegistry(secret=SECRET, require_cap=False)
    reg.register("R", lambda: Result.success(toast("r")))
    r = reg.dispatch(Intent(action="R", args={}))
    assert r.meta.get("runtime") == __version__


def test_concurrent_registry_dispatch():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    counter = {"n": 0}
    lock = threading.Lock()

    @reg.action("Inc")
    def inc():
        with lock:
            counter["n"] += 1
        return Result.success(toast("x"))

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda _: reg.dispatch(Intent(action="Inc", args={})), range(100)))
    assert counter["n"] == 100


def test_wide_form_rejected():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    reg.register("F", lambda **kw: Result.success(toast("x")))
    form = {f"k{i}": "v" for i in range(500)}
    r = reg.dispatch(Intent(action="F", args={}, form=form))
    assert not r.ok
    assert r.error.code == "bad_request"


def test_previous_secrets_rotation_roundtrip():
    old, new = SECRET, "new-secret-key-32chars-minimum!!xx"
    reg_old = ActionRegistry(secret=old, require_cap=True)
    reg_old.register("Hi", lambda: Result.success(toast("hi")))
    cap = reg_old.mint("Hi", {})
    reg_new = ActionRegistry(secret=new, require_cap=True, previous_secrets=[old])
    reg_new.register("Hi", lambda: Result.success(toast("hi")))
    assert reg_new.dispatch(Intent(action="Hi", args={}, cap=cap)).ok


def test_once_cap_requires_nonce_store():
    reg = ActionRegistry(secret=SECRET, require_cap=True)  # no nonce store
    reg.register("Pay", lambda: Result.success(toast("x")))
    cap = reg.mint("Pay", {}, once=True)
    r = reg.dispatch(Intent(action="Pay", args={}, cap=cap))
    assert not r.ok
    assert r.error and "nonce" in r.error.message.lower()


def test_push_token_required_when_configured():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ux_channel.asgi.fastapi import mount_channel
    cfg = ChannelConfig.development(
        secret=SECRET,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        push_token="secret-push",
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)
    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    # unauthenticated blocked
    assert c.get("/ux-channel/push/t1").status_code == 401
    # wrong token blocked
    assert c.get("/ux-channel/push/t1", headers={"Authorization": "Bearer wrong"}).status_code == 401
