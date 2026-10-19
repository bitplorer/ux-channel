"""Locks for mutants that still survived the outbound filter.

M10b / M28b: a push navigate honors ``navigate_allowed_hosts``.
M18: strict mode drops ``<iframe srcdoc>``; ``iframe`` stays in ``_DROP_CONTENT``.
M19: ``<base href>`` is dropped; ``base`` stays in ``_DROP_TAG``.
M12: the on* check strips the name, so a leading space still refuses it.
"""

from __future__ import annotations

import asyncio
import json

from ux_channel import Result, set_attr
from ux_channel.render.morph_policy import (
    _DROP_CONTENT,
    _DROP_TAG,
    _event_handler,
    strip_dangerous_html,
)
from ux_channel.security.security import _event_or_srcdoc
from ux_channel.transport.push import PushBus


def _publish(bus: PushBus, op: dict) -> dict:
    queue: asyncio.Queue = asyncio.Queue()
    topic = f"mutant.{id(queue)}"
    bus.subscribe(topic, queue)
    bus.publish(topic, Result.success(op))
    return queue.get_nowait()


def test_push_navigate_respects_allowed_hosts() -> None:
    bus = PushBus()
    bus.navigate_allowed_hosts = ("app.test",)
    evil = _publish(bus, {"op": "navigate", "href": "https://evil.test/x"})
    assert evil["ops"][0]["op"] == "noop"
    assert "evil.test" not in json.dumps(evil)
    kept = _publish(bus, {"op": "navigate", "href": "https://app.test/ok"})
    assert kept["ops"][0]["op"] == "navigate"
    assert kept["ops"][0]["href"].startswith("https://app.test/")


def test_strict_drops_iframe_srcdoc() -> None:
    assert "iframe" in _DROP_CONTENT
    out = strip_dangerous_html(
        '<iframe srcdoc="<script>alert(1)</script>"></iframe><b>keep</b>'
    )
    assert "iframe" not in out.lower()
    assert "srcdoc" not in out.lower()
    assert "script" not in out.lower()
    assert "keep" in out


def test_strict_drops_base_href() -> None:
    assert "base" in _DROP_TAG
    out = strip_dangerous_html('<base href="//evil.test/"><b>keep</b>')
    assert "base" not in out.lower()
    assert "evil.test" not in out.lower()
    assert "keep" in out


def test_on_handler_name_strips_a_leading_space() -> None:
    assert _event_handler(" onclick")
    assert _event_or_srcdoc(" onclick")
    op = set_attr("#a", {" onclick": "alert(1)", "class": "keep"})
    assert op["op"] == "noop", op
    assert "alert" not in json.dumps(op).lower()
