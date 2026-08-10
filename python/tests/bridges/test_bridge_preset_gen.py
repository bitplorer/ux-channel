"""Automated bridge preset generation — importable packages."""

import json
import tempfile
from pathlib import Path

from ux_channel.bridge_preset_gen import (
    create_bridge_preset,
    list_known_presets,
    write_bridges_index,
)
from ux_channel.cli import main
from ux_channel.scaffold import ScaffoldOptions, create_app


def test_catalog_has_chartjs():
    keys = {r["key"] for r in list_known_presets()}
    assert "chartjs" in keys


def test_preset_importable_package_layout():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "chartjs", force=True)
        assert root.name == "chartjs"
        assert (root / "preset.py").is_file()
        assert (root / "__init__.py").is_file()
        assert (root / "contract.json").is_file()
        assert (root / "PRESET.json").is_file()
        assert list(root.glob("ux-bridge-*.js"))
        meta = json.loads((root / "PRESET.json").read_text())
        assert meta["import"] == "from bridges.chartjs import ChartJsBridge"
        assert "class ChartJsBridge" in (root / "preset.py").read_text()
        # parent index
        assert (Path(td) / "__init__.py").is_file() or write_bridges_index(Path(td))


def test_cli_new_aliases_preset():
    with tempfile.TemporaryDirectory() as td:
        assert main(["bridge", "new", "leaflet", "--out", td, "--force"]) == 0
        assert (Path(td) / "leaflet" / "preset.py").is_file()


def test_cli_catalog():
    assert main(["bridge", "catalog"]) == 0


def test_create_app_with_bridge_importable():
    with tempfile.TemporaryDirectory() as td:
        root = create_app(
            ScaffoldOptions(
                app_name="demo",
                dest=Path(td) / "demo",
                template="minimal",
                bridges=["chartjs"],
                force=True,
            )
        )
        assert (root / "bridges" / "chartjs" / "preset.py").is_file()
        assert (root / "bridges" / "__init__.py").is_file()
        idx = (root / "bridges" / "__init__.py").read_text()
        assert "ChartJsBridge" in idx
        assert list((root / "app" / "static" / "bridges").glob("ux-bridge-*.js"))


def test_help_bridge():
    from ux_channel import Channel

    text = Channel.help("bridge")
    assert "preset" in text.lower()


def test_codegen_default_is_factory_facade():
    """preset.py always teaches Class(ch) then call + commit."""
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "chartjs", force=True)
        code = (root / "preset.py").read_text()
        assert "def __call__" in code
        assert "def commit" in code
        assert "_factory" in code
        assert "commit_mount" in code
        reg = (root / "register.py").read_text()
        assert "widgets =" in reg or "factory" in reg.lower()
        readme = (root / "README.md").read_text()
        assert "commit" in readme
