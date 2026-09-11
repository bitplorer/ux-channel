"""Region file DX is L5 scaffold, not L2 host. Public verb stays ``region``."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from ux_channel.devtools.cli import main as cli_main
from ux_channel.devtools.log import get_log


def test_region_cli_module_is_scaffold_not_host():
    assert importlib.util.find_spec("ux_channel.host.region_cli") is None
    spec = importlib.util.find_spec("ux_channel.scaffold.region_cli")
    assert spec is not None and spec.origin
    from ux_channel.scaffold.region_cli import cmd_region

    assert callable(cmd_region)


def test_dispatcher_imports_scaffold_region_cli():
    """One argv dispatcher; body lives with the library owner (compose pattern)."""
    cli = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "devtools" / "cli.py"
    text = cli.read_text(encoding="utf-8")
    assert "from ux_channel.scaffold.region_cli import cmd_region" in text
    assert "from ux_channel.host.region_cli import" not in text
    assert 'sub.add_parser(\n        "region"' in text or '"region"' in text


def test_public_region_verb_still_dispatches(tmp_path, capsys):
    """Frozen verb name + dests (region_action, --recipe, --out)."""
    out = tmp_path / "regions"
    assert cli_main(["region", "add", "pay/desk", "--recipe", "payment", "--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert "pay/desk" in captured.out or "pay.desk" in captured.out
    assert (out / "pay" / "desk.py").exists()
    assert cli_main(["region", "recipes"]) == 0


def test_scaffold_cmd_region_add(tmp_path):
    from ux_channel.scaffold.region_cli import cmd_region

    out = tmp_path / "regions"
    args = SimpleNamespace(
        region_action="add",
        path="pay/desk",
        recipe="payment",
        out=str(out),
        uid=None,
        force=False,
        strict=False,
    )
    assert cmd_region(args, get_log=get_log) == 0
    text = (out / "pay" / "desk.py").read_text(encoding="utf-8")
    assert "pay_order" in text
    assert 'uid = "pay.desk"' in text
