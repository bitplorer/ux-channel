"""WebRTC signaling plane — out of the box."""
from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.webrtc import MemoryRtcStore, get_rtc_store, reset_rtc_store


class TestMemoryRtcStore(unittest.TestCase):
    def setUp(self):
        reset_rtc_store()
        self.store = MemoryRtcStore(max_peers=3, peer_ttl_s=60, signal_ttl_s=60)

    def test_poll_join_and_roster(self):
        a = self.store.poll("lobby", "alice", name="Alice", since=0)
        b = self.store.poll("lobby", "bob", name="Bob", since=0)
        self.assertTrue(a["ok"])
        ids = {p["id"] for p in b["peers"]}
        self.assertEqual(ids, {"alice", "bob"})

    def test_signal_inbox(self):
        self.store.poll("r", "a", since=0)
        self.store.poll("r", "b", since=0)
        sig = self.store.signal(
            "r", from_peer="a", to_peer="b", kind="offer", payload={"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"}
        )
        self.assertTrue(sig["ok"])
        inbox = self.store.poll("r", "b", since=0)
        self.assertEqual(len(inbox["signals"]), 1)
        self.assertEqual(inbox["signals"][0]["kind"], "offer")
        # since cursor
        empty = self.store.poll("r", "b", since=inbox["signals"][0]["id"])
        self.assertEqual(empty["signals"], [])

    def test_room_full(self):
        self.store.poll("r", "a", since=0)
        self.store.poll("r", "b", since=0)
        self.store.poll("r", "c", since=0)
        with self.assertRaises(OverflowError):
            self.store.poll("r", "d", since=0)

    def test_leave(self):
        self.store.poll("r", "a", since=0)
        self.store.leave("r", "a")
        b = self.store.poll("r", "b", since=0)
        self.assertEqual([p["id"] for p in b["peers"]], ["b"])

    def test_bad_kind(self):
        self.store.poll("r", "a", since=0)
        with self.assertRaises(ValueError):
            self.store.signal("r", from_peer="a", to_peer="b", kind="nope", payload={})


class TestRtcHttp(unittest.TestCase):
    def setUp(self):
        reset_rtc_store()
        self.app = FastAPI()
        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            enforce_same_origin=False,
            require_channel_header=False,
            webrtc_enabled=True,
        )
        self.ch = Channel.boot(self.app, config=cfg)
        self.client = TestClient(self.app)

    def test_scripts_include_webrtc(self):
        html = str(demo_scripts(self.ch))
        self.assertIn("ux-webrtc.js", html)
        self.assertIn("ux-channel.js", html)

    def test_scripts_can_disable(self):
        html = str(demo_scripts(self.ch, webrtc=False))
        self.assertNotIn("ux-webrtc.js", html)

    def test_poll_and_signal_http(self):
        r = self.client.get("/ux-channel/rtc", params={"room": "t", "peer": "p1", "since": 0})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

        self.client.get("/ux-channel/rtc", params={"room": "t", "peer": "p2", "since": 0})
        post = self.client.post(
            "/ux-channel/rtc",
            json={
                "op": "signal",
                "room": "t",
                "from": "p1",
                "to": "p2",
                "kind": "offer",
                "payload": {"type": "offer", "sdp": "v=0"},
            },
        )
        self.assertEqual(post.status_code, 200)
        self.assertTrue(post.json()["ok"])

        inbox = self.client.get(
            "/ux-channel/rtc", params={"room": "t", "peer": "p2", "since": 0}
        ).json()
        self.assertGreaterEqual(len(inbox["signals"]), 1)

    def test_static_js_served(self):
        r = self.client.get("/ux-channel/static/ux-webrtc.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("UxWebRTC", r.text)

    def test_body_attrs(self):
        s = attr_string(self.ch.body_attrs(webrtc=True, webrtc_auto=True))
        self.assertIn("data-channel-webrtc-rtc", s)
        self.assertIn("data-channel-webrtc-auto", s)

    def test_plane_on_channel(self):
        self.assertTrue(self.ch.webrtc.enabled)
        self.assertTrue(self.ch.webrtc.path.endswith("/rtc"))
        d = self.ch.diagnose()
        self.assertIn("webrtc", d)
        self.assertTrue(d["webrtc"].get("enabled"))

    def test_leave_http(self):
        self.client.get("/ux-channel/rtc", params={"room": "x", "peer": "a", "since": 0})
        r = self.client.post("/ux-channel/rtc", json={"op": "leave", "room": "x", "peer": "a"})
        self.assertEqual(r.status_code, 200)


class TestWebrtcDisabled(unittest.TestCase):
    def test_disabled_skips_routes(self):
        reset_rtc_store()
        app = FastAPI()
        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            webrtc_enabled=False,
        )
        ch = Channel.boot(app, config=cfg)
        c = TestClient(app)
        # route not mounted
        r = c.get("/ux-channel/rtc", params={"room": "r", "peer": "p", "since": 0})
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("ux-webrtc.js", str(demo_scripts(ch, )))


