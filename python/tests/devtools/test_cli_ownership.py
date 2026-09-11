"""CLI ownership locks — verbs, doors, and owners. No fashion overlay."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

from ux_channel.devtools.cli import build_parser, main
from ux_channel.devtools.cli_catalog import (
    CLI_VERBS,
    GROUP_ORDER,
    HAPPY_PATH,
    format_epilog,
    owner_of,
    verb_names,
)

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"
SRC = ROOT / "python" / "src" / "ux_channel"

# Frozen public verbs — rename is A8. Add only with an owner + catalog row.
FROZEN_VERBS = (
    "info",
    "check",
    "new",
    "create-app",
    "scaffold-check",
    "doctor",
    "explain",
    "profile",
    "dashboard",
    "dx",
    "templates",
    "recipe",
    "help-topic",
    "bridge",
    "region",
    "upgrade-check",
)


def _registered_verbs() -> set[str]:
    parser = build_parser()
    for action in parser._subparsers._group_actions:  # noqa: SLF001 — inspect argparse
        if getattr(action, "choices", None):
            return set(action.choices)
    raise AssertionError("no subparsers on CLI")


def test_frozen_verbs_match_catalog_and_parser():
    assert set(verb_names()) == set(FROZEN_VERBS)
    assert set(CLI_VERBS) == set(FROZEN_VERBS)
    assert _registered_verbs() == set(FROZEN_VERBS)


def test_help_exits_zero_and_teaches_groups(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for group in GROUP_ORDER:
        assert group in out, group
    for verb in FROZEN_VERBS:
        assert verb in out, verb
    assert "create-app" in out and "doctor" in out
    assert format_epilog().splitlines()[0] in out


def test_no_ux_channel_cli_module():
    """Layout forbids top-level shims. The missing door must stay gone."""
    assert importlib.util.find_spec("ux_channel.cli") is None
    assert not (SRC / "cli.py").exists()
    assert not (SRC / "cli").is_dir()


def test_console_script_and_minus_m_share_devtools_owner():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'uxchannel = "ux_channel.devtools.cli:main"' in text
    assert "ux_channel.cli:" not in text
    from ux_channel.devtools.cli import main as cli_main
    from ux_channel.__main__ import main as dunder_main

    assert cli_main is dunder_main


def test_each_verb_has_one_owner_module():
    for verb in FROZEN_VERBS:
        spec = CLI_VERBS[verb]
        assert spec["group"] in GROUP_ORDER, verb
        owner = owner_of(verb)
        mod = importlib.import_module(owner)
        assert hasattr(mod, "cmd_" + verb.replace("-", "_")), f"{owner} missing cmd for {verb}"


def test_happy_path_is_create_app_and_doctor():
    assert HAPPY_PATH == ("create-app", "doctor")


def test_mapped_optional_packages_exist():
    """enhance/ + ops/ were on disk but invisible to PACKAGE_MAP — now owned."""
    import json

    meta = json.loads((SRC / "PACKAGE_MAP.json").read_text(encoding="utf-8"))
    assert "enhance" in meta["packages"]
    assert "ops" in meta["packages"]
    assert meta["strata"]["enhance"] == "L4"
    assert meta["strata"]["ops"] == "L4"
    assert "enhance" in meta["plane_packages"]
    assert "ops" in meta["plane_packages"]
    assert (SRC / "enhance" / "attach.py").is_file()
    assert (SRC / "ops" / "catalog.py").is_file()
