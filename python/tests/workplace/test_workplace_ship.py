"""Ship polish: revoke, webrtc membership helper, lab/pos integration."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.io_adapters import LabDutAdapter, ScannerAdapter
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import (
    WorkplaceTicketError,
    issue_mesh_membership,
    revoke_mesh_membership,
    workplace_from_membership,
)


SECRET = "workplace-ship-test-secret-key-32b!!!"


def _boot(**kw):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=True,
            require_channel_header=True,
            audit=True,
            **kw,
        ),
    )
    return app, ch


def test_revoke_workplace_ticket_blocks_rebind():
    app, ch = _boot()
    mem = issue_mesh_membership(ch, "r", sub="u", scopes=["pos", "add"])
    wp = workplace_from_membership(ch, mem, attach=False)
    assert wp.membership_ticket
    wp.revoke_membership()
    with pytest.raises(WorkplaceTicketError):
        workplace_from_membership(ch, mem, attach=False)


def test_revoke_mesh_membership_both_tickets():
    app, ch = _boot()
    mem = ch.webrtc.issue_membership(
        "lab", sub="tech", scopes=["lab", "lab.flash", "view"]
    )
    assert mem.rtc_ticket and mem.workplace_ticket
    revoke_mesh_membership(mem, channel=ch)
    with pytest.raises(WorkplaceTicketError):
        workplace_from_membership(ch, mem, attach=False)
    with pytest.raises(Exception):
        ch.webrtc.workplace_from_ticket(
            mem.rtc_ticket, "lab", scopes=["lab"], attach=False
        )


def test_webrtc_issue_membership_and_flash():
    app, ch = _boot()
    lab = LabDutAdapter()

    @ch.on
    def lab_flash():
        q = Quantity.from_store(1, "count", source="lab.budget", revision=1)
        wp.run_io("lab.dut", "flash", quantity=q)
        return ch.done()

    mem = ch.webrtc.issue_membership(
        "lab-cell", sub="t1", scopes=["lab", "lab.flash"]
    )
    wp = workplace_from_membership(ch, mem).allow(lab)
    assert wp.dispatch("lab_flash", {}).ok
    assert lab.flash_count == 1


def test_client_header_required_http():
    app, ch = _boot()

    @ch.on
    def ping():
        return ch.done(notice="ok")

    mem = issue_mesh_membership(ch, "pos", sub="c", scopes=["pos", "add", "ping"])
    # ping may not match scopes - use add
    @ch.on
    def add_line(sku: str = ""):
        return ch.done()

    wp = workplace_from_membership(ch, mem)
    # allow add via scope "add" - action add_line
    cap = wp.control(add_line, trust_sku="X").as_dict()["data-channel-cap"]
    client = TestClient(app)
    r_no = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "add_line", "args": {"sku": "X"}, "cap": cap},
    )
    assert r_no.status_code in (403, 401, 400)
    r_ok = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "add_line", "args": {"sku": "X"}, "cap": cap},
        headers={"X-Channel": "1"},
    )
    assert r_ok.status_code == 200


def test_lab_example_import():
    from examples.workplace_lab import app as lab_app

    assert lab_app.RUNTIME["membership"].room == "lab-cell"
    r = lab_app.wp().dispatch("lab_id", {})
    assert r.ok
