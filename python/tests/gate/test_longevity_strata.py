"""Longevity strata + core/L4 separation (see LONGEVITY.md)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ux_channel

ROOT = Path(__file__).resolve().parents[3]
MAP = ROOT / "python" / "src" / "ux_channel" / "PACKAGE_MAP.json"


def test_longevity_script_ok():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_longevity.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr or r.stdout


def test_strata_covers_all_packages():
    meta = json.loads(MAP.read_text(encoding="utf-8"))
    strata = meta["strata"]
    for pkg in meta["packages"]:
        assert pkg in strata, pkg
    assert set(meta["core_packages"]) <= set(strata)
    assert set(meta["plane_packages"]) <= set(strata)


def test_root_is_not_a_plane_dump():
    assert "AgentRunner" not in ux_channel.__all__
    assert "MemoryStateStore" not in ux_channel.__all__
    assert not hasattr(ux_channel, "MemoryStateStore")
    assert not hasattr(ux_channel, "AgentRunner")
    # application surface still present
    assert "Channel" in ux_channel.__all__ and "CapService" in ux_channel.__all__


def test_core_packages_listed_L1_L2():
    meta = json.loads(MAP.read_text(encoding="utf-8"))
    for pkg in meta["core_packages"]:
        assert meta["strata"][pkg] in ("L1", "L2")
    for pkg in meta["plane_packages"]:
        assert meta["strata"][pkg] == "L4"


def test_root_import_weight():
    """Importing ux_channel must not load agent runner / devtools.trace / realtime.

    Runs in a subprocess so purging sys.modules cannot poison later tests.
    """
    import subprocess
    import sys
    from textwrap import dedent

    code = dedent(
        """
        import sys
        import ux_channel  # noqa: F401
        heavy = (
            "ux_channel.agent_runtime.runner",
            "ux_channel.agent_runtime.tools",
            "ux_channel.agent_runtime.peer",
            "ux_channel.devtools.trace",
            "ux_channel.devtools.agents_api",
            "ux_channel.wire",
            "ux_channel.protocol.serde",
            "ux_channel.protocol.encode",
            "ux_channel.render.renderers",
            "ux_channel.realtime",
            "ux_channel.mcp",
        )
        bad = [m for m in heavy if m in sys.modules]
        assert not bad, bad
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout
