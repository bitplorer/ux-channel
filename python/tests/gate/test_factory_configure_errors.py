"""create_channel must not swallow production wire/concurrency failures."""

from __future__ import annotations

import logging

import pytest

from ux_channel.host.config import ChannelConfig
from ux_channel.host.factory import create_channel


SECRET = "gate-factory-configure-32chars!!!"


def test_production_invalid_wire_engine_raises(monkeypatch):
    from ux_channel import wire as wire_mod
    from ux_channel.transport import concurrency as conc

    monkeypatch.setattr(conc, "configure_concurrency", lambda **kwargs: None)
    monkeypatch.setattr(
        wire_mod, "configure_wire", lambda **kwargs: (_ for _ in ()).throw(ValueError("bad engine"))
    )

    cfg = ChannelConfig.production(
        SECRET,
        allow_memory_stores=True,
        wire_engine="not-a-real-engine",
        cek="off",
    )
    with pytest.raises(ValueError, match="bad engine"):
        create_channel(config=cfg, app=None, host=None)


def test_development_invalid_wire_engine_logs(monkeypatch, caplog):
    from ux_channel import wire as wire_mod
    from ux_channel.transport import concurrency as conc

    monkeypatch.setattr(conc, "configure_concurrency", lambda **kwargs: None)
    monkeypatch.setattr(
        wire_mod, "configure_wire", lambda **kwargs: (_ for _ in ()).throw(ValueError("bad engine"))
    )

    cfg = ChannelConfig.development(
        SECRET,
        allow_memory_stores=True,
        wire_engine="not-a-real-engine",
        cek="off",
    )
    with caplog.at_level(logging.ERROR, logger="ux_channel.host.factory"):
        reg, _hub = create_channel(config=cfg, app=None, host=None)
    assert reg is not None
    assert any("concurrency/wire configure failed" in r.message for r in caplog.records)
