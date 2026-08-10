"""Workplace façade — policy-shaped rooms (stable product surface)."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from hypothesis import given, settings, strategies as st

from ux_channel import Channel, ChannelConfig
from ux_channel.io_adapters import LabDutAdapter, LightsAdapter, ScannerAdapter
from ux_channel.foundations.io_channel import IoChannelError, claim_from_ticket_claims
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import (
    WorkplaceError,
    get_workplace,
    workplace,
)


SECRET = "workplace-test-secret-key-32bytes-min!!"


def _boot():
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )


def test_workplace_dispatch_and_tools_filtered_by_claim():
    ch = _boot()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done(notice=sku)

    @ch.on
    def lab_flash():
        return ch.done(notice="flash")

    @ch.on
    def lights_scene(scene: str = "party"):
        return ch.done(notice=scene)

    wp = workplace(
        ch,
        ticket={
            "room": "pos",
            "peer_id": "clerk",
            "scopes": ["add", "cart", "scan", "pos"],
        },
    )
    assert wp.allows_action("add_line")
    r = wp.dispatch("add_line", {"sku": "S1"})
    assert r.ok

    names = {t["name"] for t in wp.tools_for()}
    assert "add_line" in names
    # lab_flash requires lab scope — filtered out
    assert "lab_flash" not in names
    with pytest.raises(WorkplaceError):
        wp.dispatch("lab_flash", {})


def test_workplace_run_io_and_audit():
    ch = _boot()
    lab = LabDutAdapter()
    lights = LightsAdapter()
    wp = workplace(
        ch,
        ticket={
            "room": "lab",
            "peer_id": "tech",
            "scopes": ["lab", "lab.flash", "view"],
        },
    ).allow(lab, lights)

    q = Quantity.from_store(1, "count", source="lab.budget", revision=1)
    out = wp.run_io("lab.dut", "flash", quantity=q)
    assert out["ok"] is True
    assert lab.flash_count == 1
    assert any(row["method"] == "flash" and row["ok"] for row in wp.export_io_audit())

    # lights not in claim scopes for command — gate/method scopes fail
    with pytest.raises(IoChannelError):
        wp.run_io("home.lights", "scene", ["party"])


def test_workplace_party_ttl_and_rebind():
    ch = _boot()
    lights = LightsAdapter()
    wp = workplace(
        ch,
        ticket={
            "room": "party",
            "peer_id": "guest",
            "scopes": ["lights"],
            "exp": time.time() + 30,
        },
    ).allow(lights)
    wp.run_io("home.lights", "scene", ["dim"])
    assert lights.scene == "dim"

    wp.rebind(
        ticket={
            "room": "party",
            "peer_id": "guest",
            "scopes": ["lights"],
            "exp": time.time() - 1,
        }
    )
    with pytest.raises(WorkplaceError):
        wp.run_io("home.lights", "scene", ["off"])


def test_workplace_scanner_event_to_dispatch():
    ch = _boot()
    cart: list[str] = []

    @ch.on
    def add_line(sku: str = ""):
        cart.append(sku)
        return ch.done()

    scanner = ScannerAdapter()
    wp = workplace(
        ch,
        ticket={"room": "pos", "peer_id": "scan", "scopes": ["scan", "pos", "add"]},
    ).allow(scanner)

    payload = scanner.inject("SKU-9")
    args = wp.check_event(
        scanner.name, "scanned", payload, method_for_keys="read"
    )
    wp.dispatch("add_line", {"sku": args.get("sku") or payload["sku"]})
    assert cart == ["SKU-9"]


def test_workplace_situation_includes_membership():
    ch = _boot()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done()

    wp = workplace(
        ch, ticket={"room": "r1", "peer_id": "p1", "scopes": ["add", "pos"]}
    ).put_facts(cart={"a": 1})
    sit = wp.situation()
    assert sit["workplace"]["room"] == "r1"
    assert sit["workplace"]["alive"] is True
    assert "add_line" in {t["name"] for t in sit["tools"]}


def test_workplace_narrow_and_get():
    ch = _boot()
    wp = workplace(
        ch,
        ticket={
            "room": "cell",
            "peer_id": "x",
            "scopes": ["lab", "lab.flash", "view"],
        },
    )
    wp.narrow(["lab.flash"])
    assert wp.claim.scopes == frozenset({"lab.flash"})
    with pytest.raises(IoChannelError):
        wp.narrow(["lab.flash", "admin"])
    assert get_workplace(ch) is wp


def test_workplace_allow_actions_deny():
    ch = _boot()

    @ch.on
    def add_line(sku: str = ""):
        return ch.done()

    @ch.on
    def clear_cart():
        return ch.done()

    wp = workplace(
        ch,
        ticket={"room": "pos", "peer_id": "c", "scopes": ["*"]},
    ).allow_actions(deny=["clear_cart"])
    assert wp.allows_action("add_line")
    with pytest.raises(WorkplaceError):
        wp.dispatch("clear_cart", {})


@settings(max_examples=30, deadline=None)
@given(scope=st.sampled_from(["lights", "lab", "scan", "pos", "view"]))
def test_prop_snapshot_scopes_sorted(scope):
    ch = _boot()
    wp = workplace(
        ch, ticket={"room": "r", "peer_id": "p", "scopes": [scope, "view"]}
    )
    snap = wp.snapshot()
    assert snap["scopes"] == sorted(snap["scopes"])
    assert snap["alive"] is True
