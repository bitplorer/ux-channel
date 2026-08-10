"""uxchannel bridge DX — scaffold any npm package adapter."""

import tempfile
from pathlib import Path

from ux_channel.bridge.bridge_scaffold import create_bridge_package, explain_bridge, render_adapter_js
from ux_channel.devtools.cli import main
from ux_channel.host.patterns import RECIPE_NAMES, recipe_text


def test_explain():
    text = explain_bridge()
    assert "not FFI" in text or "uxBridge" in text
    assert main(["bridge", "explain"]) == 0


def test_scaffold_adapter_files():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_package(
            td,
            "chartjs",
            methods=("resetZoom",),
            npm_dep="chart.js",
            force=True,
        )
        files = {p.name for p in root.iterdir()}
        assert "package.json" in files
        assert "register.py" in files
        assert any(n.startswith("ux-bridge-") and n.endswith(".js") for n in files)
        js = next(root.glob("ux-bridge-*.js")).read_text()
        assert 'register("chartjs"' in js or 'register("chartjs"' in js.replace(" ", "")
        assert "resetZoom" in js
        reg = (root / "register.py").read_text()
        assert "ch.bridge.register" in reg


def test_recipe_bridge_npm():
    assert "bridge-npm" in RECIPE_NAMES
    code = recipe_text("bridge-npm")
    assert "ch.bridge" in code
    assert main(["bridge", "recipe"]) == 0


def test_cli_bridge_new():
    with tempfile.TemporaryDirectory() as td:
        assert main(["bridge", "new", "leaflet", "--out", td, "--methods", "flyTo", "--force"]) == 0
        assert list(Path(td).rglob("register.py"))


def test_adapter_js_method_dispatch():
    js = render_adapter_js("x", methods=("foo", "bar"))
    assert 'case "foo"' in js
    assert "uxBridge" in js
