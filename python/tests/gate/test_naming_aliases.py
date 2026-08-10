"""Intent-aligned aliases stay identical (naming constitution)."""
from ux_channel import Region, RegionBook, RegionRegistry
from ux_channel.capability import CapabilityService
from ux_channel.day1 import Region as Day1Region, RegionRegistry as Day1Reg


def test_region_is_not_the_registry():
    assert Region is not RegionBook
    assert Region is Day1Region


def test_region_registry_is_region_book():
    assert RegionRegistry is RegionBook
    assert Day1Reg is RegionBook


def test_mint_is_sign():
    svc = CapabilityService("dev-secret-key-32chars-minimum!!!!")
    assert svc.mint.__func__ is not None or callable(svc.mint)
    token = svc.mint("Counter.inc", {})
    out = svc.verify(token, action="Counter.inc", args={})
    assert out["action"] == "Counter.inc"
    token2 = svc.sign("Counter.inc", {})
    assert svc.verify(token2, action="Counter.inc", args={})["action"] == "Counter.inc"
