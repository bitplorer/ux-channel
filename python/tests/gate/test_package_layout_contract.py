"""Layout contract: PACKAGE_MAP ↔ generated aliases (long-term guard)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_sync_python_layout_check():
    script = ROOT / "scripts" / "sync_python_layout.py"
    r = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_day1_and_cap_rust_parity_surface():
    from ux_channel.day1 import CapService, Channel, Region, RegionBook
    from ux_channel import CapService as Cap2

    assert CapService is Cap2
    svc = CapService("dev-secret-key-32chars-minimum!!!!")
    assert hasattr(svc, "mint") and hasattr(svc, "verify")
    assert not hasattr(svc, "sign")
    assert Region is not RegionBook
    assert "mint" in Channel.day1_names()
