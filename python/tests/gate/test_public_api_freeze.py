"""Frozen application / root public API — renames here are user-visible breaks."""
from __future__ import annotations

import importlib.util

import ux_channel
import ux_channel.api as api


FORBIDDEN_ROOT = {"Think", "Component", "ComponentSet", "toast_message"}

API_REQUIRED = {
    "Channel",
    "ChannelConfig",
    "Region",
    "Intent",
    "Result",
    "CapService",
    "CapError",
    "state",
    "agents",
    "morph",
    "toast",
}


def test_no_deprecated_root_exports():
    for name in FORBIDDEN_ROOT:
        assert name not in ux_channel.__all__
        assert not hasattr(ux_channel, name)


def test_think_module_removed():
    assert importlib.util.find_spec("ux_channel.think") is None


def test_stable_core_on_root():
    for name in (
        "Channel",
        "ActionRegistry",
        "Result",
        "Intent",
        "Region",
        "ChannelConfig",
        "ControlAttrs",
        "http_status_for",
        "CapService",
    ):
        assert name in ux_channel.__all__, name
        assert getattr(ux_channel, name) is not None


def test_api_facade_is_subset_of_root():
    for name in api.__all__:
        assert hasattr(ux_channel, name), name
        assert getattr(api, name) is getattr(ux_channel, name), name


def test_api_has_required_names():
    for name in API_REQUIRED:
        assert name in api.__all__, name


def test_components_not_named_component():
    import ux_channel.components as components

    assert "Component" not in getattr(components, "__all__", ())
    assert not hasattr(components, "Component")
