"""I/O channel foundations — authorize, don't drive."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.io_channel import (
    IO_CONSTITUTION,
    IO_LAWS,
    IoChannelError,
    IoGate,
    IoKind,
    IoMethodSpec,
    IoProtocol,
    IoRoomClaim,
    attach_io_gate,
    command_budget_allows,
    event_args_for_intent,
    get_io_gate,
    reading_to_quantity,
)
from ux_channel.quantity import Quantity


SECRET = "io-channel-test-secret-key-32bytes!!"


def _protocol() -> IoProtocol:
    return IoProtocol(
        name="lab.bench",
        methods={
            "flash": IoMethodSpec(
                "flash",
                kind=IoKind.COMMAND,
                scopes=frozenset({"lab", "lab.flash"}),
                unit="count",
                max_magnitude=1,
                allow_event_keys=("dut_id",),
                description="Flash DUT once under budget",
            ),
            "read_temp": IoMethodSpec(
                "read_temp",
                kind=IoKind.READING,
                scopes=frozenset({"lab"}),
            ),
            "video": IoMethodSpec(
                "video",
                kind=IoKind.STREAM,
                scopes=frozenset({"lab"}),
            ),
        },
        events=frozenset({"scanned", "ready"}),
    )


def test_constitution_and_laws_stable():
    assert "adapters" in IO_CONSTITUTION.lower()
    assert "no_effect_without_intent" in IO_LAWS
    assert "mesh_is_not_trust" in IO_LAWS
    assert len(IO_LAWS) >= 8


def test_room_claim_attenuates_only():
    parent = IoRoomClaim(
        room="cell-a",
        scopes=frozenset({"lab", "lab.flash", "view"}),
        peer_id="peer-1",
    )
    child = parent.narrow(frozenset({"lab.flash"}))
    assert child.scopes == frozenset({"lab.flash"})
    with pytest.raises(IoChannelError):
        parent.narrow(frozenset({"lab", "admin"}))


def test_room_claim_expiry_is_not_trust():
    claim = IoRoomClaim(
        room="party",
        scopes=frozenset({"lights"}),
        peer_id="guest",
        expires_at=time.time() - 10,
    )
    assert not claim.alive()
    assert not claim.allows_scope("lights")


def test_gate_command_with_quantity_budget():
    gate = IoGate().register(_protocol())
    claim = IoRoomClaim(
        room="cell-a",
        scopes=frozenset({"lab", "lab.flash"}),
        peer_id="tech-1",
    )
    q = Quantity.from_store(1, "count", source="adapter.lab.flash.budget", revision=1)
    inv = gate.check("lab.bench", "flash", [], claim=claim, quantity=q)
    assert inv.kind is IoKind.COMMAND
    assert inv.method == "flash"

    q_bad = Quantity.from_store(2, "count", source="adapter.lab.flash.budget", revision=1)
    with pytest.raises(IoChannelError):
        gate.check("lab.bench", "flash", [], claim=claim, quantity=q_bad)

    with pytest.raises(IoChannelError):
        gate.check("lab.bench", "flash", [], claim=claim, quantity=None)


def test_gate_refuses_missing_scope_and_stream():
    gate = IoGate().register(_protocol())
    claim = IoRoomClaim(room="cell-a", scopes=frozenset({"view"}), peer_id="p")
    with pytest.raises(IoChannelError):
        gate.check("lab.bench", "flash", [], claim=claim)
    claim2 = IoRoomClaim(room="cell-a", scopes=frozenset({"lab"}), peer_id="p")
    with pytest.raises(IoChannelError):
        gate.check("lab.bench", "video", [], claim=claim2)


def test_reading_stamps_quantity():
    q = reading_to_quantity(
        22.5, "°C", source="adapter.lab.temp", revision=9, principal="probe-1"
    )
    assert float(q.magnitude) == 22.5
    assert q.unit == "°C"
    assert q.provenance.revision == 9


def test_event_to_intent_strips_quantity_keys():
    args = event_args_for_intent(
        "scanned",
        {"dut_id": "d1", "amount": 99, "sku": "x"},
        allow_keys=("dut_id", "sku", "amount"),
    )
    assert args["event"] == "scanned"
    assert args.get("dut_id") == "d1"
    assert "amount" not in args


def test_gate_event_allowlist():
    gate = IoGate().register(_protocol())
    claim = IoRoomClaim(room="cell-a", scopes=frozenset({"lab"}), peer_id="p")
    args = gate.check_event(
        "lab.bench",
        "scanned",
        {"dut_id": "d9", "price": 10},
        claim=claim,
        method_for_keys="flash",
    )
    assert args.get("dut_id") == "d9"
    assert "price" not in args
    with pytest.raises(IoChannelError):
        gate.check_event("lab.bench", "hack", {}, claim=claim)


def test_sealed_bridge_projection():
    proto = _protocol()
    sealed = proto.to_sealed_bridge()
    sealed.validate_call("flash", [])
    with pytest.raises(Exception):
        sealed.validate_call("eval", [])


def test_attach_io_gate_on_channel():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )
    g = attach_io_gate(ch)
    g.register(_protocol())
    assert get_io_gate(ch) is g


def test_command_budget_helper():
    spec = IoMethodSpec("x", kind=IoKind.COMMAND, unit="mg", max_magnitude=5)
    q = Quantity.from_store(3, "mg", source="db.rx.dose", revision=1)
    assert command_budget_allows(spec, q)
    assert not command_budget_allows(
        spec, Quantity.from_store(9, "mg", source="db.rx.dose", revision=1)
    )
