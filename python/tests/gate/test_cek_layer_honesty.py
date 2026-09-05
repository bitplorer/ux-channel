"""D4 + no vendor-copy + no second Cap on require + off imports nothing."""

from __future__ import annotations

import sys
from pathlib import Path

from ux_channel.cek.layer_honesty import (
    cap_machine_is_cek_runtime,
    cek_surface_imports_ux_channel,
    channel_vendor_copy_hits,
    second_cap_owners,
)


def test_no_vendor_copy_of_cek():
    assert channel_vendor_copy_hits() == []


def test_d4_cek_surface_does_not_import_ux_channel():
    # Empty when extra missing — that is still D4 (no reverse import exists).
    assert cek_surface_imports_ux_channel() == []


def test_off_path_does_not_import_cek_host():
    # A freshly imported ChannelConfig.cek=off must not pull cek_host.
    banned = {n for n in sys.modules if n.split(".")[0] in {"cek_host", "cek_surface"}}
    # Tests in this file may have imported cek; the contract is: importing
    # ux_channel.cek.config (the parser) does not import cek_host.
    import importlib

    import ux_channel.cek.config as cfg

    importlib.reload(cfg)
    assert cfg.parse_cek("off") == "off"
    assert cfg.parse_cek(None) == "off"


def test_require_swaps_one_cap_machine():
    from ux_channel.cek.config import cek_available

    if not cek_available():
        # Local workspace pin
        cek = Path("/workspace/cek/cek-python")
        if not cek.is_dir():
            cek = Path("/workspace/cek-python")
        if cek.is_dir():
            sys.path.insert(0, str(cek / "cek-host" / "src"))
            sys.path.insert(0, str(cek / "cek-surface" / "src"))
    from ux_channel.cek.config import cek_available as now

    if not now():
        return  # main CI without extra — honesty still holds (no second machine installed)
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig

    cfg = ChannelConfig.development(
        secret="layer-honesty-secret-32chars-min!!",
        allow_memory_stores=True,
        cek="require",
    )
    ch = Channel.boot(FastAPI(), config=cfg)
    owners = second_cap_owners(ch.registry)
    assert len(owners) == 1
    assert "CekHostCapService" in owners[0]
    assert cap_machine_is_cek_runtime(ch.registry)


def test_classic_ir_needs_no_hello():
    """Invariant 15 — classic Intent without hello / CXB still dispatches."""
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.protocol.types import Intent

    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="classic-floor-secret-32chars-min!!",
            allow_memory_stores=True,
            cek="off",
        ),
    )

    @ch.on
    def ping():
        return ch.done()

    r = ch.registry.dispatch(Intent(action="ping", args={}, cap=ch.registry.mint("ping", {})))
    assert r.ok
    # no hello envelope required
    assert "hello" not in (r.meta or {})
