"""A new channel bus inherits that channel's policy and allowed hosts.

``ensure_registry_push_bus`` used to stamp ``off`` and drop
``navigate_allowed_hosts``. A bus that is already bound is left alone.
"""

from __future__ import annotations

import pytest

from ux_channel.host.config import ChannelConfig
from ux_channel.transport.push import PushBus, ensure_registry_push_bus

_SECRET = "q77b-secret-32chars-minimum!!!"


class _Registry:
    def __init__(self, policy: str) -> None:
        self.config = ChannelConfig.development(
            secret=_SECRET,
            morph_html_policy=policy,
            navigate_allowed_hosts=("cdn.test",),
            observe="off",
            allow_memory_stores=True,
        )


def _registry(policy: str) -> _Registry:
    return _Registry(policy)


def test_new_push_bus_inherits_the_channel_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fresh = PushBus()
    monkeypatch.setattr("ux_channel.transport.push.get_push_bus", lambda: fresh)
    monkeypatch.setattr("ux_channel.transport.push._live_buses", lambda: [])
    bus = ensure_registry_push_bus(_registry("strict"))
    assert bus.outbound_policy() == "strict"
    assert bus.navigate_allowed_hosts == ("cdn.test",)


def test_bound_push_bus_keeps_its_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    bound = PushBus()
    bound.morph_html_policy = "off"
    bound._policy_bound = True
    bound.navigate_allowed_hosts = ("keep.test",)
    monkeypatch.setattr("ux_channel.transport.push.get_push_bus", lambda: bound)
    monkeypatch.setattr("ux_channel.transport.push._live_buses", lambda: [])
    bus = ensure_registry_push_bus(_registry("strict"))
    assert bus.outbound_policy() == "off"
    assert bus.navigate_allowed_hosts == ("keep.test",)
