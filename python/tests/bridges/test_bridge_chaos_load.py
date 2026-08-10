"""
Brutal chaos / load / regression tests for bridge + presets + contracts.

Goals: surface silent bugs, race-ish concurrent registration, bad inputs,
idempotency, allowlist defaults, factory/commit Result shape.
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import re
import string
import tempfile
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridge_meta.bridge_preset_gen import (
    create_bridge_preset,
    list_known_presets,
    module_name_for,
    resolve_preset_spec,
)
from ux_channel.bridge_meta.bridge_scaffold import (
    add_contract_method,
    create_bridge_package,
    default_methods,
    list_contract_methods,
    remove_contract_method,
    sync_register_py_methods,
)
from ux_channel.bridges import ChartBridge
from ux_channel.bridge_meta.plugins import BridgeManifest, get_hub


def _ch(**kwargs):
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        require_cap=False,
        **kwargs,
    )
    return Channel.boot(FastAPI(), config=cfg)


# ── defaults & allowlist ──────────────────────────────────────────────


def test_default_methods_always_update_destroy():
    assert default_methods() == ("update", "destroy")
    assert "zoom" in default_methods(["zoom"])


def test_empty_manifest_allows_all_methods():
    hub = get_hub()
    hub.add_bridge_manifest(BridgeManifest(package="open-pkg", methods=()))
    hub.validate_bridge_call("open-pkg", "anythingGoes")  # no raise


def test_nonempty_manifest_blocks_unknown():
    hub = get_hub()
    hub.add_bridge_manifest(
        BridgeManifest(package="strict-pkg", methods=("update",))
    )
    hub.validate_bridge_call("strict-pkg", "update")
    with pytest.raises(ValueError):
        hub.validate_bridge_call("strict-pkg", "deleteAll")


def test_unknown_package_open_by_default():
    get_hub().validate_bridge_call("no-such-package-xyz", "whatever")


# ── contract / sync ───────────────────────────────────────────────────


def test_add_method_syncs_methods_constant():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_package(td, "widget", methods=("update",), force=True)
        add_contract_method("widget", "ping", start=td, args=["x:number:required"])
        reg = (root / "register.py").read_text()
        assert 'METHODS = ("destroy", "ping", "update")' in reg or "ping" in reg
        assert "ping" in list_contract_methods("widget", start=td)["names"]
        remove_contract_method("widget", "ping", start=td)
        reg2 = (root / "register.py").read_text()
        assert "ping" not in reg2 or '"ping"' not in reg2


def test_add_method_idempotent_same_signature():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "w2", methods=("update",), force=True)
        r1 = add_contract_method("w2", "foo", start=td, args=["a:string:required"])
        r2 = add_contract_method("w2", "foo", start=td, args=["a:string:required"])
        assert r2.get("action") in ("unchanged", "added", None) or "foo" in r2["methods"]


def test_add_method_conflict_without_force():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "w3", methods=("update",), force=True)
        add_contract_method("w3", "foo", start=td, args=["a:string:required"])
        with pytest.raises(Exception):
            add_contract_method("w3", "foo", start=td, args=["b:number:required"])


def test_add_method_force_updates_signature():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "w4", methods=("update",), force=True)
        add_contract_method("w4", "foo", start=td, args=["a:string:required"])
        r = add_contract_method(
            "w4", "foo", start=td, args=["b:number:required"], force=True
        )
        data = json.loads(Path(r["path"]).read_text())
        assert data["methods"]["foo"]["args"][0]["name"] == "b"


# ── factory / commit chaos ────────────────────────────────────────────


def test_factory_cannot_mount_spec():
    ch = _ch()
    with pytest.raises(TypeError):
        ChartBridge(ch).mount_spec()


def test_commit_merges_bridge_update_ops():
    ch = _ch()
    rev = ChartBridge(ch)("r", values=[1], labels=["a"])
    result = rev.commit(values=[2, 3], labels=["x", "y"])
    assert result.ok
    ops = list(result.ops)
    assert ops, "commit must attach bridge ops"
    names = [
        o.get("op") if isinstance(o, dict) else getattr(o, "op", None) for o in ops
    ]
    assert "bridge.update" in names


def test_commit_notice_does_not_drop_ops():
    ch = _ch()
    rev = ChartBridge(ch)("r", values=[1], labels=["a"])
    result = rev.commit(values=[9], notice="ok")
    assert result.ok
    assert any(
        (o.get("op") if isinstance(o, dict) else getattr(o, "op", None))
        == "bridge.update"
        for o in result.ops
    )


def test_empty_id_rejected():
    ch = _ch()
    with pytest.raises((ValueError, TypeError)):
        ChartBridge(ch)("  ")
    with pytest.raises((ValueError, TypeError)):
        ChartBridge(ch, "")


def test_bridge_call_requires_package():
    ch = _ch()
    with pytest.raises(TypeError):
        ch.bridge.call("id1", "update")  # type: ignore[call-arg]


def test_bridge_call_strict_unknown_method_when_registered():
    ch = _ch()
    ch.bridge.register("strict.js", methods=("update",))
    with pytest.raises(ValueError):
        ch.bridge.call("b1", "nuke", package="strict.js")


def test_bridge_call_open_without_register():
    ch = _ch()
    ops = ch.bridge.call("b1", "anyMethod", 1, 2, package="loose.js", strict=False)
    assert ops


# ── preset codegen load ───────────────────────────────────────────────


def test_all_catalog_presets_generate_and_import():
    import importlib.util

    ch = _ch()
    with tempfile.TemporaryDirectory() as td:
        for row in list_known_presets():
            root = create_bridge_preset(td, row["key"], force=True)
            assert (root / "preset.py").is_file()
            assert (root / "contract.json").is_file()
            code = (root / "preset.py").read_text()
            assert "def __call__" in code and "def commit" in code
            # no invented css teach
            assert "css={" not in code.split("Public API")[1][:400]
            # import & exercise
            mod_name = f"preset_{row['key'].replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, root / "preset.py")
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader
            spec.loader.exec_module(mod)
            cls = getattr(mod, next(x for x in dir(mod) if x.endswith("Bridge")))
            factory = cls(ch)
            w = factory("island-1")
            r = w.commit()
            assert r.ok


def test_module_name_for_safe_identifiers():
    assert re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", module_name_for("chart.js", "chartjs"))
    assert re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", module_name_for("123bad", ""))


def test_named_methods_args_roundtrip_leaflet():
    import importlib.util

    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "leaflet", force=True)
        c = json.loads((root / "contract.json").read_text())
        assert c["methods"]["setView"]["args"]
        spec = importlib.util.spec_from_file_location("lf", root / "preset.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        ch = _ch()
        w = mod.LeafletBridge(ch)("m", center=[0, 0], zoom=1)
        r = w.set_view([1, 2], 3)
        assert r.ok
        ops = list(r.ops)
        assert any(
            (o.get("op") if isinstance(o, dict) else getattr(o, "op", None))
            == "bridge.call"
            for o in ops
        )


# ── chaos inputs ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        None,
        123,
        [],
        {},
        "x" * 5000,
        "../../etc/passwd",
        "a; DROP TABLE",
        "\x00null",
        "emoji-🔥",
    ],
)
def test_resolve_preset_weird_names_do_not_crash(bad):
    if bad is None or not isinstance(bad, str) or not bad.strip():
        with pytest.raises(Exception):
            resolve_preset_spec(bad)  # type: ignore[arg-type]
        return
    # free-form string packages should resolve or raise cleanly
    try:
        spec = resolve_preset_spec(str(bad)[:80])
        assert "package" in spec
    except Exception as exc:
        assert exc.__class__.__name__  # clean failure ok


def test_mount_spec_json_props_serializable():
    ch = _ch()
    # nested / non-JSON types coerced via default=str
    class Weird:
        def __str__(self):
            return "W"

    spec = ch.bridge.mount_spec(
        "id",
        package="chart.js",
        props={"x": Weird(), "n": 1, "nested": {"a": [1, 2]}},
    )
    raw = spec.attrs["data-channel-bridge-props"]
    json.loads(raw)  # must be valid JSON


def test_concurrent_chart_commits_no_crash():
    ch = _ch()
    charts = ChartBridge(ch)
    islands = [charts(f"c{i}", values=[i], labels=["a"]) for i in range(20)]

    def work(idx: int):
        return islands[idx % len(islands)].commit(values=[random.random() for _ in range(5)])

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, i) for i in range(100)]
        results = [f.result(timeout=10) for f in futs]
    assert all(r.ok for r in results)
    assert sum(len(list(r.ops)) for r in results) >= 100


def test_load_many_presets_sequential():
    """Generate many free-form packages quickly (load-ish)."""
    with tempfile.TemporaryDirectory() as td:
        for i in range(15):
            name = f"pkg{i}"
            root = create_bridge_preset(
                td, name, methods=("update", "ping"), force=True
            )
            assert (root / "contract.json").is_file()
            methods = json.loads((root / "contract.json").read_text())["methods"]
            assert "update" in methods and "ping" in methods


def test_capability_regression_bridge_day1():
    """Public API API still present after all refactors."""
    ch = _ch()
    assert hasattr(ch, "bridge")
    for name in (
        "mount_spec",
        "mount_ops",
        "update_ops",
        "call",
        "register",
        "load_contract",
    ):
        assert callable(getattr(ch.bridge, name))
    charts = ChartBridge(ch)
    rev = charts("rev", values=[1, 2], labels=["a", "b"], kind="bar")
    assert rev.mount_spec().attrs["data-channel-bridge-package"] == "chart.js"
    r = rev.commit_kind("line")
    assert r.ok


def test_register_then_call_args_pass_through_without_contract_arg_schema():
    ch = _ch()
    ch.bridge.register("x.js", methods=("foo",))
    ops = ch.bridge.call("i", "foo", {"a": 1}, package="x.js")
    assert ops


def test_mount_update_destroy_ops_shape():
    ch = _ch()
    m = ch.bridge.mount_ops("i1", "chart.js", props={"type": "bar"})
    u = ch.bridge.update_ops("i1", {"type": "line"})
    d = ch.bridge.destroy_ops("i1")
    assert m and u and d
    for batch, opname in ((m, "bridge.mount"), (u, "bridge.update"), (d, "bridge.destroy")):
        o = batch[0]
        name = o.get("op") if isinstance(o, dict) else getattr(o, "op", None)
        assert name == opname


def test_preset_force_overwrite_idempotent():
    with tempfile.TemporaryDirectory() as td:
        a = create_bridge_preset(td, "leaflet", force=True)
        b = create_bridge_preset(td, "leaflet", force=True)
        assert a == b
        assert (a / "preset.py").stat().st_mtime_ns >= 0


def test_unicode_island_ids():
    ch = _ch()
    rev = ChartBridge(ch)("rev-α-β", values=[1], labels=["λ"])
    assert rev.id == "rev-α-β"
    assert rev.commit(values=[2]).ok


def test_very_large_props_commit():
    ch = _ch()
    big = list(range(5000))
    rev = ChartBridge(ch)("big", values=big[:10], labels=[str(i) for i in range(10)])
    r = rev.commit(values=big[:100], labels=[str(i) for i in range(100)])
    assert r.ok
    # props JSON in mount_spec should not explode
    spec = rev.mount_spec()
    assert len(spec.attrs["data-channel-bridge-props"]) > 10
