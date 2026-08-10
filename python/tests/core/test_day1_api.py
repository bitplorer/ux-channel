"""Day-1 API mental model — keep cognitive load low."""
from __future__ import annotations

import unittest

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.host.dx import DAY1_CHANNEL_API, DAY1_WEBRTC_API
from ux_channel.realtime.webrtc import reset_rtc_store


class TestDay1Api(unittest.TestCase):
    def test_mental_model_string(self):
        text = Channel.mental_model()
        self.assertIn("Day-1", text)
        self.assertIn("boot", text)
        self.assertIn("Placement", text)
        self.assertIn("truth", text.lower())

    def test_day1_names_stable(self):
        self.assertEqual(Channel.day1_names(), DAY1_CHANNEL_API)
        for name in DAY1_CHANNEL_API:
            if name == "boot":
                self.assertTrue(callable(Channel.boot))
            # others need instance

    def test_day1_on_instance(self):
        reset_rtc_store()
        ch = Channel.boot(
            FastAPI(),
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            ),
        )
        for name in DAY1_CHANNEL_API:
            if name == "boot":
                continue
            self.assertTrue(
                hasattr(ch, name),
                msg=f"day-1 name missing on Channel: {name}",
            )
        w = ch.webrtc
        # webrtc is power layer — not day-1
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
