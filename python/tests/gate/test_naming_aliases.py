"""Rust-parity names for shared surface; host types stay distinct."""
from ux_channel import CapError, CapService, Region, RegionBook
from ux_channel.day1 import CapService as Day1Cap, Region as Day1Region


def test_cap_service_rust_parity_names():
    assert CapService is Day1Cap
    svc = CapService("dev-secret-key-32chars-minimum!!!!")
    assert hasattr(svc, "mint") and hasattr(svc, "verify")
    assert hasattr(CapService, "hash_args")
    assert not hasattr(svc, "sign")  # no dual — mint only
    token = svc.mint("Counter.inc", {})
    assert svc.verify(token, action="Counter.inc", args={})["action"] == "Counter.inc"
    h = CapService.hash_args({"sku": "abc-123", "qty": 2})
    assert h == "96e4f83e3793b646323a67f314b51044"


def test_cap_error_name():
    assert issubclass(CapError, Exception)


def test_region_host_only_names():
    """Region / RegionBook are host-only; not renamed for Rust (Rust has no twin)."""
    assert Region is Day1Region
    assert Region is not RegionBook
