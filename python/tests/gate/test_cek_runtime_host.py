"""Cut #4/#5: Cap machine is cek-runtime Host; once consume is Host-only on require.

Skipped when wrap packages are missing so a bare tree can still collect.
Rust wrap reachability runs only when CEK_BIN points at cek-runtime ``cek host-json``.
"""

from __future__ import annotations

import importlib.util
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


def test_arch_package_is_gone():
    """No ux_channel.arch import — Cap machine is not a parallel kernel."""
    assert importlib.util.find_spec("ux_channel.arch") is None
    with pytest.raises(ImportError):
        import ux_channel.arch  # noqa: F401


def test_require_cap_machine_is_cek_runtime_host():
    ch = _boot("require")
    caps = ch.registry._caps
    assert type(caps).__name__ == "CekHostCapService"
    assert caps.kernel_ssot == KERNEL_SSOT == "cek-runtime"
    assert caps.kernel_ssot_adr == KERNEL_SSOT_ADR
    assert caps.name == "cek-runtime.Host"
    assert caps.backend in ("rust_wrap", "port_host")
    assert type(caps.host).__name__ == "Host"
    assert caps.runtime_kernel is None
    assert "arch" not in type(caps).__module__
    assert "arch" not in type(caps.host).__module__
    assert not hasattr(ch, "emit_graph")
    assert not hasattr(ch, "set_hello")
    assert not hasattr(ch, "grant_stamp")


def test_default_boot_cap_authority_is_cek_runtime_host():
    """Channel.boot default decide is the cek-runtime Host façade (ADR 0010/0011)."""
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig

    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
    )
    assert cfg.cek == "require"
    ch = Channel.boot(FastAPI(), config=cfg)
    caps = ch.registry._caps
    assert type(caps).__name__ == "CekHostCapService"
    assert caps.kernel_ssot == "cek-runtime"
    assert caps.name == "cek-runtime.Host"
    assert type(caps.host).__name__ == "Host"
    assert caps.runtime_kernel is None


def test_factory_fallback_default_require():
    from ux_channel.host.factory import create_channel

    reg, _hub = create_channel(
        secret=SECRET,
        environment="development",
        app=None,
        host=None,
    )
    assert type(reg._caps).__name__ == "CekHostCapService"
    assert reg._caps.kernel_ssot == "cek-runtime"
    assert reg._caps.runtime_kernel is None


def test_single_mint_verify_owner():
    from ux_channel.cek.host_adapter import CekHostCapService
    from ux_channel.cek.runtime_host import bind_runtime_host

    bind = bind_runtime_host(SECRET)
    assert type(bind.host).__name__ == "Host"
    assert bind.runtime_kernel is None
    assert bind.kernel_ssot == "cek-runtime"
    caps = CekHostCapService(SECRET)
    assert caps.host is not None
    assert caps.runtime_kernel is None
    tok = caps.mint("Cart.add", {"sku": "x"})
    assert caps.verify(tok, "Cart.add", {"sku": "x"})


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
    from ux_channel.cek.effects import graph, toast

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
    from ux_channel.cek.effects import graph, toast

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
            from ux_channel.cek.runtime_host import is_runtime_cek_bin

            assert is_runtime_cek_bin(str(fake)) is False


def test_require_once_is_host_owned_channel_store_unused():
    """cek=require: Host consumes once; Channel MemoryNonceStore is never called."""
    from ux_channel.host.nonce import MemoryNonceStore

    class ProbeStore(MemoryNonceStore):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, float]] = []

        def use_once(self, key: str, *, ttl_s: float = 3600) -> bool:
            self.calls.append((key, ttl_s))
            return super().use_once(key, ttl_s=ttl_s)

    probe = ProbeStore()
    ch = _boot("require")
    ch.registry.nonce_store = probe

    @ch.on
    def pay():
        return ch.done()

    cap = ch.registry.mint("pay", {}, once=True)
    r = ch.registry.dispatch(Intent(action="pay", args={}, cap=cap))
    assert r.ok
    assert probe.calls == []

    replay = ch.registry.dispatch(Intent(action="pay", args={}, cap=cap))
    assert replay.ok is False
    assert replay.error is not None
    assert probe.calls == []

    ch.registry._nonce_store = None
    assert ch.diagnose()["once_jti_enforced"] is True


