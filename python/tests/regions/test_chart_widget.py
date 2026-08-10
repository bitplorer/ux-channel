"""ChartBridge factory + commit DX."""

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import ChartBridge, ChartSeries
from ux_channel.paint.placement import Placement


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            require_cap=False,
        ),
    )


def test_factory_then_call():
    ch = _ch()
    charts = ChartBridge(ch)
    assert charts._factory
    rev = charts("revenue", labels=["A", "B"], values=[1, 2], kind="bar")
    assert not rev._factory
    assert rev.id == "revenue"
    assert rev.props()["datasets"][0]["data"] == [1, 2]
    assert isinstance(rev.mount_spec(), Placement)


def test_commit_returns_result():
    ch = _ch()
    rev = ChartBridge(ch)("rev", values=[1], labels=["A"])
    result = rev.commit(values=[9, 8], labels=["X", "Y"])
    assert result.ok is True
    ops = list(result.ops)
    def op_name(o):
        if isinstance(o, dict):
            return o.get("op")
        return getattr(o, "op", None)
    assert any(op_name(o) == "bridge.update" for o in ops)


def test_oneshot_still_works():
    ch = _ch()
    rev = ChartBridge(ch, "rev", labels=["A"], values=[1])
    ops = rev.set_values([2])
    assert ops[0]["op"] == "bridge.update"


def test_factory_methods_require_island():
    ch = _ch()
    charts = ChartBridge(ch)
    try:
        charts.mount_spec()
        assert False, "should raise"
    except TypeError:
        pass


def test_commit_kind():
    ch = _ch()
    rev = ChartBridge(ch)("rev", values=[1], labels=["A"], kind="bar")
    r = rev.commit_kind("line")
    assert r.ok


def test_multi_series():
    ch = _ch()
    rev = ChartBridge(ch)(
        "rev",
        labels=["A", "B"],
        series=[ChartSeries("A", [1, 2]), ChartSeries("B", [3, 4])],
    )
    assert len(rev.props()["datasets"]) == 2


def test_recipe():
    from ux_channel.host.recipes import recipe_text

    text = recipe_text("chart-widget")
    assert "ChartBridge(ch)" in text
    assert "commit" in text


def test_generated_preset_factory():
    import importlib.util
    import tempfile
    from pathlib import Path

    from ux_channel.bridge_meta.bridge_preset_gen import create_bridge_preset

    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "leaflet", force=True)
        spec = importlib.util.spec_from_file_location(
            "leaflet_preset", root / "preset.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        ch = _ch()
        factory = mod.LeafletBridge(ch)
        w = factory("map1", props={"center": [0, 0]})
        assert w.id == "map1"
        r = w.commit(zoom=3)
        assert r.ok
