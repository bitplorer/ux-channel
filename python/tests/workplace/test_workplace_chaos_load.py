"""Chaos / load / integration for Workplace + tickets + I/O gate."""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st

from ux_channel import Channel, ChannelConfig, attach_audit
from ux_channel.io_adapters import LabDutAdapter, LightsAdapter, ScannerAdapter
from ux_channel.foundations.io_channel import IoChannelError
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import (
    WorkplaceError,
    WorkplaceTicketError,
    claim_from_rtc_ticket,
    sign_workplace_ticket,
    workplace,
)
from ux_channel.realtime.webrtc import sign_rtc_ticket


SECRET = "workplace-chaos-load-secret-key-32b!"


def _boot(require_cap: bool = True):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=require_cap,
            audit=True,
            rate_limit_per_minute=0,
            enforce_same_origin=False,
            require_channel_header=False,
        ),
    )
    attach_audit(ch)
    return app, ch


def test_integration_pos_scan_agent_pay_path():
    """Full vertical: ticket → workplace → scan ≡ dispatch → quantity pay."""
    app, ch = _boot()
    cart: dict[str, int] = {}
    paid: list[str] = []

    @ch.on
    def add_line(sku: str = ""):
        cart[sku] = cart.get(sku, 0) + 1
        return ch.done(notice=sku)

    @ch.on
    def pay():
        total = Quantity.from_store(
            len(cart) * 10, "USD", source="db.cart.total", revision=1
        )
        paid.append(str(total.magnitude))
        cart.clear()
        return ch.done(notice=f"paid {total.magnitude}")

    scanner = ScannerAdapter()
    tok = sign_workplace_ticket(
        ch.config, "pos", sub="clerk", scopes=["add", "pos", "scan", "pay"]
    )
    wp = workplace(ch, ticket_token=tok).allow(scanner)

    # button-equivalent
    assert wp.dispatch("add_line", {"sku": "A"}).ok
    # scanner event path
    payload = scanner.inject("B")
    args = wp.check_event(scanner.name, "scanned", payload, method_for_keys="read")
    assert wp.dispatch("add_line", {"sku": args.get("sku") or "B"}).ok
    # control mint
    ctrl = wp.control(add_line, trust_sku="C").as_dict()
    assert "data-channel-cap" in ctrl
    assert wp.dispatch("pay", {}).ok
    assert paid == ["20"]
    assert cart == {}
    # chaos: wrong room ticket
    with pytest.raises(WorkplaceTicketError):
        workplace(ch, ticket_token=tok, room="other", attach=False)


def test_chaos_forged_and_expired_tickets():
    app, ch = _boot()
    tok = sign_workplace_ticket(
        ch.config, "r", sub="p", scopes=["pos"], max_age=1
    )
    with pytest.raises(WorkplaceTicketError):
        workplace(ch, ticket_token="not-a-real-ticket", attach=False)
    with pytest.raises(WorkplaceTicketError):
        workplace(ch, ticket_token=tok + "x", attach=False)
    time.sleep(2)
    with pytest.raises(WorkplaceTicketError):
        workplace(ch, ticket_token=tok, attach=False)


def test_chaos_scope_escape_attempts():
    app, ch = _boot()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done()

    @ch.on
    def lab_flash():
        return ch.done()

    @ch.on
    def lights_scene(scene: str = "party"):
        return ch.done()

    lab, lights = LabDutAdapter(), LightsAdapter()
    tok = sign_workplace_ticket(
        ch.config, "party", sub="guest", scopes=["lights"], max_age=300
    )
    wp = workplace(ch, ticket_token=tok).allow(lab, lights)

    assert wp.run_io("home.lights", "scene", ["party"])
    with pytest.raises((WorkplaceError, IoChannelError)):
        wp.dispatch("lab_flash", {})
    with pytest.raises((WorkplaceError, IoChannelError)):
        wp.control(lab_flash)
    with pytest.raises(IoChannelError):
        wp.run_io("lab.dut", "flash", quantity=Quantity.from_store(
            1, "count", source="x", revision=1
        ))
    # try widen via rebind mapping — must fail
    with pytest.raises(IoChannelError):
        wp.narrow(["lights", "admin"])


