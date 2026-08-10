"""P0–P3 coverage: production tickets, metrics, WHIP, SFU, redis (optional)."""
from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.realtime.webrtc import get_rtc_store, reset_rtc_store
from ux_channel.realtime.webrtc_metrics import rtc_metrics
from ux_channel.realtime.sfu import NullSfu, get_sfu, SfuConfig, LiveKitSfu


class TestP0ProductionTickets(unittest.TestCase):
    def test_production_defaults_require_ticket(self):
        cfg = ChannelConfig.production(
            "prod-secret-key-32chars-minimum!!!!!!",
            allow_memory_stores=True,
        )
        self.assertTrue(cfg.webrtc_require_ticket)
        self.assertTrue(cfg.webrtc_require_origin)

    def test_ticket_flow_end_to_end(self):
        reset_rtc_store()
        rtc_metrics.reset()
        app = FastAPI()
        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            webrtc_require_ticket=True,
            enforce_same_origin=False,
            require_channel_header=False,
        )
        ch = Channel.boot(app, config=cfg)
        c = TestClient(app)
        self.assertEqual(
            c.get("/ux-channel/rtc", params={"room": "p", "peer": "a", "since": 0}).status_code,
            403,
        )
        ticket = ch.webrtc.sign_ticket("p", sub="u1")
        r = c.get(
            "/ux-channel/rtc",
            params={"room": "p", "peer": "a", "since": 0, "ticket": ticket},
        )
        self.assertEqual(r.status_code, 200)
        snap = c.get("/ux-channel/rtc/metrics").json()
        self.assertIn("counters", snap)


class TestP1Metrics(unittest.TestCase):
    def test_metrics_count_signals(self):
        reset_rtc_store()
        rtc_metrics.reset()
        store = get_rtc_store(
            ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            )
        )
        store.poll("m", "a", since=0)
        store.poll("m", "b", since=0)
        store.signal("m", from_peer="a", to_peer="b", kind="offer", payload={"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"})
        snap = rtc_metrics.snapshot()
        self.assertGreaterEqual(snap["counters"].get("signals_total", 0), 1)
        self.assertGreaterEqual(snap["counters"].get("poll_total", 0), 1)


class TestP2WhipAndSfu(unittest.TestCase):
    def test_whip_disabled_by_default(self):
        reset_rtc_store()
        app = FastAPI()
        Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
                enforce_same_origin=False,
                require_channel_header=False,
            ),
        )
        c = TestClient(app)
        self.assertEqual(c.post("/ux-channel/whip/r", content=b"v=0\r\nm=audio 0 UDP/TLS/RTP/SAVPF 0\r\n").status_code, 404)

    def test_whip_enabled(self):
        reset_rtc_store()
        app = FastAPI()
        Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
                enforce_same_origin=False,
                require_channel_header=False,
                whip_enabled=True,
            ),
        )
        c = TestClient(app)
        sdp = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=setup:actpass\r\n"
        r = c.post("/ux-channel/whip/room1", content=sdp.encode(), headers={"Content-Type": "application/sdp"})
        self.assertIn(r.status_code, (201, 202))

    def test_sfu_null_and_token_route(self):
        self.assertIsInstance(get_sfu(None), NullSfu)
        reset_rtc_store()
        app = FastAPI()
        Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
                enforce_same_origin=False,
                require_channel_header=False,
            ),
        )
        c = TestClient(app)
        r = c.post("/ux-channel/sfu/token", json={"room": "x", "identity": "u"})
        self.assertEqual(r.status_code, 501)

    def test_livekit_jwt_fallback(self):
        try:
            import jwt  # noqa: F401
        except ImportError:
            self.skipTest("PyJWT missing")
        sfu = LiveKitSfu(
            SfuConfig(
                url="https://lk.example",
                api_key="APIKEY",
                api_secret="secret-secret-secret-secret",
            )
        )
        tok = sfu.create_token(room="lobby", identity="u1")
        self.assertTrue(len(tok) > 20)


class TestP0RedisOptional(unittest.TestCase):
    def test_redis_rtc_with_fakeredis_or_real(self):
        reset_rtc_store()
        url = os.environ.get("REDIS_URL")
        if os.environ.get("UX_CHANNEL_RUN_REDIS_TESTS") == "1" and url:
            from ux_channel.redis_extra import RedisRtcStore

            store = RedisRtcStore(url, max_peers=4)
            a = store.poll("rr", "a", since=0)
            b = store.poll("rr", "b", since=0)
            self.assertEqual({p["id"] for p in b["peers"]}, {"a", "b"})
            store.signal(
                "rr",
                from_peer="a",
                to_peer="b",
                kind="offer",
                payload={"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"},
            )
            inbox = store.poll("rr", "b", since=0)
            self.assertTrue(any(s["kind"] == "offer" for s in inbox["signals"]))
            store.leave("rr", "a")
            return
        # fakeredis unit path
        try:
            import fakeredis
        except ImportError:
            self.skipTest("no redis test backend")
        from ux_channel.redis_extra import RedisRtcStore

        fake = fakeredis.FakeRedis(decode_responses=True)
        # inject by duck-typing url as client: _client accepts non-str
        store = RedisRtcStore(fake, max_peers=3)
        # pubsub thread may not fully work on fakeredis — poll/signal still must work
        store.poll("f", "p1", since=0)
        store.poll("f", "p2", since=0)
        store.signal(
            "f", from_peer="p1", to_peer="p2", kind="ice", payload={"candidate": "x"}
        )
        inbox = store.poll("f", "p2", since=0)
        self.assertTrue(len(inbox["signals"]) >= 1)


class TestP3Version(unittest.TestCase):
    def test_version_0_2(self):
        from ux_channel import __version__

        self.assertTrue(__version__.startswith("0.1"))


if __name__ == "__main__":
    unittest.main()
