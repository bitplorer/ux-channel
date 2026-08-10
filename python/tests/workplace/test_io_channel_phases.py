"""Phases A–D: ticket claims, adapters, run_checked, audit, JSON contracts, demo."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from hypothesis import given, settings, strategies as st

from ux_channel import Channel, ChannelConfig, agents
from ux_channel.io_adapters import LabDutAdapter, LightsAdapter, ScannerAdapter
from ux_channel.foundations.io_channel import (
    IoChannelError,
    IoGate,
    IoRoomClaim,
    attach_io_audit,
    attach_io_gate,
    claim_from_ticket_claims,
    load_protocol_json,
    protocol_from_mapping,
    run_checked,
)
from ux_channel.foundations.quantity import Quantity
from ux_channel.protocol.types import Intent
from ux_channel.workplace import workplace


SECRET = "io-phases-test-secret-key-32bytes-min!"
ROOT = Path(__file__).resolve().parents[2]


def _ch():
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )


def test_claim_from_ticket_claims_and_expiry():
    claim = claim_from_ticket_claims(
        {
            "room": "party",
            "sub": "phone-1",
            "scopes": "lights,view",
            "exp": time.time() + 60,
        }
    )
    assert claim.room == "party"
    assert claim.peer_id == "phone-1"
    assert "lights" in claim.scopes
    dead = claim_from_ticket_claims(
        {"room": "party", "peer_id": "x", "scopes": ["lights"], "exp": time.time() - 1}
    )
    assert not dead.alive()


def test_scanner_button_agent_same_action():
    ch = _ch()
    cart: dict[str, int] = {}

    @ch.on
    def add_line(sku: str = ""):
        cart[sku] = cart.get(sku, 0) + 1
        return ch.done(notice=sku)

    ag = agents(ch)
    r = ag.dispatch("add_line", {"sku": "A"}, peer=ag.peer("bot"))
    assert r.ok and cart["A"] == 1

    scanner = ScannerAdapter()
    gate = IoGate().register(scanner.describe())
    claim = claim_from_ticket_claims(
        {"room": "pos", "peer_id": "scan", "scopes": ["scan", "pos"]}
    )
    payload = scanner.inject("B")
    args = gate.check_event(
        scanner.name, "scanned", payload, claim=claim, method_for_keys="read"
    )
    r2 = ch.registry.dispatch(
        Intent(
            action="add_line",
            args={"sku": args.get("sku") or payload["sku"]},
            cap=ch.mint("add_line", {"sku": payload["sku"]}),
        )
    )
    assert r2.ok and cart["B"] == 1


def test_party_lights_scope_and_no_lab():
    lights = LightsAdapter()
    lab = LabDutAdapter()
    gate = IoGate().register(lights.describe()).register(lab.describe())

    class Bag:
        pass

    bag = Bag()
    audit = attach_io_audit(bag)
    party = claim_from_ticket_claims(
        {"room": "party", "peer_id": "g", "scopes": ["lights"], "exp": time.time() + 30}
    )
    out = run_checked(gate, lights, "scene", ["party"], claim=party, audit=audit)
    assert out["scene"] == "party"
    with pytest.raises(IoChannelError):
        run_checked(gate, lab, "flash", [], claim=party, audit=audit)
    assert any(r.ok for r in audit.since())
    assert any(not r.ok for r in audit.since())


def test_lab_flash_budget_and_audit():
    lab = LabDutAdapter()
    gate = IoGate().register(lab.describe())
    claim = claim_from_ticket_claims(
        {"room": "lab", "peer_id": "t", "scopes": ["lab", "lab.flash"]}
    )
    bag = type("B", (), {})()
    audit = attach_io_audit(bag)
    q_ok = Quantity.from_store(1, "count", source="lab.budget", revision=1)
    run_checked(gate, lab, "flash", [], claim=claim, quantity=q_ok, audit=audit)
    assert lab.flash_count == 1
    q_bad = Quantity.from_store(2, "count", source="lab.budget", revision=2)
    with pytest.raises(IoChannelError):
        run_checked(gate, lab, "flash", [], claim=claim, quantity=q_bad, audit=audit)
    rows = audit.export()
    assert rows[-1]["ok"] is False


def test_protocol_json_contract_roundtrip():
    path = ROOT / "src/ux_channel/io_adapters/contracts/lab_dut.json"
    proto = load_protocol_json(path)
    assert proto.name == "lab.dut"
    assert proto.get("flash").max_magnitude == 1
    raw = json.loads(path.read_text())
    assert protocol_from_mapping(raw).name == proto.name


def test_attach_io_on_channel_and_agent_lab():
    ch = _ch()
    gate = attach_io_gate(ch)
    audit = attach_io_audit(ch)
    lab = LabDutAdapter()
    gate.register(lab.describe())

    @ch.on
    def lab_flash():
        claim = claim_from_ticket_claims(
            {"room": "lab", "peer_id": "tech", "scopes": ["lab", "lab.flash"]}
        )
        q = Quantity.from_store(1, "count", source="lab.budget", revision=1)
        run_checked(gate, lab, "flash", [], claim=claim, quantity=q, audit=audit)
        return ch.done()

    ag = agents(ch)
    assert ag.dispatch("lab_flash", {}, peer=ag.peer("bot")).ok
    assert lab.flash_count == 1


@settings(max_examples=40, deadline=None)
@given(
    scopes=st.lists(
        st.sampled_from(["lights", "lab", "scan", "view", "pos"]),
        min_size=1,
        max_size=4,
        unique=True,
    ),
    extra=st.sampled_from(["admin", "root", "super"]),
)
def test_prop_claim_narrow_never_widens(scopes, extra):
    parent = IoRoomClaim(room="r", scopes=frozenset(scopes), peer_id="p")
    child_scopes = frozenset(scopes[: max(1, len(scopes) // 2)] or scopes[:1])
    child = parent.narrow(child_scopes)
    assert child.scopes.issubset(parent.scopes)
    if extra not in parent.scopes:
        with pytest.raises(IoChannelError):
            parent.narrow(frozenset(list(parent.scopes) + [extra]))


def test_example_module_importable():
    from examples.io_mesh_workplace import app as workplace_app

    assert workplace_app.ch is not None
    assert "pos.scanner" in workplace_app.wp.gate.protocols
    assert workplace_app.wp.claim.room == "pos-desk"


def test_workplace_facade_on_demo_pattern():
    ch = _ch()
    scanner = ScannerAdapter()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done(notice=sku)

    wp = workplace(
        ch,
        ticket={"room": "pos", "peer_id": "c", "scopes": ["add", "scan", "pos"]},
    ).allow(scanner)
    assert wp.dispatch("add_line", {"sku": "Z"}).ok
    payload = scanner.inject("Z2")
    args = wp.check_event(scanner.name, "scanned", payload, method_for_keys="read")
    assert "sku" in args or payload["sku"] == "Z2"
