"""Advanced stage tests: plugins, bridge helpers, SSE formatting."""

from ux_channel import Result, create_channel
from ux_channel.bridge_meta.bridge_api import (
    mount_html,
    mount_ops,
    register_simple_manifest,
    update_ops,
)
from ux_channel.bridge_meta.plugins import BridgeManifest, PluginHub, set_hub
from ux_channel.paint.render import ChainRenderer, StringRenderer
from ux_channel.transport.stream import ResultStream, format_sse, iter_result_sse
from ux_channel.protocol.types import Intent


def test_bridge_manifest_validation():
    hub = PluginHub()
    set_hub(hub)
    hub.add_bridge_manifest(
        BridgeManifest(package="sparkline", methods=("update", "destroy"), events=())
    )
    hub.validate_bridge_call("sparkline", "update")
    try:
        hub.validate_bridge_call("sparkline", "nope")
        assert False, "expected error"
    except Exception:
        pass


def test_mount_html_and_ops():
    html = mount_html(
        "c1", package="sparkline", props={"values": [1, 2]}, class_name="x"
    )
    assert "data-channel-bridge-id=\"c1\"" in html
    assert "sparkline" in html
    ops = mount_ops("c1", "sparkline", props={"values": [1]})
    assert ops[0]["op"] == "bridge.mount"
    ops2 = update_ops("c1", {"values": [3]})
    assert ops2[0]["op"] == "bridge.update"
    m = register_simple_manifest("sparkline", methods=["update"])
    assert m.package == "sparkline"


def test_sse_format():
    r = Result.success()
    stream = ResultStream()
    chunk = stream.chunk(r, done=True)
    s = format_sse(chunk)
    if isinstance(s, (bytes, bytearray)):
        s = s.decode("utf-8")
    assert "data:" in s
    parts = list(iter_result_sse([r]))
    assert parts
