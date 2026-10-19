"""Strict navigate is same-origin unless the host is allowlisted.

Policy ``off`` keeps today's ``safe_href``: an absolute https URL is
delivered when ``navigate_allowed_hosts`` is empty. Strict refuses a
cross-origin target and the scheme-relative forms ``//x``, ``/\\t/x``,
``\\x01//x``, and ``javascript:``. A relative URL stays. The request
Host (hostname only) is same-origin. A push has no request, so an
absolute URL is allowed only through ``navigate_allowed_hosts``.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.security.security import filter_outbound_ops
from ux_channel.transport.push import PushBus

_SECRET = "strict-nav-secret-32chars-minimum!"
_REFUSED = (
    "//x",
    "/\t/x",
    "\x01//x",
    "javascript:alert(1)",
    "https://evil.test/x",
)


def _ops(href: str, **kwargs: object) -> list:
    return filter_outbound_ops([{"op": "navigate", "href": href}], **kwargs)  # type: ignore[arg-type]


def test_strict_navigate_refuses_cross_origin_and_scheme_relative() -> None:
    for href in _REFUSED:
        ops = _ops(href, policy="strict")
        assert ops[0]["op"] == "noop", href
        blob = json.dumps(ops)
        assert "evil.test" not in blob
        assert "javascript:" not in blob.lower()

    relative = _ops("/rel", policy="strict")
    assert relative[0]["href"] == "/rel"

    listed = _ops(
        "https://cdn.test/a",
        policy="strict",
        allowed_hosts=("cdn.test",),
    )
    assert listed[0]["op"] == "navigate"
    assert listed[0]["href"] == "https://cdn.test/a"

    opened = _ops("https://evil.test/x", policy="off")
    assert opened[0]["op"] == "navigate"
    assert opened[0]["href"] == "https://evil.test/x"


def test_strict_push_without_request_refuses_absolute_navigate() -> None:
    bus = PushBus()
    queue: asyncio.Queue = asyncio.Queue()
    bus.subscribe("nav", queue)
    bus.publish("nav", Result.success({"op": "navigate", "href": "https://evil.test/x"}))
    evil = queue.get_nowait()
    assert evil["ops"][0]["op"] == "noop"
    assert "evil.test" not in json.dumps(evil)
    bus.publish("nav", Result.success({"op": "navigate", "href": "/rel"}))
    kept = queue.get_nowait()
    assert kept["ops"][0]["href"] == "/rel"


class _Request:
    def __init__(self, host: str) -> None:
        self.headers = {"host": host}


def test_strict_dispatch_uses_the_request_host() -> None:
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="strict",
        observe="off",
        allow_memory_stores=True,
    )
    ch = Channel.boot(app, config=cfg)

    @ch.on("Go.there")
    def _go() -> Result:
        return Result.success(
            {"op": "navigate", "href": "https://evil.test/x"},
            {"op": "navigate", "href": "https://app.test/ok"},
            {"op": "navigate", "href": "//x"},
            {"op": "push_url", "href": "/\t/x"},
        )

    ch.registry.bind_request(_Request("app.test"))
    cap = ch.registry.mint("Go.there", {})
    result = ch.registry.dispatch(Intent(action="Go.there", args={}, cap=cap))
    assert result.ok, result.error
    blob = json.dumps(result.to_dict())
    assert "evil.test" not in blob
    assert "javascript:" not in blob.lower()
    hrefs = [op.get("href") for op in result.ops if op.get("op") == "navigate"]
    assert hrefs == ["https://app.test/ok"]
    others = [op for op in result.ops if op.get("op") != "navigate"]
    assert others
    assert all(op.get("op") == "noop" for op in others)
