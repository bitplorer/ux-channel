"""WebRTC + Workplace mesh membership integration."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.io_adapters import ScannerAdapter
from ux_channel.webrtc import verify_rtc_ticket
from ux_channel.workplace import (
    WorkplaceTicketError,
    issue_mesh_membership,
    workplace_from_membership,
    workplace_from_rtc,
)


SECRET = "workplace-mesh-test-secret-key-32bytes!"


def _boot():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=True,
            require_channel_header=True,
            audit=True,
        ),
    )
    return app, ch


def test_issue_mesh_membership_both_tickets():
    app, ch = _boot()
    mem = issue_mesh_membership(
        ch, "room-a", sub="user-1", scopes=["pos", "add", "view"]
    )
    assert mem.room == "room-a"
    assert mem.sub == "user-1"
    assert "pos" in mem.scopes
    assert mem.rtc_ticket and mem.workplace_ticket
    ok, detail = verify_rtc_ticket(ch.config, mem.rtc_ticket, "room-a")
    assert ok
    assert detail == "user-1" or "user-1" in str(detail)

    wp = workplace_from_membership(ch, mem).allow(ScannerAdapter())
    assert wp.claim.peer_id == "user-1"
    assert wp.claim.room == "room-a"


def test_workplace_from_rtc_server_scopes():
    app, ch = _boot()
    mem = issue_mesh_membership(ch, "media", sub="v", scopes=["view"])
    # Prefer RTC path but scopes from server (membership.scopes)
    wp = workplace_from_rtc(
        ch, mem.rtc_ticket, "media", scopes=["view", "lights"], attach=False
    )
    assert "lights" in wp.claim.scopes
    assert wp.claim.peer_id == "v"
    with pytest.raises(WorkplaceTicketError):
        workplace_from_rtc(
            ch, mem.rtc_ticket, "wrong", scopes=["view"], attach=False
        )


def test_three_surfaces_same_action():
    app, ch = _boot()
    seen: list[str] = []

    @ch.on
    def add_line(sku: str = ""):
        seen.append(sku)
        return ch.done(notice=sku)

    mem = issue_mesh_membership(
        ch, "pos", sub="clerk", scopes=["add", "pos", "scan"]
    )
    scanner = ScannerAdapter()
    wp = workplace_from_membership(ch, mem).allow(scanner)

    # button surface
    attrs = wp.control(add_line, trust_sku="A").as_dict()
    assert attrs.get("data-channel-cap")
    # agent surface
    assert wp.dispatch("add_line", {"sku": "B"}).ok
    # adapter surface
    payload = scanner.inject("C")
    args = wp.check_event(scanner.name, "scanned", payload, method_for_keys="read")
    assert wp.dispatch("add_line", {"sku": args.get("sku") or "C"}).ok
    assert seen == ["B", "C"]

    # HTTP with channel header + cap
    client = TestClient(app)
    r = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "add_line",
            "args": {"sku": "A"},
            "cap": attrs["data-channel-cap"],
        },
        headers={"X-Channel": "1"},
    )
    assert r.status_code == 200
    assert "A" in seen


def test_membership_to_dict_stable():
    app, ch = _boot()
    mem = issue_mesh_membership(ch, "r", sub="s", scopes=["a", "b"])
    d = mem.to_dict()
    assert d["room"] == "r"
    assert set(d["scopes"]) == {"a", "b"}
    assert "rtc_ticket" in d and "workplace_ticket" in d
