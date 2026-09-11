"""cek=adapt is compare-only — Channel CapService stays authority."""

from __future__ import annotations

import pytest

from ux_channel.cek.config import cek_available
from ux_channel.host.config import ChannelConfig
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.capability import CapService

SECRET = "adapt-mode-secret-32chars-minimum!!"

pytestmark = pytest.mark.skipif(
    not cek_available(),
    reason="cek-host/cek-surface not importable (required deps)",
)


def test_adapt_mint_uses_classic_cap_service():
    from ux_channel.cek.host_adapter import CekHostCapService, after_cek_cut2

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        cek="adapt",
    )
    reg = ActionRegistry.from_config(cfg)
    assert type(reg._caps) is CapService
    extra = getattr(reg, "_cek_caps", None)
    assert extra is not None
    assert type(extra) is CekHostCapService
    assert extra is not reg._caps
    assert any(fn is after_cek_cut2 for fn in reg.hooks.after)
    token = reg.mint("unused_adapt", {})
    claims = reg._caps.verify(token, "unused_adapt", {})
    assert claims.get("action") == "unused_adapt"
