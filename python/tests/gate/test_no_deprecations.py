"""Lock: removed shims stay removed and docs stop teaching them (chore/remove-deprecations)."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("mod", ["ux_channel.region_component", "ux_channel.regions"])
def test_root_shim_modules_absent(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_channel_has_no_deprecated_html_helpers():
    from ux_channel.host.channel import Channel

    assert not hasattr(Channel, "button")
    assert not hasattr(Channel, "page")


@pytest.mark.parametrize(
    "rel, stale",
    [
        ("python/docs/dx/DX.md", "DeprecationWarning (still work)"),
        ("TERMINOLOGY.md", "(shim: `ux_channel.region_component`)"),
        ("TERMINOLOGY.md", "(shim: `ux_channel.regions`)"),
        ("python/ONTOLOGY.md", "legacy shims"),
        ("NAMING.md", "Packages + shims"),
    ],
)
def test_docs_do_not_teach_removed_shims(rel, stale):
    assert stale not in (REPO / rel).read_text(encoding="utf-8")
