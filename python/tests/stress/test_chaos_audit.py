"""Chaotic / multi-instance / adversarial cases found in library audit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Region
from ux_channel.security.security import validate_action_name

SECRET = "chaos-audit-secret-key-32chars!!!!!"


def test_multi_instance_region_actions_use_uid_method():
    ch = Channel.boot(secret=SECRET)

    class Card(Region):
        def render(self, ctx):
            return self.uid

        @Region.action
        def tap(self):
            return self.ch.done(notice=self.uid)

    a = Card(ch, uid="card.a").mount()
    b = Card(ch, uid="card.b").mount()
    assert a.tap.action == "card.a.tap"
    assert b.tap.action == "card.b.tap"
    r = ch.registry.dispatch(
        Intent(action="card.a.tap", args={}, cap=ch.mint("card.a.tap", {}))
    )
    assert r.ok
    r = ch.registry.dispatch(
        Intent(action="card.b.tap", args={}, cap=ch.mint("card.b.tap", {}))
    )
    assert r.ok


def test_numeric_uid_segments_valid_action_names():
    validate_action_name("card.0.tap")
    ch = Channel.boot(secret=SECRET)

    class Card(Region):
        def render(self, ctx):
            return "x"

        @Region.action
        def tap(self):
            return self.ch.done()

    Card(ch, uid="card.0").mount()
    r = ch.registry.dispatch(
        Intent(action="card.0.tap", args={}, cap=ch.mint("card.0.tap", {}))
    )
    assert r.ok


def test_form_cannot_override_sealed_trust_args():
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="F.save")
    def save(title: str = "", body: str = ""):
        return ch.done(notice=f"{title}|{body}")

    cap = ch.mint("F.save", {"title": "T"})
    r = ch.registry.dispatch(
        Intent(
            action="F.save",
            args={"title": "T"},
            form={"body": "hello", "title": "HACK"},
            cap=cap,
        )
    )
    assert r.ok
    toast = next(o for o in r.ops if o.get("op") == "toast")
    assert toast["message"].startswith("T|")
    assert "HACK" not in toast["message"]


def test_once_cap_concurrent_single_success():
    ch = Channel.boot(
        secret=SECRET,
        config=ChannelConfig.development(secret=SECRET, allow_memory_stores=True),
    )
    hits: list[int] = []

    @ch.on(name="Pay.go", once=True)
    def pay():
        hits.append(1)
        return ch.done()

    cap = ch.mint("Pay.go", {}, once=True)

    def go(_: int):
        return ch.registry.dispatch(Intent(action="Pay.go", args={}, cap=cap))

    with ThreadPoolExecutor(24) as ex:
        results = list(ex.map(go, range(24)))
    assert sum(1 for r in results if r.ok) == 1
    assert len(hits) == 1


def test_production_internal_error_does_not_leak_exception():
    ch = Channel.boot(
        config=ChannelConfig.production(secret=SECRET, allow_memory_stores=True)
    )

    @ch.on(name="X.boom")
    def boom():
        raise RuntimeError("password=hunter2")

    r = ch.registry.dispatch(
        Intent(action="X.boom", args={}, cap=ch.mint("X.boom", {}))
    )
    assert not r.ok
    assert r.error and "hunter2" not in (r.error.message or "")


def test_fastapi_action_and_batch_smoke():
    app = FastAPI()
    ch = Channel.boot(
        app, config=ChannelConfig.development(secret=SECRET, allow_memory_stores=True)
    )

    @ch.on(name="Echo.hi")
    def hi(msg: str = ""):
        return ch.done(notice=msg)

    client = TestClient(app)
    cap = ch.mint("Echo.hi", {"msg": "yo"})
    r = client.post(
        "/ux-channel/action",
        json={"action": "Echo.hi", "args": {"msg": "yo"}, "cap": cap},
        headers={"X-UID-Channel": "1"},
    )
    assert r.status_code == 200 and r.json()["ok"]

    r = client.post(
        "/ux-channel/batch",
        json={
            "intents": [
                {"action": "Echo.hi", "args": {"msg": "a"}, "cap": ch.mint("Echo.hi", {"msg": "a"})},
                {"action": "Echo.hi", "args": {"msg": "b"}, "cap": ch.mint("Echo.hi", {"msg": "b"})},
            ]
        },
        headers={"X-UID-Channel": "1"},
    )
    # all ok → 200
    assert r.status_code == 200
    assert r.json().get("ok") is True
