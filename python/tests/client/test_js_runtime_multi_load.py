"""Source + contract tests for multi-JS load behaviour."""

from __future__ import annotations

from pathlib import Path

STATIC = Path("src/ux_channel/static")


def test_channel_and_bridge_are_idempotent():
    ch = (STATIC / "ux-channel.js").read_text()
    br = (STATIC / "ux-bridge.js").read_text()
    assert "__UX_CHANNEL_RUNTIME_LOADED__" in ch
    assert "already loaded" in ch
    assert "already loaded" in br
    assert "function scanBridges" in ch
    assert "setTimeout(scanBridges" in ch


def test_adapters_rescan_after_register():
    fx = (STATIC / "adapters/ux-fx.js").read_text()
    ui = (STATIC / "adapters/ux-ui.js").read_text()
    assert "uxBridge.scan" in fx
    assert "uxBridge.scan" in ui
    assert "uxBridge missing" in fx


def test_min_matches_channel():
    a = (STATIC / "ux-channel.js").read_text()
    b = (STATIC / "ux-channel.min.js").read_text()
    assert a == b  # currently identical ship; keep in sync


def test_arch_ops_and_peer_hello_in_js():
    ch = (STATIC / "ux-channel.js").read_text()
    assert 'case "seq":' in ch
    assert 'case "timer.set":' in ch
    assert 'case "timer.clear":' in ch
    assert 'case "invoke":' in ch
    assert "function peerHello" in ch
    assert "peerHello: peerHello" in ch


def test_peer_kernel_has_no_dom():
    kernel = (STATIC / "ux-peer-kernel.js").read_text()
    assert "createPeerKernel" in kernel
    assert "function safeHref" in kernel
    assert "document." not in kernel
    assert "window." not in kernel
    assert "innerHTML" not in kernel
    assert "querySelector" not in kernel
    assert 'op === "seq"' in kernel or 'op.op === "seq"' in kernel
    assert "timer.set" in kernel
    assert "invoke" in kernel


def test_demo_scripts_order_mentions_bridge_before_adapters():
    from ux_channel.render.kit import bridge_script_tags, demo_scripts
    from ux_channel import Channel, ChannelConfig
    from fastapi import FastAPI

    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="js-runtime-order-secret-key-32b!!!!",
            allow_memory_stores=True,
        ),
    )
    html = demo_scripts(ch) + bridge_script_tags(fx=True, ui=True)
    i_ch = html.find("ux-channel.js")
    i_br = html.find("ux-bridge.js")
    i_fx = html.find("ux-fx.js")
    assert 0 <= i_ch < i_br or i_br < 0  # channel before bridge when both present
    if i_br >= 0 and i_fx >= 0:
        assert i_br < i_fx


def test_client_runtime_doors():
    ch = (STATIC / "ux-channel.js").read_text()
    assert "function registerOp" in ch
    assert "registerOp: registerOp" in ch
    assert "store: signals" in ch
    assert "CORE_OPS" in ch
    assert "channel:beforeOp" in ch
    assert "channel:afterOp" in ch
    assert "channel:unknownOp" in ch
    assert "registerOp refused core op" in ch
    assert "data-channel-restore-focus" in ch
    assert "data-channel-hydrate-store" in ch
    # existing core cases stay in the switch — doors do not delete them
    assert 'case "morph":' in ch
    assert 'case "signal.set":' in ch