@pytest.mark.skipif(not runtime_wrap_available(), reason="CEK_BIN / cek-runtime host-json not bound")
def test_require_records_rust_wrap_reachability_without_second_mint():
    ch = _boot("require")
    caps = ch.registry._caps
    assert caps.backend == "rust_wrap"
    assert caps.bin_path
    assert find_runtime_cek_bin()
    assert caps.runtime_kernel is None
    tok = caps.mint("Cart.add", {"sku": "x"})
    assert caps.verify(tok, "Cart.add", {"sku": "x"})


PREVIOUS = "old-secret-key-32chars-minimum!!xx"
ROTATION_NEW = "new-secret-key-32chars-minimum!!xx"


def test_require_previous_secrets_refuses_loudly():
    """cek=require + previous_secrets must not silently drop rotation (cut #5D).

    cek-host 0.1.3 Host/CapService has no HMAC previous_secrets API. Channel
    must refuse rather than store-and-ignore (no second Cap machine).
    """
    from ux_channel.cek.host_adapter import CekHostCapService
    from ux_channel.cek.runtime_host import (
        PREVIOUS_SECRETS_REQUIRE_MSG,
        bind_runtime_host,
    )
    from ux_channel.host.config import ChannelConfig
    from ux_channel.host.factory import create_channel

    with pytest.raises((ValueError, RuntimeError), match="previous_secrets"):
        ChannelConfig.development(
            secret=ROTATION_NEW,
            allow_memory_stores=True,
            require_cap=True,
            cek="require",
            previous_secrets=(PREVIOUS,),
        )

    with pytest.raises(RuntimeError, match="previous_secrets"):
        bind_runtime_host(ROTATION_NEW, previous_secrets=[PREVIOUS])

    with pytest.raises(RuntimeError, match="previous_secrets"):
        CekHostCapService(ROTATION_NEW, previous_secrets=[PREVIOUS])

    with pytest.raises((ValueError, RuntimeError), match="previous_secrets"):
        create_channel(
            secret=ROTATION_NEW,
            environment="development",
            app=None,
            host=None,
            previous_secrets=[PREVIOUS],
        )

    assert "HMAC previous_secrets" in PREVIOUS_SECRETS_REQUIRE_MSG


def test_require_diagnose_does_not_claim_rotation():
    """Hello/diagnose must not imply previous_secrets verify under require."""
    ch = _boot("require")
    d = ch.diagnose()
    rot = d["previous_secrets"]
    assert rot["wired"] is False
    assert rot["verify"] == "unwired"
    assert "cek=off" in rot["note"] or "classic CapService" in rot["note"]
    assert PREVIOUS not in str(d)
    doc = ch.doctor()
    assert any("previous_secrets" in h or "rotation" in h for h in doc["hints"])


def test_classic_off_previous_secrets_still_rotates():
    """Classic cek=off rotation stays on Channel CapService (unchanged law)."""
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.protocol.capability import CapService
    from ux_channel.protocol.types import Intent

    old_cfg = ChannelConfig.development(
        secret=PREVIOUS,
        allow_memory_stores=True,
        require_cap=True,
        cek="off",
    )
    old = Channel.boot(FastAPI(), config=old_cfg)

    @old.on
    def hi():
        return old.done()

    cap = old.registry.mint("hi", {})

    new_cfg = ChannelConfig.development(
        secret=ROTATION_NEW,
        allow_memory_stores=True,
        require_cap=True,
        cek="off",
        previous_secrets=(PREVIOUS,),
    )
    ch = Channel.boot(FastAPI(), config=new_cfg)
    assert type(ch.registry._caps) is CapService
    ch.registry.replace("hi", hi)
    r = ch.registry.dispatch(Intent(action="hi", args={}, cap=cap))
    assert r.ok
    d = ch.diagnose()
    assert d["previous_secrets"]["wired"] is True
    assert d["previous_secrets"]["verify"] == "classic CapService"
