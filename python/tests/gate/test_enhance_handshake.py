"""Gate: host handshake + negotiate projection."""
from __future__ import annotations

from ux_channel.enhance.handshake import HandshakeRegistry, PeerSession
from ux_channel.enhance import PeerHello


def test_accept_hello_and_project_drops_delta():
    reg = HandshakeRegistry()
    hello = PeerHello(surfaces=["dom.morph", "dom.toast"], features=["perception.v1"])
    reg.accept_hello("s1", hello)
    result = {
        "v": "1",
        "ok": True,
        "ops": [
            {"op": "morph", "target": "#a", "html": "x"},
            {"op": "delta.patch", "target": "#a", "patch": []},
            {"op": "toast", "message": "ok"},
        ],
    }
    out = reg.project_result("s1", result)
    kinds = [o["op"] for o in out["ops"]]
    assert kinds == ["morph", "toast"]


def test_default_session_keeps_classic():
    sess = PeerSession()
    ops, warnings = sess.project_ops([{"op": "morph", "target": "#x", "html": "1"}])
    assert ops[0]["op"] == "morph"
    assert warnings == []


def test_drop_session():
    reg = HandshakeRegistry()
    reg.accept_hello("s2", {"surfaces": ["dom.toast"]})
    reg.drop("s2")
    assert "s2" not in reg.sessions
