"""0.1 production lock — contracts that must not regress.

Locks brand-critical production behavior:

* ``ChannelConfig.production`` strict defaults
* ``from_env`` prefix: ``UX_CHANNEL_*`` only
* Dashboard model ``schema == 1`` and JSON-safe panels
* CSRF: channel header never collides with host meta
* Static JS: ``uxBridge`` + ``X-Channel``
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from ux_channel import serde as _serde
from ux_channel.config import ChannelConfig
from ux_channel.dx_dashboard import DASHBOARD_MODEL_SCHEMA, build_dashboard_model
from ux_channel.host_csrf import CHANNEL_CSRF_HEADER, CHANNEL_CSRF_VALUE
from ux_channel_ux_dom.csrf import (
    UX_DOM_CSRF_META_NAME,
    assert_csrf_names_do_not_collide,
    channel_and_ux_dom_headers,
)


class TestProductionConfigLock(unittest.TestCase):
    def test_production_requires_strong_secret(self):
        with self.assertRaises(ValueError):
            ChannelConfig.production(secret="short")

    def test_production_defaults_are_strict(self):
        cfg = ChannelConfig.production(secret="x" * 32)
        self.assertEqual(cfg.environment, "production")
        self.assertTrue(cfg.require_cap)
        self.assertTrue(cfg.require_channel_header)
        self.assertFalse(cfg.allow_memory_stores)

    def test_from_env_reads_ux_channel_prefix(self):
        env = {
            "UX_CHANNEL_SECRET": "y" * 32,
            "UX_CHANNEL_ENV": "production",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = ChannelConfig.from_env()
        self.assertEqual(cfg.secret, "y" * 32)
        self.assertEqual(cfg.environment, "production")

    def test_from_env_requires_secret_in_production(self):
        with mock.patch.dict(os.environ, {"UX_CHANNEL_ENV": "production"}, clear=True):
            with self.assertRaises(ValueError):
                ChannelConfig.from_env()


class TestDashboardModelLock(unittest.TestCase):
    def test_schema_is_one(self):
        self.assertEqual(DASHBOARD_MODEL_SCHEMA, 1)
        model = build_dashboard_model(doctor={"ok": True}, latencies=[])
        self.assertEqual(model["schema"], 1)
        # JSON-serializable (no Panel factory leakage)
        raw = _serde.dumps(model)
        data = json.loads(raw)
        self.assertEqual(data["schema"], 1)
        for p in data["panels"]:
            self.assertIsInstance(p.get("html", ""), str)
            self.assertIsInstance(p.get("svg", ""), str)


class TestCsrfCoexistenceLock(unittest.TestCase):
    def test_headers_never_collide(self):
        assert_csrf_names_do_not_collide()
        self.assertNotEqual(CHANNEL_CSRF_HEADER.lower(), UX_DOM_CSRF_META_NAME.lower())
        h = channel_and_ux_dom_headers(host_token="host-tok")
        self.assertEqual(h.get(CHANNEL_CSRF_HEADER), CHANNEL_CSRF_VALUE)
        # host token present under a non-channel header name
        self.assertTrue(
            any(k.lower() != CHANNEL_CSRF_HEADER.lower() and v == "host-tok" for k, v in h.items())
            or "host-tok" in h.values()
        )


class TestStaticBrandLock(unittest.TestCase):
    def test_js_uses_ux_bridge_and_ux_headers(self):
        root = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"
        bridge = (root / "ux-bridge.js").read_text(encoding="utf-8")
        channel = (root / "ux-channel.js").read_text(encoding="utf-8")
        self.assertIn("uxBridge", bridge)
        self.assertNotIn("uidBridge", bridge)
        self.assertTrue(
            "X-Channel" in channel or "x-channel" in channel.lower(),
            "channel client must send X-Channel",
        )


if __name__ == "__main__":
    unittest.main()
