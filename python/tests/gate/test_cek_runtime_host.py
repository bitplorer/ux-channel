"""Cut #2: cek=require Cap machine is cek-runtime Host (not arch HostRuntime).

Skipped when extra [cek] is missing so main CI stays green.
Rust wrap assertions run only when CEK_BIN points at cek-runtime ``cek host-json``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

for _root in (Path("/workspace/cek/cek-python"), Path("/workspace/cek-python")):
    if _root.is_dir():
        sys.path.insert(0, str(_root / "cek-host" / "src"))
        sys.path.insert(0, str(_root / "cek-surface" / "src"))
        break

from ux_channel.cek.config import cek_available
from ux_channel.cek.runtime_host import (
    KERNEL_SSOT,
    KERNEL_SSOT_ADR,
    find_runtime_cek_bin,
    runtime_wrap_available,
)
from ux_channel.protocol.types import Intent

pytestmark = pytest.mark.skipif(not cek_available(), reason="optional extra [cek] not installed")

SECRET = "runtime-host-secret-32chars-min!!"


def _boot(mode: str, **cfg_kw):
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        cek=mode,
        **cfg_kw,
    )
    return Channel.boot(FastAPI(), config=cfg)


def test_require_cap_machine_is_cek_runtime_host():
    ch = _boot("require")
    caps = ch.registry._caps
    assert type(caps).__name__ == "CekHostCapService"
    assert caps.kernel_ssot == KERNEL_SSOT == "cek-runtime"
    assert caps.kernel_ssot_adr == KERNEL_SSOT_ADR
    assert caps.name == "cek-runtime.Host"
    assert caps.backend in ("rust_wrap", "port_host")
    # Documented port Host is the stateful mint/verify machine.
    assert type(caps.host).__name__ == "Host"
    # arch HostRuntime is bootable but is not the Cap machine.
    from ux_channel.arch.host_runtime import HostRuntime

    assert not isinstance(caps, HostRuntime)
    assert not isinstance(caps.host, HostRuntime)


def test_arch_e2e_still_boots_alongside_require():
    from ux_channel.arch import HostConfig, HostRuntime, graph, toast

    ch = _boot("require")
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False),
    )
    host.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"]})
    result = host.emit_from_graph(graph(toast("hi")), session_id="s1")
    assert result["ok"] is True
    # Parallel kernel lives; it is not registry._caps.
    assert ch.registry._caps.kernel_ssot == "cek-runtime"
    assert hasattr(ch, "emit_graph")
    assert hasattr(ch, "set_hello")
    assert hasattr(ch, "grant_stamp")


def test_classic_ir_without_hello_still_dispatches_on_require():
    ch = _boot("require")

    @ch.on
    def ping():
        return ch.done()

    cap = ch.registry.mint("ping", {})
    r = ch.registry.dispatch(Intent(action="ping", args={}, cap=cap))
    assert r.ok
    assert "hello" not in (r.meta or {})


def test_flow_id_becomes_trace_on_require_result():
    ch = _boot("require")

    @ch.on
    def step():
        return ch.done()

    cap = ch.registry.mint("step", {"flow_id": "flow_cut2"})
    r = ch.registry.dispatch(
        Intent(
            action="step",
            args={"flow_id": "flow_cut2"},
            cap=cap,
            meta={"flow_id": "flow_cut2"},
        )
    )
    assert r.ok
    assert r.meta.get("flow_id") == "flow_cut2"
    assert r.meta.get("trace") == "flow_cut2"


def test_hello_binds_profile_manifest_not_cap():
    ch = _boot("require")

    @ch.on
    def ping():
        return ch.done()

    cap = ch.registry.mint("ping", {})
    r = ch.registry.dispatch(
        Intent(
            action="ping",
            args={},
            cap=cap,
            meta={"hello": {"profiles": ["web.v1"], "features": ["seq"]}},
        )
    )
    assert r.ok
    manifest = (r.meta or {}).get("manifest")
    profile = (r.meta or {}).get("profile")
    assert isinstance(manifest, dict)
    assert isinstance(profile, dict)
    assert "cap" not in manifest
    assert "cap" not in profile


def test_effect_graph_refused_without_cap_on_require():
    """EffectGraph is L7 after Cap — not L1, not a Cap substitute."""
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.arch.effects import graph, toast

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=False,
        cek="require",
    )
    ch = Channel.boot(FastAPI(), config=cfg)

    @ch.registry.action("paint")
    def paint():
        return {"ok": True, "_graph": graph(toast("no-cap"))}

    r = ch.registry.dispatch(Intent(action="paint", args={}))
    assert r.ok is False
    assert r.error is not None
    assert "L7" in (r.error.message or "") or "after Cap" in (r.error.message or "")
    assert r.ops == []


def test_effect_graph_projects_after_cap_on_require():
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.arch.effects import graph, toast

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        cek="require",
    )
    ch = Channel.boot(FastAPI(), config=cfg)

    @ch.registry.action("paint")
    def paint():
        return {"ok": True, "_graph": graph(toast("capped"))}

    cap = ch.registry.mint("paint", {})
    r = ch.registry.dispatch(Intent(action="paint", args={}, cap=cap))
    assert r.ok
    assert any(o.get("op") == "toast" for o in r.ops)
    assert "_graph" not in (r.meta or {})


def test_python_cek_cli_is_not_runtime_bin():
    """cek-host's console script is not cek-runtime host-json."""
    fake = Path(os.environ.get("HOME", "/tmp")) / ".local/bin/cek"
    if fake.is_file():
        text = fake.read_text(encoding="utf-8")
        if "cek_host.cli" in text:
            # Probe must reject this path even if it is named ``cek``.
            from ux_channel.cek.runtime_host import is_runtime_cek_bin

            assert is_runtime_cek_bin(str(fake)) is False


@pytest.mark.skipif(not runtime_wrap_available(), reason="CEK_BIN / cek-runtime host-json not bound")
def test_require_uses_rust_host_kernel_when_runtime_bin_present():
    ch = _boot("require")
    caps = ch.registry._caps
    assert caps.backend == "rust_wrap"
    assert caps.runtime_kernel is not None
    assert type(caps.runtime_kernel).__name__ == "RustHostKernel"
    # Reachability: mint through host-json (Cap object, not Channel token).
    raw = caps.runtime_kernel.mint("kv.write", once=False)
    assert isinstance(raw, dict)
    assert raw.get("action") == "kv.write"
    assert find_runtime_cek_bin()
