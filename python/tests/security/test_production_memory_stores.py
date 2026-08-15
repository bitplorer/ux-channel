"""Production factory + doctor refuse silent memory stores."""

from __future__ import annotations

import pytest

from ux_channel import ChannelConfig
from ux_channel.devtools.doctor import production_go_nogo


def test_production_defaults_disallow_memory():
    cfg = ChannelConfig.production("s" * 32)
    assert cfg.allow_memory_stores is False
    assert cfg.max_cap_age == 900


def test_doctor_nogo_on_memory_without_redis():
    cfg = ChannelConfig.production("s" * 32, allow_memory_stores=True)
    report = production_go_nogo(cfg)
    assert report["ok"] is False
    assert any("memory" in x.lower() or "redis" in x.lower() for x in report["no_go"])


def test_doctor_go_with_redis_url():
    cfg = ChannelConfig.production("s" * 32, redis_url="redis://localhost:6379/0")
    report = production_go_nogo(cfg)
    assert report["go"] is True
    assert report["ok"] is True


def test_boot_still_refuses_prod_without_durable_or_opt_in():
    from ux_channel.host.factory import create_channel

    cfg = ChannelConfig.production("s" * 32)
    with pytest.raises(ValueError, match="durable stores"):
        create_channel(config=cfg, app=None, host=None)
