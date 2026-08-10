"""Public API surface — no deprecated exports."""

from __future__ import annotations

import ux_channel
import ux_channel.components as components


FORBIDDEN = {
    "Think",
    "Component",
    "ComponentSet",
    "toast_message",
}


def test_package_has_no_deprecated_exports():
    for name in ("Think", "Component", "ComponentSet"):
        assert name not in ux_channel.__all__, name
        assert not hasattr(ux_channel, name), name


def test_components_has_no_deprecated_exports():
    for name in ("Component", "ComponentSet", "Think"):
        assert name not in components.__all__
        assert not hasattr(components, name)


def test_think_module_removed():
    import importlib.util

    assert importlib.util.find_spec("ux_channel.think") is None


def test_channel_and_component_describe():
    from ux_channel import Channel
    from ux_channel.components import Counter
    from ux_channel.host.config import ChannelConfig

    ch = Channel.boot(
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!", rate_limit_per_minute=0
        )
    )
    c = Counter(ch, uid="D:root").install()
    d = c.describe()
    assert d["uid"] == "D:root" and d["installed"] is True
    assert "ChannelComponent" in d["mro"]


def test_stable_core_exports_present():
    for name in (
        "Channel",
        "ActionRegistry",
        "Result",
        "Intent",
        "Region",
        "ChannelConfig",
        "ControlAttrs",
        "http_status_for",
    ):
        assert name in ux_channel.__all__, name
    # optional layers live in submodules (not root)
    import ux_channel.components as comps
    assert hasattr(comps, "Counter") or hasattr(comps, "Badge")
