"""Public API — minimal root + explicit layers (uxchannel philosophy)."""
from __future__ import annotations

import unittest

import ux_channel as uc


# Root must stay small — protocol + Channel façade + regions + config.
ROOT_REQUIRED = [
    "Channel",
    "ChannelConfig",
    "Result",
    "Intent",
    "Region",
    "ActionError",
    "ChannelError",
    "create_channel",
    "ControlAttrs",
    "morph",
    "toast",
]

# These belong in layers — must NOT appear on root.
ROOT_FORBIDDEN = [
    "WebRTCPlane",
    "MemoryRtcStore",
    "get_rtc_store",
    "sign_rtc_ticket",
    "verify_rtc_ticket",
    "authorize_rtc",
    "webrtc_enabled",
    "rtc_metrics",
    "RtcMetrics",
    "get_sfu",
    "LiveKitSfu",
    "NullSfu",
    "SfuConfig",
    "whip_enabled",
    "parse_sdp_body",
    "is_sdp_offer",
    "create_app",
    "ScaffoldOptions",
    "available_templates",
    "validate_scaffold",
    "WebRTCError",
]


class TestMinimalRoot(unittest.TestCase):
    def test_required_core(self):
        missing = [n for n in ROOT_REQUIRED if not hasattr(uc, n)]
        self.assertEqual(missing, [], msg=f"missing core: {missing}")

    def test_layers_not_on_root(self):
        leaked = [n for n in ROOT_FORBIDDEN if hasattr(uc, n)]
        self.assertEqual(leaked, [], msg=f"layer leaked to root: {leaked}")

    def test_all_has_no_layer_spam(self):
        for n in ROOT_FORBIDDEN:
            self.assertNotIn(n, uc.__all__, msg=f"{n} in __all__")

    def test_all_has_core(self):
        for n in ("Channel", "ChannelConfig", "Region", "Result"):
            self.assertIn(n, uc.__all__)


class TestLayerImports(unittest.TestCase):
    """Layers remain first-class — import from submodules."""

    def test_webrtc_layer(self):
        from ux_channel.webrtc import (
            WebRTCPlane,
            authorize_rtc,
            get_rtc_store,
            sign_rtc_ticket,
            webrtc_enabled,
        )

        self.assertTrue(callable(sign_rtc_ticket))
        self.assertTrue(callable(get_rtc_store))

    def test_sfu_layer(self):
        from ux_channel.sfu import LiveKitSfu, NullSfu, SfuConfig, get_sfu

        self.assertIsInstance(get_sfu(None), NullSfu)

    def test_whip_layer(self):
        from ux_channel.whip import is_sdp_offer, parse_sdp_body, whip_enabled

        self.assertTrue(is_sdp_offer("v=0\nm=audio 0 RTP/AVP 0\n"))

    def test_scaffold_layer(self):
        from ux_channel.scaffold import ScaffoldOptions, create_app, available_templates

        self.assertIn("minimal", available_templates())

    def test_metrics_layer(self):
        from ux_channel.webrtc_metrics import rtc_metrics

        self.assertIn("counters", rtc_metrics.snapshot())

    def test_ch_webrtc_after_boot(self):
        """Day-1 WebRTC DX is ch.webrtc — not root free functions."""
        from fastapi import FastAPI

        from ux_channel import Channel, ChannelConfig
        from ux_channel.webrtc import reset_rtc_store

        reset_rtc_store()
        app = FastAPI()
        ch = Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            ),
        )
        self.assertTrue(hasattr(ch, "webrtc"))
        self.assertTrue(ch.webrtc.path.endswith("/rtc"))
        self.assertIn("ux-webrtc", ch.webrtc.script_src)


class TestErrorLayer(unittest.TestCase):
    def test_webrtc_error_from_errors_module(self):
        from ux_channel.errors import WebRTCError

        self.assertTrue(issubclass(WebRTCError, uc.ChannelError))


if __name__ == "__main__":
    unittest.main()
