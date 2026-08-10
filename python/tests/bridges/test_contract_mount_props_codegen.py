"""Preset parameters are generated from contract mount_props only."""

import json
import tempfile
from pathlib import Path

from ux_channel.bridge_meta.bridge_preset_gen import create_bridge_preset, resolve_preset_spec


def test_chartjs_contract_lists_real_fields_not_css():
    spec = resolve_preset_spec("chartjs")
    props = (spec.get("mount_props") or {}).get("properties") or {}
    assert "options" in props
    assert "type" in props
    assert "css" not in props  # Chart.js has no top-level css prop


def test_codegen_mount_prop_keys_from_contract():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "chartjs", force=True)
        contract = json.loads((root / "contract.json").read_text())
        keys = set((contract.get("mount_props") or {}).get("properties") or {})
        code = (root / "preset.py").read_text()
        assert "MOUNT_PROP_KEYS" in code
        for k in keys:
            assert f'"{k}"' in code
        assert "invented css" in code.lower() or "No invented css" in code
        assert 'css=' not in code.split("Public API")[1][:500]


def test_leaflet_props_in_codegen():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "leaflet", force=True)
        code = (root / "preset.py").read_text()
        assert "center" in code and "zoom" in code


def test_named_methods_from_contract_args():
    import importlib.util
    import tempfile

    from fastapi import FastAPI
    from ux_channel import Channel, ChannelConfig
    from ux_channel.bridge_meta.bridge_preset_gen import create_bridge_preset

    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "leaflet", force=True)
        contract = json.loads((root / "contract.json").read_text())
        assert contract["methods"]["setView"]["args"][0]["name"] == "center"
        code = (root / "preset.py").read_text()
        assert "def set_view(self, center" in code
        assert "def fly_to(self, center" in code
        # runtime
        spec = importlib.util.spec_from_file_location("lf", root / "preset.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        ch = Channel.boot(
            FastAPI(),
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
                require_cap=False,
            ),
        )
        w = mod.LeafletBridge(ch)("m1", center=[0, 0], zoom=2)
        r = w.set_view([1.0, 2.0], 5)
        assert r.ok
        ops = list(r.ops)
        assert any(
            (o.get("op") if isinstance(o, dict) else getattr(o, "op", None))
            == "bridge.call"
            for o in ops
        )