def test_load_concurrent_dispatch_and_io():
    """Thread burst: many dispatches + I/O under one workplace."""
    app, ch = _boot()
    hits = {"n": 0}

    @ch.on
    def add_line(sku: str = ""):
        hits["n"] += 1
        return ch.done()

    scanner = ScannerAdapter()
    lights = LightsAdapter()
    tok = sign_workplace_ticket(
        ch.config, "pos", sub="load", scopes=["add", "pos", "scan", "lights"]
    )
    wp = workplace(ch, ticket_token=tok).allow(scanner, lights)

    def work(i: int):
        if i % 3 == 0:
            r = wp.dispatch("add_line", {"sku": f"S{i % 5}"})
            return r.ok
        if i % 3 == 1:
            payload = scanner.inject(f"S{i}")
            args = wp.check_event(
                scanner.name, "scanned", payload, method_for_keys="read"
            )
            r = wp.dispatch("add_line", {"sku": str(args.get("sku") or "x")})
            return r.ok
        wp.run_io("home.lights", "scene", [random.choice(["party", "dim", "off"])])
        return True

    ok = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(work, i) for i in range(120)]
        for f in as_completed(futs):
            if f.result():
                ok += 1
    assert ok >= 110
    assert hits["n"] >= 70
    assert len(wp.export_io_audit()) >= 1


def test_load_http_actions_with_workplace_caps():
    """HTTP integration: signed controls under require_cap."""
    app, ch = _boot(require_cap=True)

    @ch.on
    def add_line(sku: str = ""):
        return ch.done(notice=sku)

    tok = sign_workplace_ticket(
        ch.config, "pos", sub="http", scopes=["add", "pos"]
    )
    wp = workplace(ch, ticket_token=tok)
    attrs = wp.control(add_line, trust_sku="Z").as_dict()
    cap = attrs.get("data-channel-cap")
    assert cap

    client = TestClient(app)
    r = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "add_line",
            "args": {"sku": "Z"},
            "cap": cap,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True or body.get("v") == "1"

    # forged action name with same cap should fail closed
    r2 = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "not_a_real_action",
            "args": {},
            "cap": cap,
        },
    )
    assert r2.status_code in (200, 400, 403, 404)
    if r2.status_code == 200:
        assert r2.json().get("ok") is False or r2.json().get("error")


def test_integration_rtc_ticket_bridge():
    app, ch = _boot()
    rtc = sign_rtc_ticket(ch.config, "media-1", sub="viewer")
    claim = claim_from_rtc_ticket(
        ch.config, rtc, "media-1", scopes=["view", "lights"]
    )
    wp = workplace(ch, claim=claim).allow(LightsAdapter())
    assert wp.claim.peer_id == "viewer"
    wp.run_io("home.lights", "status")


@settings(max_examples=25, deadline=None)
@given(
    scopes=st.lists(
        st.sampled_from(["pos", "add", "scan", "lights", "lab", "view"]),
        min_size=1,
        max_size=3,
        unique=True,
    )
)
def test_prop_ticket_roundtrip_scopes(scopes):
    app, ch = _boot()
    tok = sign_workplace_ticket(
        ch.config, "room-x", sub="u", scopes=scopes, max_age=60
    )
    wp = workplace(ch, ticket_token=tok, attach=False)
    assert set(wp.claim.scopes) == set(scopes)
    assert wp.claim.room == "room-x"
    # mint attenuated subset
    sub = scopes[:1]
    tok2 = wp.mint_ticket(scopes=sub)
    wp.rebind(ticket_token=tok2)
    assert set(wp.claim.scopes) == set(sub)
