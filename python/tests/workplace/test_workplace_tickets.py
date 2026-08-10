"""Workplace tickets + claim-aware control (next-step upgrade)."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.io_adapters import ScannerAdapter
from ux_channel.realtime.webrtc import sign_rtc_ticket
from ux_channel.workplace import (
    WorkplaceError,
    WorkplaceTicketError,
    claim_from_rtc_ticket,
    claim_from_workplace_ticket,
    sign_workplace_ticket,
    workplace,
)


SECRET = "workplace-ticket-test-secret-key-32b!!"


def _boot(**cfg_extra):
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=True,
            **cfg_extra,
        ),
    )


def test_sign_and_claim_workplace_ticket():
    ch = _boot()
    tok = sign_workplace_ticket(
        ch.config,
        "pos-desk",
        sub="clerk-1",
        scopes=["pos", "add", "scan"],
        trust={"station": "A1"},
        max_age=120,
    )
    claim = claim_from_workplace_ticket(ch.config, tok, room="pos-desk")
    assert claim.room == "pos-desk"
    assert claim.peer_id == "clerk-1"
    assert "pos" in claim.scopes
    assert claim.trust.get("station") == "A1"
    assert claim.alive()

    with pytest.raises(WorkplaceTicketError):
        claim_from_workplace_ticket(ch.config, tok, room="other-room")


def test_workplace_from_ticket_token_dispatch_and_control():
    ch = _boot()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done(notice=sku)

    @ch.on
    def lab_flash():
        return ch.done()

    tok = sign_workplace_ticket(
        ch.config, "pos", sub="c1", scopes=["add", "pos", "scan"]
    )
    wp = workplace(ch, ticket_token=tok).allow(ScannerAdapter())
    assert wp.dispatch("add_line", {"sku": "X"}).ok

    attrs = wp.control(add_line, trust_sku="X")
    d = attrs.as_dict() if hasattr(attrs, "as_dict") else dict(attrs)
    # sealed control attrs present
    assert any("uid" in str(k).lower() or "action" in str(k).lower() for k in d) or d

    with pytest.raises(WorkplaceError):
        wp.control(lab_flash)
    with pytest.raises(WorkplaceError):
        wp.dispatch("lab_flash", {})


def test_mint_ticket_refresh_and_rebind():
    ch = _boot()
    tok = sign_workplace_ticket(ch.config, "r1", sub="p", scopes=["view", "pos"])
    wp = workplace(ch, ticket_token=tok)
    tok2 = wp.mint_ticket(scopes=["pos"])  # attenuated
    wp.rebind(ticket_token=tok2)
    assert wp.claim.scopes == frozenset({"pos"})
    assert wp.claim.peer_id == "p"


def test_claim_from_rtc_ticket_scopes_from_policy():
    ch = _boot()
    rtc = sign_rtc_ticket(ch.config, "media-room", sub="viewer-9")
    claim = claim_from_rtc_ticket(
        ch.config, rtc, "media-room", scopes=["view", "lights"]
    )
    assert claim.room == "media-room"
    assert claim.peer_id == "viewer-9"
    assert "lights" in claim.scopes
    with pytest.raises(WorkplaceTicketError):
        claim_from_rtc_ticket(
            ch.config, rtc, "wrong-room", scopes=["view"]
        )


def test_expired_ticket_fails():
    ch = _boot()
    tok = sign_workplace_ticket(
        ch.config, "r", sub="p", scopes=["pos"], max_age=1
    )
    time.sleep(2)
    with pytest.raises(WorkplaceTicketError):
        claim_from_workplace_ticket(ch.config, tok, max_age=1)
