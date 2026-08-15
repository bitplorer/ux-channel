"""Gate: enhance runtime wiring (handshake project + continuation mint + recorder)."""
from __future__ import annotations

from ux_channel.enhance.attach import (
    EnhanceFacade,
    attach_enhance,
    session_id_from_headers,
)
from ux_channel.enhance.asgi_wire import handle_hello, project_after_dispatch, resolve_enhance
from ux_channel.enhance.handshake import HandshakeRegistry
from ux_channel.enhance.negotiation import PeerHello, SurfaceSet, negotiate_ops
from ux_channel.enhance.continuations import Continuation
from ux_channel.enhance.delta import region_hash, prefer_delta
from ux_channel.enhance.recorder import SessionRecorder


class _FakeReg:
    def mint(self, action, args, **kwargs):
        return f"cap:{action}:{sorted(args.items())}"


class _FakeCh:
    def __init__(self):
        self.registry = _FakeReg()
        self.config = type("C", (), {"enhance": True, "enhance_record": True})()


def test_session_id_prefers_header():
    sid = session_id_from_headers({"X-Channel-Session": "abc-123"}, client_ip="1.2.3.4")
    assert sid == "abc-123"


def test_attach_and_hello_project_drops_unsupported():
    ch = _FakeCh()
    fac = attach_enhance(ch, record=True)
    assert isinstance(fac, EnhanceFacade)
    assert ch.enhance is fac

    hello = PeerHello(
        surfaces=["dom.toast", "sys.noop"],
        features=["perception.v1", "continuations"],
        peer_id="peer-1",
    )
    fac.accept_hello("sess-1", hello)

    result = {
        "v": "1",
        "ok": True,
        "ops": [
            {"op": "toast", "message": "hi"},
            {"op": "morph", "target": "#x", "html": "<b>1</b>"},
            {"op": "noop"},
        ],
    }
    out = fac.project_result("sess-1", result)
    ops = [o["op"] for o in out["ops"]]
    assert "toast" in ops
    assert "noop" in ops
    assert "morph" not in ops  # peer did not advertise dom.morph


def test_handle_hello_ack():
    ch = _FakeCh()
    fac = attach_enhance(ch)
    ack = handle_hello(
        fac,
        headers={"x-channel-session": "s9"},
        body={"ir_version": "1", "surfaces": ["dom.toast"], "peer_id": "p"},
        client_ip="127.0.0.1",
    )
    assert ack["ok"] is True
    assert ack["session_id"] == "s9"
    assert ack["surfaces"] == 1


def test_mint_continuation_real_cap():
    ch = _FakeCh()
    fac = attach_enhance(ch)
    cont = fac.mint_continuation(
        event="http.response",
        action="Search.done",
        args={"q": "x"},
        args_from={"status": "event.status"},
        once=True,
    )
    assert isinstance(cont, Continuation)
    assert cont.cap.startswith("cap:Search.done:")
    assert cont.event == "http.response"


def test_project_after_dispatch_without_enhance_passthrough():
    body = project_after_dispatch(
        None,
        headers={},
        result={"v": "1", "ok": True, "ops": [{"op": "toast", "message": "x"}]},
    )
    assert body["ops"][0]["op"] == "toast"


def test_region_hash_stable():
    a = region_hash("<div>hi</div>")
    b = region_hash("<div>hi</div>")
    assert a == b
    assert len(a) == 16


def test_prefer_delta_fallback():
    peer = SurfaceSet(surfaces={"dom.morph"})
    ops = prefer_delta(
        target="#r",
        full_html="<b>1</b>",
        patch=[{"op": "replace"}],
        last_hash=None,
        peer=peer,
    )
    assert ops[0]["op"] == "morph"


def test_recorder_on_facade():
    ch = _FakeCh()
    fac = attach_enhance(ch, record=True)
    fac.accept_hello("s", PeerHello(surfaces=["dom.toast"]))
    fac.record_intent("s", {"action": "A", "args": {}})
    fac.project_result("s", {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "m"}]})
    rec = fac.recorder("s")
    kinds = [e.kind for e in rec.events]
    assert "hello" in kinds
    assert "intent" in kinds
    assert "result" in kinds