if __name__ == "__main__":
    unittest.main()


class TestWebrtcMediaClientContract(unittest.TestCase):
    """JS ships media API surface (getUserMedia path)."""

    def setUp(self):
        reset_rtc_store()
        self.app = FastAPI()
        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            enforce_same_origin=False,
            require_channel_header=False,
        )
        self.ch = Channel.boot(self.app, config=cfg)
        self.client = TestClient(self.app)

    def test_js_has_media_api(self):
        js = self.client.get("/ux-channel/static/ux-webrtc.js").text
        for token in (
            "startMedia",
            "stopMedia",
            "muteAudio",
            "muteVideo",
            "getUserMedia",
            "onTrack",
            "onLocalStream",
            "addTrack",
            "getRemoteStream",
            "data-channel-webrtc-media",
        ):
            self.assertIn(token, js, msg=f"missing {token}")

    def test_body_media_attr(self):
        s = attr_string(self.ch.body_attrs(webrtc=True, webrtc_media="av"))
        self.assertIn("data-channel-webrtc-media", s)
        self.assertIn("av", s)

    def test_plane_media_attrs(self):
        d = self.ch.webrtc.body_attrs(room="call", media="audio")
        self.assertEqual(d.get("data-channel-webrtc-media"), "audio")


class TestWebrtcGapsFilled(unittest.TestCase):
    def setUp(self):
        reset_rtc_store()
        self.app = FastAPI()
        self.cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            enforce_same_origin=False,
            require_channel_header=False,
            webrtc_enabled=True,
        )
        self.ch = Channel.boot(self.app, config=self.cfg)
        self.client = TestClient(self.app)

    def test_ice_done_kind(self):
        store = get_rtc_store(self.cfg)
        store.poll("r", "a", since=0)
        store.poll("r", "b", since=0)
        out = store.signal(
            "r", from_peer="a", to_peer="b", kind="ice-done", payload=None
        )
        self.assertTrue(out["ok"])
        inbox = store.poll("r", "b", since=0)
        kinds = [s["kind"] for s in inbox["signals"]]
        self.assertIn("ice-done", kinds)

    def test_ticket_auth(self):
        from ux_channel.webrtc import sign_rtc_ticket, reset_rtc_store

        reset_rtc_store()
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
        denied = c.get("/ux-channel/rtc", params={"room": "x", "peer": "p", "since": 0})
        self.assertEqual(denied.status_code, 403)
        ticket = ch.webrtc.sign_ticket("x")
        ok = c.get(
            "/ux-channel/rtc",
            params={"room": "x", "peer": "p", "since": 0, "ticket": ticket},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["ok"])

    def test_ws_path_and_js_contract(self):
        self.assertTrue(self.ch.webrtc.ws_path.endswith("/rtc/ws"))
        js = self.client.get("/ux-channel/static/ux-webrtc.js").text
        for tok in ("ice-done", "rtc/ws", "WebSocket", "preferWs", "X-Channel-Rtc-Ticket"):
            self.assertIn(tok, js)

    def test_diagnose_lists_kinds(self):
        d = self.ch.webrtc.diagnose()
        self.assertIn("ice-done", d["kinds"])
        self.assertIn("ws_path", d)

    def test_body_attrs_ws_and_ice(self):
        attrs = self.ch.webrtc.body_attrs(room="lobby", auto=True)
        self.assertIn("data-channel-webrtc-ws", attrs)
        self.assertIn("data-channel-webrtc-ice", attrs)


class TestIceRestartAndRedisFlag(unittest.TestCase):
    def test_js_has_restart_ice(self):
        reset_rtc_store()
        app = FastAPI()
        ch = Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            ),
        )
        c = TestClient(app)
        js = c.get("/ux-channel/static/ux-webrtc.js").text
        self.assertIn("restartIce", js)

    def test_diagnose_store_memory(self):
        reset_rtc_store()
        app = FastAPI()
        ch = Channel.boot(
            app,
            config=ChannelConfig.development(
                secret="dev-secret-key-32chars-minimum!!!!",
                allow_memory_stores=True,
            ),
        )
        d = ch.webrtc.diagnose()
        self.assertEqual(d.get("store"), "MemoryRtcStore")

    def test_redis_store_optional(self):
        try:
            import redis  # noqa: F401
        except ImportError:
            self.skipTest("redis not installed")
        # Without a live server, constructing may still work with fake url
        # only if redis connects lazily — skip connect test
        from ux_channel.redis_extra import RedisRtcStore

        self.assertTrue(callable(RedisRtcStore))
