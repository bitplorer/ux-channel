"""Push HTML policy lives on each channel's bus, not on the process.

A second boot must not relax the first channel. A bare bus with no
policy attribute is strict. A channel with no policy is off.
``strict `` (with the trailing space) is not a known value and raises when
the config is validated.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Result, swap
from ux_channel.transport.push import PushBus, get_push_bus, set_push_bus

_SECRET = "push-policy-per-channel-32chars!!"
_HTML = '<img src="x" onerror="alert(1)">'
_topic_seq = 0


def _boot(policy: str | None = "off", hosts: tuple[str, ...] = ()) -> PushBus:
    app = FastAPI()
    kwargs: dict[str, object] = {
        "secret": _SECRET,
        "observe": "off",
        "allow_memory_stores": True,
        "navigate_allowed_hosts": hosts,
    }
    if policy is not None:
        kwargs["morph_html_policy"] = policy
    cfg = ChannelConfig.development(**kwargs)  # type: ignore[arg-type]
    ch = Channel.boot(app, config=cfg)
    bus = ch.registry.push_bus
    assert isinstance(bus, PushBus)
    return bus


def _publish(bus: PushBus, op: dict) -> dict:
    global _topic_seq
    _topic_seq += 1
    queue: asyncio.Queue = asyncio.Queue()
    topic = f"probe.{id(bus)}.{_topic_seq}"
    bus.subscribe(topic, queue)
    assert bus.publish(topic, Result.success(op)) == 1
    return queue.get_nowait()


def test_two_channels_keep_their_own_push_policies() -> None:
    bus_a = _boot("strict", ("app.test",))
    bus_b = _boot("off")
    assert bus_a is not bus_b

    strict_swap = _publish(bus_a, swap("#t", _HTML))
    assert "onerror" not in json.dumps(strict_swap).lower()
    evil = _publish(bus_a, {"op": "navigate", "href": "https://evil.test/x"})
    assert evil["ops"][0]["op"] == "noop"
    allowed = _publish(bus_a, {"op": "navigate", "href": "https://app.test/ok"})
    assert allowed["ops"][0]["op"] == "navigate"
    assert allowed["ops"][0]["href"].startswith("https://app.test/")

    open_swap = _publish(bus_b, swap("#t", _HTML))
    assert "onerror" in open_swap["ops"][0]["html"].lower()

    # A later default boot must not open the first channel.
    _boot("off")
    again = _publish(bus_a, swap("#t", _HTML))
    assert "onerror" not in json.dumps(again).lower()
    evil_again = _publish(bus_a, {"op": "navigate", "href": "https://evil.test/x"})
    assert evil_again["ops"][0]["op"] == "noop"
    still_open = _publish(bus_b, swap("#t", _HTML))
    assert "onerror" in still_open["ops"][0]["html"].lower()


def test_set_push_bus_after_boot_keeps_that_channels_policy() -> None:
    _boot("strict", ("app.test",))
    set_push_bus(PushBus())
    bus = get_push_bus()
    body = _publish(bus, swap("#t", _HTML))
    assert "onerror" not in json.dumps(body).lower()
    evil = _publish(bus, {"op": "navigate", "href": "https://evil.test/x"})
    assert evil["ops"][0]["op"] == "noop"
    allowed = _publish(bus, {"op": "navigate", "href": "https://app.test/ok"})
    assert allowed["ops"][0]["href"].startswith("https://app.test/")


def test_missing_push_policy_is_strict() -> None:
    bus = PushBus()
    if hasattr(bus, "morph_html_policy"):
        del bus.morph_html_policy
    body = _publish(bus, swap("#t", _HTML))
    assert "onerror" not in json.dumps(body).lower()


def test_unknown_morph_policy_raises_at_config_time() -> None:
    with pytest.raises(ValueError):
        ChannelConfig.development(
            secret=_SECRET,
            morph_html_policy="strict ",
            observe="off",
        )
