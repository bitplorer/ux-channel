"""Layout contract: cohesive packages only — no top-level shims."""
from __future__ import annotations

import subprocess
import sys
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
    from ux_channel.protocol import CapService, Intent, Result, morph
    from ux_channel.host import Channel, Region, RegionBook
    from ux_channel.api import Channel as C2

    assert Channel is C2
    assert callable(morph)
    svc = CapService("dev-secret-key-32chars-minimum!!!!")
    assert svc.mint("T", {})
