"""A (cek=off) ≡ B (cek=require) — same Intent → same Result ops.

Skipped when extra [cek] is not installed so main CI stays green.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

for _root in (Path("/workspace/cek/cek-python"), Path("/workspace/cek-python")):
    if _root.is_dir():
        sys.path.insert(0, str(_root / "cek-host" / "src"))
        sys.path.insert(0, str(_root / "cek-surface" / "src"))
        break

from ux_channel.cek.config import cek_available
from ux_channel.cek.host_adapter import ORACLE_ARGS, ORACLE_HASH, CekHostCapService
from ux_channel.protocol.capability import CapError, CapService
from ux_channel.protocol.types import Intent

pytestmark = pytest.mark.skipif(
    not cek_available(),
    reason="cek-host/cek-surface not importable (required deps)",
)

SECRET = "parity-secret-key-32chars-minimum!!"


def _ops(result) -> list[dict]:
    raw = result.ops if hasattr(result, "ops") else result.get("ops") or []
    out = []
    for op in raw:
        if hasattr(op, "to_dict"):
            d = op.to_dict()
        elif isinstance(op, dict):
            d = dict(op)
        else:
            continue
        d.pop("trace", None)
        out.append(d)
    return out


def test_oracle_hash_agrees():
    assert CapService.hash_args(ORACLE_ARGS) == ORACLE_HASH
    assert CekHostCapService(SECRET).hash_args(ORACLE_ARGS) == ORACLE_HASH


def test_cek_host_is_012():
    import cek_host

    parts = tuple(int(x) for x in cek_host.__version__.split(".")[:3])
    assert parts >= (0, 1, 3)
    b = CekHostCapService(SECRET)
    assert type(b.host).__name__ == "Host"
    assert b.kernel_ssot == "cek-runtime"
    assert b.name == "cek-runtime.Host"
    assert b.backend in ("rust_wrap", "port_host")


def test_mint_verify_roundtrip_both_machines():
    a = CapService(SECRET)
    b = CekHostCapService(SECRET)
    args = {"sku": "abc-123", "qty": 2}
    ta = a.mint("Cart.add", args)
    tb = b.mint("Cart.add", args)
    assert a.verify(ta, "Cart.add", args)
    assert b.verify(tb, "Cart.add", args)


def test_different_action_or_args_fails_both():
    a = CapService(SECRET)
    b = CekHostCapService(SECRET)
    args = {"sku": "abc-123", "qty": 2}
    ta = a.mint("Cart.add", args)
    tb = b.mint("Cart.add", args)
    with pytest.raises(CapError):
        a.verify(ta, "Cart.remove", args)
    with pytest.raises(CapError):
        b.verify(tb, "Cart.remove", args)
    with pytest.raises(CapError):
        a.verify(ta, "Cart.add", {"sku": "abc-123", "qty": 3})
    with pytest.raises(CapError):
        b.verify(tb, "Cart.add", {"sku": "abc-123", "qty": 3})


def test_once_replay_fails_closed_both():
    a = CapService(SECRET)
    from ux_channel.host.nonce import MemoryNonceStore

    a.nonce_store = MemoryNonceStore()
    b = CekHostCapService(SECRET)
    args = {"sku": "x"}
    ta = a.mint("Pay.once", args, once=True)
    tb = b.mint("Pay.once", args, once=True)
    a.verify(ta, "Pay.once", args)
    b.verify(tb, "Pay.once", args)
    with pytest.raises(CapError):
        a.verify(ta, "Pay.once", args)
    with pytest.raises(CapError):
        b.verify(tb, "Pay.once", args)


def test_bogus_present_cap_fails_closed_both():
    a = CapService(SECRET)
    b = CekHostCapService(SECRET)
    with pytest.raises(CapError):
        a.verify("not-a-cap", "Cart.add", {})
    with pytest.raises(CapError):
        b.verify("not-a-cap", "Cart.add", {})


def test_dispatch_ops_parity_off_vs_require():
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig

    def _boot(mode: str):
        app = FastAPI()
        cfg = ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=True,
            cek=mode,
        )
        ch = Channel.boot(app, config=cfg)

        @ch.on
        def ping():
            return ch.done()

        return ch

    a = _boot("off")
    b = _boot("require")
    ia = Intent(action="ping", args={}, cap=a.registry.mint("ping", {}))
    ib = Intent(action="ping", args={}, cap=b.registry.mint("ping", {}))
    ra = a.registry.dispatch(ia)
    rb = b.registry.dispatch(ib)
    assert ra.ok and rb.ok
    assert _ops(ra) == _ops(rb)


def test_classic_channel_ops_are_not_catalog():
    """toast and navigate stay Channel wire. Only morph is in the declared catalog."""
    from cek_host.catalog import in_catalog
    from ux_channel.cek.project import to_catalog

    classic = [
        {"op": "morph", "target": "shell", "html": "<b>hi</b>"},
        {"op": "toast", "text": "ok"},
        {"op": "navigate", "path": "/x"},
    ]
    catalog = to_catalog(classic)
    assert len(catalog) == 1
    assert catalog[0]["ns"] == "ui.dom" and catalog[0]["name"] == "morph"
    assert in_catalog("ui.dom", "morph")
    assert not in_catalog("nav", "navigate")
    assert not in_catalog("ui", "toast")


def test_project_catalog_missing_stamp_honors_strict(monkeypatch):
    """No stamp is the default catalog. Strict is Baseline only, not the whole catalog."""
    from cek_host.catalog import BASELINE_PAIRS, UndeclaredPair

    from ux_channel.cek.project import project_catalog

    ops = [
        {"op": "morph", "target": "shell", "html": "<b>hi</b>"},
        {"op": "toast", "text": "ok"},
    ]
    monkeypatch.delenv("CEK_CATALOG_MODE", raising=False)
    out = project_catalog(ops)
    assert len(out) == 1
    assert out[0]["ns"] == "ui.dom" and out[0]["name"] == "morph"
    assert out[0]["payload"]["target"] == "shell"
    assert out[0]["payload"]["patch"]["html"] == "<b>hi</b>"

    monkeypatch.setenv("CEK_CATALOG_MODE", "strict")
    with pytest.raises(UndeclaredPair):
        project_catalog(ops)

    monkeypatch.delenv("CEK_CATALOG_MODE", raising=False)
    with pytest.raises(UndeclaredPair):
        project_catalog(ops, stamp=BASELINE_PAIRS)
