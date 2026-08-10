"""Public API mental model — keep cognitive load low."""
from __future__ import annotations

import unittest

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.host.channel import CHANNEL_PUBLIC_API, WEBRTC_PUBLIC_API
from ux_channel.realtime.webrtc import reset_rtc_store


class TestPublicApi(unittest.TestCase):
    def test_describe_string(self):
        text = Channel.describe()
        self.assertIn("Public API", text)
        self.assertIn("boot", text)
        self.assertIn("Placement", text)
        self.assertIn("truth", text.lower())

    def test_public_api_names_stable(self):
        self.assertEqual(Channel.public_api_names(), CHANNEL_PUBLIC_API)
        for name in CHANNEL_PUBLIC_API:
            if name == "boot":
                self.assertTrue(callable(Channel.boot))
            # others need instance

    def test_public_api_on_instance(self):
        reset_rtc_store()
        ch = Channel.boot(
            FastAPI(),
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            ),
        )
        for name in CHANNEL_PUBLIC_API:
            if name == "boot":
                continue
            self.assertTrue(
                hasattr(ch, name),
                msg=f"public API name missing on Channel: {name}",
            )
        w = ch.webrtc
        # webrtc is power layer — not public API
        self.assertTrue(hasattr(ch, "media"))
        self.assertTrue(hasattr(ch, "runtime"))
        self.assertTrue(hasattr(ch, "bridge"))

    def test_root_stays_layer_free(self):
        import ux_channel as u

        for banned in (
            "create_app",
            "get_rtc_store",
            "LiveKitSfu",
            "sign_rtc_ticket",
            "whip_enabled",
        ):
            self.assertFalse(hasattr(u, banned), banned)


if __name__ == "__main__":
    unittest.main()
