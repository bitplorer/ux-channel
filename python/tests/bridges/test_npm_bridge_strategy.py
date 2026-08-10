"""npm bridge strategy — bridging still first-class; packages registry."""

from pathlib import Path

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridge_meta.bridge_api import mount_html, mount_ops
from ux_channel.paint.demo import mount_html as demo_host
from ux_channel.paint.placement import Placement


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )


def test_bridge_pipeline_end_to_end_data():
    ch = _ch()
    ch.bridge.register("chartjs", methods=("update", "destroy"))
    assert "chartjs" in ch.bridge.packages()
    spec = ch.bridge.mount_spec("c1", package="chartjs", props={"type": "bar"})
    assert isinstance(spec, Placement)
    assert spec.attrs["data-channel-bridge-package"] == "chartjs"
    ops = ch.bridge.mount_ops("c1", "chartjs", props={"type": "bar"})
    assert ops and (getattr(ops[0], "op", None) or ops[0].get("op")) in (
        "bridge.mount",
        None,
    ) or True
    # ops are bridge.mount
    op0 = ops[0]
    opname = getattr(op0, "op", None) or (op0.get("op") if isinstance(op0, dict) else None)
    if opname is None and hasattr(op0, "type"):
        opname = op0.type
    # Op dataclass uses .op field via to_dict
    d = op0.to_dict() if hasattr(op0, "to_dict") else dict(op0)
    assert d.get("op") == "bridge.mount"
    assert d.get("package") == "chartjs"


def test_runtime_includes_uid_bridge():
    ch = _ch()
    srcs = [s.src for s in ch.runtime(bridge=True).scripts]
    assert any("ux-bridge.js" in s for s in srcs)


def test_demo_can_still_render_host_html():
    ch = _ch()
    spec = ch.bridge.mount_spec("x", package="chartjs")
    html = demo_host(spec)
    assert "data-channel-bridge-id" in html and "chartjs" in html


def test_legacy_mount_html_still_in_bridge_api():
    html = mount_html("x", package="chartjs", props={})
    assert "data-channel-bridge-package" in html


def test_npm_docs_and_workspace_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs" / "bridges" / "NPM.md").is_file()
    assert (root / "package.json").is_file()
    assert (root / "packages" / "@ux-channel" / "bridge-core" / "package.json").is_file()
