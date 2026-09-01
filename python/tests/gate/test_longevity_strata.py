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


def test_headless_boot_does_not_load_l4_planes():
    """Channel.boot() without touching media/webrtc/bridge must not import L4.

    Compose's wire/boot headless path depends on this staying cheap.
    Accessing ch.webrtc / ch.media / ch.bridge still attaches (public API).
    """
    import subprocess
    import sys
    from textwrap import dedent

    code = dedent(
        """
        import sys
        from ux_channel import Channel, ChannelConfig, Intent

        ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))

        @ch.on
        def ping():
            return ch.done()

        cap = ch.mint("ping", {})
        result = ch.registry.dispatch(Intent(action="ping", args={}, cap=cap))
        assert result.ok, result

        heavy = (
            "ux_channel.realtime",
            "ux_channel.realtime.webrtc",
            "ux_channel.realtime.media",
            "ux_channel.bridge.bridge_plane",
            "ux_channel.mcp",
            "ux_channel.agent_runtime.runner",
        )
        bad = [m for m in heavy if m in sys.modules]
        assert not bad, bad

        # Public façade still works (lazy attach).
        assert ch.webrtc is not None
        assert "ux_channel.realtime.webrtc" in sys.modules
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


def test_lazy_planes_are_idempotent():
    from ux_channel import Channel, ChannelConfig

    ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))
    a = ch.media
    b = ch.media
    assert a is b
    c = ch.bridge
    d = ch.bridge
    assert c is d
    e = ch.webrtc
    f = ch.webrtc
    assert e is f


def test_compose_frozen_import_paths():
    """ux-compose wire/ may only touch these paths. Do not rename them."""
    from ux_channel import Channel, ChannelConfig
    from ux_channel.cek.host_adapter import apply_host_adapter
    from ux_channel.protocol.types import Intent

    assert Channel is not None and ChannelConfig is not None
    assert callable(apply_host_adapter)
    assert Intent is not None
    assert hasattr(Channel, "boot")
    ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))
    assert hasattr(ch, "mint") and hasattr(ch, "done") and hasattr(ch, "registry")
