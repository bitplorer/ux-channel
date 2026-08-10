"""Deepening: sealed bridge.call, redis/memory intent log, uid inject."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent
from ux_channel.bridge.bridge_protocol import (
    BridgeFirewallError,
    get_sealed_registry,
    reset_sealed_registry,
)
from ux_channel.devtools.intent_log import attach_intent_log
from ux_channel_ux_dom import inject_uids


SECRET = "deep-foundation-secret-key-32b!!"


@pytest.fixture(autouse=True)
def _clean_sealed():
    reset_sealed_registry()
    yield
    reset_sealed_registry()


def test_bridge_call_sealed_firewall():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )
    ch.bridge.register("chart.js", methods=("update", "destroy"), events=("select",))
    # sealed protocol auto-registered
    ch.bridge.call("c1", "update", [], package="chart.js")
    with pytest.raises(BridgeFirewallError):
        ch.bridge.call("c1", "eval", [], package="chart.js")


def test_intent_log_attach():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )
    log = attach_intent_log(ch)

    @ch.on
    def ping():
        return ch.done(notice="ok")

    ch.registry.dispatch(Intent(action="ping", args={}, cap=ch.mint("ping", {})))
    assert len(log) >= 1


def test_inject_uids_glue():
    tree = {"tag": "div", "children": [{"tag": "span", "children": []}]}
    annotated, slots = inject_uids(tree, prefix="page")
    assert annotated is not None
