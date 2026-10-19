"""The same strict navigate and swap rules on FastAPI, Starlette, and asgi-core."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.testclient import TestClient as StarletteClient

from ux_channel import Channel, ChannelConfig, Result
from ux_channel.asgi.core import handle_action_asgi
from ux_channel.asgi.starlette import mount_channel_starlette
from ux_channel.host.registry import ActionRegistry

_SECRET = "review-hosts-secret-32chars-min!"
_TRICK = "https://evil.test\\@app.test/"
_STYLE = "<svg><style>.x{color:red}</style><rect></rect></svg>"


def _config() -> ChannelConfig:
    return ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="strict",
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
        navigate_allowed_hosts=("cdn.test",),
    )


def _registry() -> ActionRegistry:
    reg = ActionRegistry(secret=_SECRET, require_cap=False)
    reg.config = _config()

    @reg.action("Go.there")
    def _go(href: str = "/ok") -> Result:
        return Result.success({"op": "navigate", "href": href})

    @reg.action("Show.html")
    def _show() -> Result:
        return Result.success({"op": "swap", "target": "#t", "html": _STYLE})

    return reg


def _post_fastapi(href: str) -> dict:
    app = FastAPI()
    cfg = _config()
    ch = Channel.boot(app, config=cfg)

    @ch.on("Go.there")
    def _go(href: str = "/ok") -> Result:
        return Result.success({"op": "navigate", "href": href})

    client = TestClient(app, base_url="http://app.test")
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Go.there", "args": {"href": href}},
        headers={"Host": "app.test"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _post_starlette(href: str) -> dict:
    app = Starlette()
    reg = _registry()
    mount_channel_starlette(app, reg, config=reg.config)
    client = StarletteClient(app, base_url="http://app.test")
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Go.there", "args": {"href": href}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _post_asgi(href: str) -> dict:
    reg = _registry()

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await handle_action_asgi(scope, receive, send, reg, config=reg.config)

    client = StarletteClient(app, base_url="http://app.test")
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Go.there", "args": {"href": href}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _op(body: dict) -> dict:
    return body["ops"][0]


def test_three_hosts_refuse_the_open_redirect_and_keep_same_origin() -> None:
    for name, post in (
        ("fastapi", _post_fastapi),
        ("starlette", _post_starlette),
        ("asgi", _post_asgi),
    ):
        trick = _op(post(_TRICK))
        assert trick["op"] == "noop", name + " " + json.dumps(trick)
        assert "evil.test" not in json.dumps(trick)
        same = _op(post("https://app.test/ok"))
        assert same["op"] == "navigate", name
        assert same["href"] == "https://app.test/ok"
        relative = _op(post("/ok"))
        assert relative["href"] == "/ok", name


def test_three_hosts_drop_svg_style() -> None:
    for name, poster in (
        ("fastapi", _post_style_fastapi),
        ("starlette", _post_style_starlette),
        ("asgi", _post_style_asgi),
    ):
        html = poster()
        assert "<style" not in html.lower(), name + " " + html
        assert "<rect" in html.lower(), name


def _post_style_fastapi() -> str:
    app = FastAPI()
    ch = Channel.boot(app, config=_config())

    @ch.on("Show.html")
    def _show() -> Result:
        return Result.success({"op": "swap", "target": "#t", "html": _STYLE})

    response = TestClient(app).post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["ops"][0]["html"]


def _post_style_starlette() -> str:
    app = Starlette()
    reg = _registry()
    mount_channel_starlette(app, reg, config=reg.config)
    response = StarletteClient(app).post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["ops"][0]["html"]


def _post_style_asgi() -> str:
    reg = _registry()

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await handle_action_asgi(scope, receive, send, reg, config=reg.config)

    response = StarletteClient(app).post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["ops"][0]["html"]
