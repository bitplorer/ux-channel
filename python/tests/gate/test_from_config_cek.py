"""from_config is the Cap door — same machine as Channel.boot."""

from __future__ import annotations

import pytest

from ux_channel.cek.config import cek_available
from ux_channel.host.config import ChannelConfig
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.capability import CapService
from ux_channel.protocol.types import Intent

SECRET = "from-config-cek-secret-32chars-min!!"

pytestmark = pytest.mark.skipif(
    not cek_available(),
    reason="cek-host/cek-surface not importable (required deps)",
)


def test_from_config_applies_cek_require():
    from ux_channel.cek.host_adapter import after_cek_cut2
    from ux_channel.cek.layer_honesty import cap_machine_is_cek_runtime, second_cap_owners

    cfg = ChannelConfig.development(secret=SECRET, allow_memory_stores=True)
    assert cfg.cek == "require"
    reg = ActionRegistry.from_config(cfg)
    assert type(reg._caps).__name__ == "CekHostCapService"
    assert cap_machine_is_cek_runtime(reg)
    owners = second_cap_owners(reg)
    assert len(owners) == 1
    assert any(fn is after_cek_cut2 for fn in reg.hooks.after)


def test_from_config_off_keeps_classic_capservice():
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        cek="off",
    )
    reg = ActionRegistry.from_config(cfg)
    assert type(reg._caps) is CapService


def test_effect_graph_refused_without_cap_from_config():
    from ux_channel.cek.effects import graph, toast

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=False,
        cek="require",
    )
    reg = ActionRegistry.from_config(cfg)

    @reg.action("paint")
    def paint():
        return {"ok": True, "_graph": graph(toast("no-cap"))}

    r = reg.dispatch(Intent(action="paint", args={}))
    assert r.ok is False
    assert r.error is not None
    assert "L7" in (r.error.message or "") or "after Cap" in (r.error.message or "")
    assert r.ops == []


def test_effect_graph_projects_after_cap_from_config():
    from ux_channel.cek.effects import graph, toast

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        cek="require",
    )
    reg = ActionRegistry.from_config(cfg)

    @reg.action("paint")
    def paint():
        return {"ok": True, "_graph": graph(toast("capped"))}

    cap = reg.mint("paint", {})
    r = reg.dispatch(Intent(action="paint", args={}, cap=cap))
    assert r.ok
    assert any(o.get("op") == "toast" for o in r.ops)
    assert "_graph" not in (r.meta or {})
