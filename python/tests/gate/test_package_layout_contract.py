"""Layout contract: cohesive packages only — no top-level shims."""
from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "python" / "src" / "ux_channel"


def test_sync_python_layout_check():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_python_layout.py"), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_top_level_implementation_modules():
    allowed = {"__init__.py", "__main__.py", "_version.py"}
    extras = [p.name for p in PKG.glob("*.py") if p.name not in allowed]
    assert extras == [], f"top-level modules forbidden (no shims): {extras}"


def test_public_paths():
    from ux_channel.api import CapService, Channel, Region, RegionBook
    from ux_channel.host.regions import RegionBook as RB
    from ux_channel.protocol.capability import CapService as CS

    assert RegionBook is RB
    assert CapService is CS
    svc = CapService("dev-secret-key-32chars-minimum!!!!")
    assert hasattr(svc, "mint") and not hasattr(svc, "sign")
    assert "mint" in Channel.public_api_names()
    assert Region is not RegionBook


def test_package_public_api():
    """Cohesive packages expose primary symbols without deep paths."""
    from ux_channel.api import Channel as C2
    from ux_channel.host import Channel, Region, RegionBook
    from ux_channel.protocol import CapService, Intent, Result, morph

    assert Channel is C2
    assert callable(morph)
    svc = CapService("dev-secret-key-32chars-minimum!!!!")
    assert svc.mint("T", {})


def test_no_legacy_package_dirs():
    root = Path(__import__("ux_channel").__file__).resolve().parent
    for name in ("paint", "ops_dx", "bridge_meta", "day1", "zones", "security_plane"):
        assert not (root / name).exists(), name


def test_cohesive_package_exports():
    from ux_channel import foundations, host, protocol, render, security
    from ux_channel.foundations import Quantity
    from ux_channel.host import Channel, Region
    from ux_channel.protocol import CapService, Intent, morph
    from ux_channel.render import morph_ir
    from ux_channel.security import intent_headers, safe_href

    assert Channel and Region and CapService and Intent and morph
    assert morph_ir and intent_headers and Quantity and safe_href


def test_state_api_vs_stores_module():
    """stores = MemoryStateStore…; state() = application API on state_api / root."""
    from ux_channel import state as root_state
    from ux_channel.host import stores as stores_mod
    from ux_channel.host.state_api import state as api_state
    from ux_channel.host.stores import MemoryStateStore

    assert isinstance(stores_mod, types.ModuleType)
    assert root_state is api_state
    assert callable(root_state)
    assert MemoryStateStore is stores_mod.MemoryStateStore


def test_root_identity_with_packages():
    import ux_channel as u
    from ux_channel.devtools import attach_audit
    from ux_channel.host import Channel
    from ux_channel.protocol import CapService, morph
    from ux_channel.render import esc

    assert u.Channel is Channel
    assert u.CapService is CapService
    assert u.morph is morph
    assert u.attach_audit is attach_audit
    assert u.esc is esc
