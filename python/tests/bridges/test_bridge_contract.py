"""Bridge py/js mapping is string contracts, not function reflection."""

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.protocol.ops import bridge_call


def test_call_requires_package_and_allowlists():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    ch.bridge.register("chartjs", methods=("resetZoom",))
    ops = ch.bridge.call("c1", "resetZoom", package="chartjs")
    d = ops[0]
    assert d["op"] == "bridge.call"
    assert d["method"] == "resetZoom"
    assert d.get("package") == "chartjs"
    with pytest.raises(ValueError, match="not in contract|not allowed|not in sealed"):
        ch.bridge.call("c1", "eval", package="chartjs")
    with pytest.raises(ValueError, match="package is required"):
        ch.bridge.call("c1", "resetZoom", package="")


def test_bridge_call_op_is_json_command_not_callable():
    op = bridge_call("id1", "foo", [1, 2], package="pkg")
    assert op["op"] == "bridge.call"
    assert op["method"] == "foo"
    assert op["args"] == [1, 2]
    assert op.get("package") == "pkg"
    assert isinstance(op["method"], str)
