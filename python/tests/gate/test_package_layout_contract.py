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
    for name in ("paint", "ops_dx", "bridge_meta", "public_api", "zones", "security_plane"):
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


def test_wire_and_asgi_surfaces():
    from ux_channel.wire import MEDIA_TYPES, encode, decode, encode_cxb, is_cxb
    from ux_channel.asgi import mount_channel

    assert MEDIA_TYPES and encode and decode and encode_cxb and is_cxb
    assert callable(mount_channel)


def test_api_is_subset_of_root_identity():
    import ux_channel as u
    import ux_channel.api as api

    for name in api.__all__:
        if name.startswith("_"):
            continue
        assert hasattr(u, name), name
        assert getattr(api, name) is getattr(u, name), name


def test_rust_parity_cap_names():
    from ux_channel.protocol.capability import CapService, CapError
    assert hasattr(CapService, "mint")
    assert hasattr(CapService, "verify")
    assert hasattr(CapService, "hash_args")
    assert not hasattr(CapService, "sign")
    assert CapError is not None


def test_public_api_constants_named_consistently():
    from ux_channel.host.channel import CHANNEL_PUBLIC_API, WEBRTC_PUBLIC_API
    assert "boot" in CHANNEL_PUBLIC_API and "mint" in CHANNEL_PUBLIC_API
    assert "plugin" in WEBRTC_PUBLIC_API


def test_public_api_freeze_doc_names():
    """Root freeze doc must describe mint (not sign) and current packages."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    text = (root / "PUBLIC_API_FREEZE.md").read_text(encoding="utf-8")
    assert "CapService.mint" in text or "mint" in text
    assert "CapService.sign" not in text
    assert "host.stores" in text or "MemoryStateStore" in text
    assert "day1" not in text.lower() or "forbidden" in text.lower()


def test_product_package_imports():
    import ux_channel.agent_runtime  # noqa: F401
    import ux_channel.mcp  # noqa: F401
    import ux_channel.workplace  # noqa: F401
    import ux_channel.components  # noqa: F401
    import ux_channel.scaffold  # noqa: F401
    from ux_channel.redis_extra import RedisStateStore  # may exist
    assert RedisStateStore


def test_agent_runtime_kernel_surface():
    from ux_channel.agent_runtime import (
        AgentPeer,
        AgentPolicy,
        AgentRunner,
        AgentSession,
        dispatch_peer,
    )
    from ux_channel import agents
    import types
    import ux_channel.agent_runtime as ar

    assert all((AgentRunner, AgentPolicy, AgentSession, AgentPeer, dispatch_peer))
    assert callable(agents) and isinstance(ar, types.ModuleType)
    assert not callable(ar)
