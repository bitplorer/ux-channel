"""Architecture e2e — production CapService + HostRuntime. Gate suite."""

from __future__ import annotations

import pytest

from ux_channel.arch import (
    HostConfig,
    HostRuntime,
    PeerApply,
    PeerRuntime,
    graph,
    make_agent_drivers,
    make_web_drivers,
    new_flow_id,
    project,
    seq,
    toast,
)
from ux_channel.arch.effects import invoke
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.protocol.capability import CapError, CapService


def test_cap_once_replay():
    store = MemoryNonceStore()
    caps = CapService("0123456789abcdef", nonce_store=store)
    tok = caps.mint("Order.pay", {"id": 1}, once=True)
    caps.verify(tok, "Order.pay", {"id": 1})
    with pytest.raises(CapError) as ei:
        caps.verify(tok, "Order.pay", {"id": 1})
    assert "replay" in str(ei.value)


def test_cap_store_down():
    caps = CapService("0123456789abcdef", nonce_store=None)
    tok = caps.mint("Order.pay", {}, once=True, jti="j9")
    with pytest.raises(CapError) as ei:
        caps.verify(tok, "Order.pay", {})
    assert "nonce_store" in str(ei.value)


def test_present_cap_must_verify():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(require_cap=False, demo_mode=True),
    )
    host.registry.config.open_actions.add("Open.ping")

    def ping(args, ctx):
        return {"ok": True, "ops": [{"op": "toast", "message": "pong"}]}

    host.register("Open.ping", ping)
    bad = host.handle_intent({"action": "Open.ping", "args": {}, "cap": "bogus"})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "unauthorized"


def test_project_and_peer_apply_with_flow_meta():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(effects="auto", proofs="off", demo_mode=True, require_cap=False),
    )
    host.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"]})
    g = graph(seq(toast("a"), toast("b")))
    result = host.emit_from_graph(g, session_id="s1", flow_id=new_flow_id(), step=1)
    assert result["ops"][0]["op"] == "seq"
    assert "flow_id" in result["meta"]

    drivers = make_web_drivers()
    peer = PeerApply(drivers)
    rt = PeerRuntime(peer, profiles=["web.v1"], features=["seq"])
    rt.on_result(result)
    msgs = [x[1] for x in peer.ctx["log"] if x[0] == "toast"]
    assert msgs == ["a", "b"]


def test_proofs_roundtrip():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(proofs="require", effects="classic", demo_mode=True, require_cap=False),
    )
    host.set_hello("s1", {"effect_proof": True, "profiles": ["web.v1"]})
    result = host.emit_from_graph(graph(toast("x")), session_id="s1")
    assert "effect" in result["meta"]

    proof = host.proofs
    peer = PeerApply(
        make_web_drivers(),
        proof_service=proof,
        proofs_required=True,
        session_id="s1",
    )
    peer.session_gen = host.sessions["s1"].gen
    peer.ctx["gen"] = peer.session_gen
    peer.apply_result(result)
    assert any(x[0] == "toast" for x in peer.ctx["log"])

    peer2 = PeerApply(
        make_web_drivers(),
        proof_service=proof,
        proofs_required=True,
        session_id="s1",
    )
    peer2.session_gen = host.sessions["s1"].gen
    bad = dict(result)
    bad["ops"] = [{"op": "toast", "message": "forged"}]
    peer2.apply_result(bad)
    assert peer2.ctx["log"] == []
    assert peer2.ctx["reject"] == "proof"


def test_invoke_stamp_check():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False, effects="auto"),
    )
    host.set_hello("s1", {"profiles": ["web.v1"], "features": ["invoke", "seq"]})
    ref = host.grant_stamp("s1", "dom", {"call", "ping"})
    g = graph(invoke(ref, "ping", {"x": 1}, body=[toast("after")]))
    result = host.emit_from_graph(g, session_id="s1")
    assert result["ops"][0]["op"] == "invoke"

    def stamp_check(r, m):
        return host.stamps.allows("s1", r, host.sessions["s1"].gen, m)

    peer = PeerApply(make_web_drivers(), stamp_check=stamp_check)
    peer.apply_result(result)
    assert any(x[0] == "invoke" for x in peer.ctx["log"])
    assert any(x[0] == "toast" and x[1] == "after" for x in peer.ctx["log"])

    g2 = graph(invoke(ref, "evil", {}))
    r2 = host.emit_from_graph(g2, session_id="s1")
    peer2 = PeerApply(make_web_drivers(), stamp_check=stamp_check)
    peer2.apply_result(r2)
    assert any(x[0] == "invoke_denied" for x in peer2.ctx["log"])


def test_flow_store_and_cap_dispatch():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=True),
    )
    flow = host.flows.start("checkout")

    def address(args, ctx):
        host.flows.advance(args["flow_id"], data={"line1": args["line1"]})
        g = graph(toast("address ok"))
        return {
            "ok": True,
            "_graph": g,
            "meta": {"flow_id": args["flow_id"], "step": 2},
        }

    host.register("Checkout.address", address)
    host.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"]})
    args = {"flow_id": flow.flow_id, "line1": "Main"}
    tok = host.caps.mint("Checkout.address", args)
    result = host.handle_intent(
        {"action": "Checkout.address", "args": args, "cap": tok},
        session_id="s1",
    )
    assert result["ok"] is True
    assert result["meta"]["flow_id"] == flow.flow_id
    assert any(o.get("op") == "toast" for o in result["ops"])


def test_agent_drivers():
    tools = {"add": lambda a: a.get("a", 0) + a.get("b", 0)}
    drivers = make_agent_drivers(tools)
    peer = PeerApply(drivers)
    peer.apply_result(
        {"ok": True, "ops": [{"op": "tool", "name": "add", "args": {"a": 2, "b": 3}}]}
    )
    assert ("tool", "add", 5) in peer.ctx["log"]


def test_budget_reject():
    peer = PeerApply(make_web_drivers(), max_nodes=2)
    ops = [{"op": "toast", "message": str(i)} for i in range(5)]
    peer.apply_result({"ok": True, "ops": ops})
    assert peer.ctx["log"] == []
    assert peer.ctx["reject"] == "budget"


def test_revoke_gen_clears_timers():
    peer = PeerApply(make_web_drivers())
    peer.apply_result(
        {
            "ok": True,
            "ops": [{"op": "timer.set", "id": "t1", "ms": 1000, "ops": []}],
        }
    )
    assert "t1" in peer.ctx["timers"]
    peer.bump_gen()
    assert peer.ctx["timers"] == {}


def test_classic_floor_without_hello():
    """No peer hello → project emits classic leaves (IR 0.1 floor)."""
    g = graph(seq(toast("a"), toast("b")))
    ops = project(g, {}, effects="auto")
    assert [o["op"] for o in ops] == ["toast", "toast"]


def test_channel_attach_arch_power_not_public():
    from ux_channel import Channel
    from ux_channel.host.channel import CHANNEL_PUBLIC_API

    ch = Channel.boot(secret="dev-secret-key-32chars-minimum!!!!")
    assert hasattr(ch, "emit_graph")
    assert hasattr(ch, "set_hello")
    assert hasattr(ch, "grant_stamp")
    assert hasattr(ch, "flow_store")
    assert hasattr(ch, "stamps")
    assert "emit_graph" not in CHANNEL_PUBLIC_API
    assert "set_hello" not in CHANNEL_PUBLIC_API
    ch.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"]})
    r = ch.emit_graph(graph(seq(toast("hi"))), session_id="s1")
    assert r.ok
    assert r.ops[0]["op"] == "seq"


def test_inspect_does_not_burn_once():
    store = MemoryNonceStore()
    caps = CapService("0123456789abcdef", nonce_store=store)
    tok = caps.mint("Once.x", {}, once=True)
    data = caps.verify(tok, "Once.x", {}, consume_once=False)
    assert data.get("jti")
    caps.verify(tok, "Once.x", {})
    with pytest.raises(CapError):
        caps.verify(tok, "Once.x", {})


def test_handler_exception_is_internal():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False),
    )

    def boom(args, ctx):
        raise RuntimeError("explode")

    host.register("Boom.go", boom)
    result = host.handle_intent({"action": "Boom.go", "args": {}})
    assert result["ok"] is False
    assert result["error"]["code"] == "internal"
    assert result["ops"] == []


def test_host_config_rejects_bad_modes():
    with pytest.raises(ValueError):
        HostConfig(effects="rich")
    with pytest.raises(ValueError):
        HostConfig(proofs="maybe")
    with pytest.raises(ValueError):
        HostConfig(flow="yes")


def test_channel_boot_installs_memory_nonce():
    from ux_channel import Channel

    ch = Channel.boot(secret="dev-secret-key-32chars-minimum!!!!")
    assert ch.registry.nonce_store is not None
    assert ch.diagnose()["once_jti_enforced"] is True
    tok = ch.registry._caps.mint("Once.x", {}, once=True)
    ch.registry._caps.verify(tok, "Once.x", {})
    with pytest.raises(CapError):
        ch.registry._caps.verify(tok, "Once.x", {})


def test_revoke_session_bumps_gen():
    from ux_channel import Channel

    ch = Channel.boot(secret="dev-secret-key-32chars-minimum!!!!")
    ch.set_hello("s1", {"profiles": ["web.v1"]})
    first = ch._arch_sessions.get_gen("s1")
    nxt = ch.revoke_session("s1")
    assert nxt == first + 1


def test_unknown_flow_is_explicit():
    from ux_channel.arch import FlowError, FlowStore

    store = FlowStore()
    with pytest.raises(FlowError):
        store.advance("missing")


def test_timer_zero_applies_body():
    peer = PeerApply(make_web_drivers())
    peer.apply_result(
        {
            "ok": True,
            "ops": [
                {
                    "op": "timer.set",
                    "id": "t0",
                    "ms": 0,
                    "ops": [{"op": "toast", "message": "now"}],
                }
            ],
        }
    )
    assert any(x[0] == "toast" and x[1] == "now" for x in peer.ctx["log"])


def test_peer_runtime_submit_intent_outbox_and_transport():
    peer = PeerApply(make_web_drivers())
    rt = PeerRuntime(peer, profiles=["web.v1"], features=["seq"])
    rt.enable_outbox()

    def loopback(intent):
        assert intent["meta"]["hello"]["profiles"] == ["web.v1"]
        return {"ok": True, "ops": [{"op": "toast", "message": "from-host"}]}

    rt.set_transport(loopback)
    sent = rt.submit_intent("Counter.inc", {"by": 1}, request_id="r1")
    assert sent["action"] == "Counter.inc"
    assert sent["request_id"] == "r1"
    assert rt.recorded()[0]["action"] == "Counter.inc"
    assert any(x[0] == "toast" and x[1] == "from-host" for x in peer.ctx["log"])


def test_agent_only_project_drops_morph():
    from ux_channel.arch.effects import morph

    g = graph(seq(toast("ok"), morph("#x", "<b>no</b>")))
    ops = project(g, {"profiles": ["agent.v1"], "features": ["seq"]}, effects="auto")
    assert ops[0]["op"] == "seq"
    assert [o["op"] for o in ops[0]["ops"]] == ["toast"]


def test_host_emit_budget():
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False, max_nodes=1),
    )
    host.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"]})
    r = host.emit_from_graph(graph(seq(toast("a"), toast("b"))), session_id="s1")
    assert r["ok"] is False
    assert r["error"]["code"] == "budget"
    assert r["ops"] == []


def test_single_flight():
    from ux_channel.arch import ApplyError

    peer = PeerApply(make_web_drivers())
    assert peer._lock.acquire(blocking=False)
    try:
        with pytest.raises(ApplyError):
            peer.apply_result({"ok": True, "ops": [{"op": "toast", "message": "x"}]})
    finally:
        peer._lock.release()


def test_web_v1_extra_ops_and_profiles():
    from ux_channel.arch import make_trace_drivers, make_wire_drivers

    peer = PeerApply({**make_web_drivers(), **make_trace_drivers(), **make_wire_drivers()})
    peer.apply_result(
        {
            "ok": True,
            "ops": [
                {"op": "push_url", "href": "/next"},
                {"op": "set_text", "target": "#t", "text": "hi"},
                {"op": "record", "name": "step"},
                {"op": "noop"},
            ],
        }
    )
    kinds = [x[0] for x in peer.ctx["log"]]
    assert "push_url" in kinds
    assert "set_text" in kinds
    assert "record" in kinds
    assert "noop" in kinds


def test_flow_meta_is_not_authority():
    """Unknown meta including flow_id must not block apply (ADR 0007)."""
    peer = PeerApply(make_web_drivers())
    peer.apply_result(
        {
            "ok": True,
            "ops": [{"op": "toast", "message": "hi"}],
            "meta": {"flow_id": "flow_x", "not_a_cap": True},
        }
    )
    assert any(x[0] == "toast" for x in peer.ctx["log"])


def test_proofs_require_refuses_peer_without_hello():
    hits = {"n": 0}
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(proofs="require", demo_mode=True, require_cap=False),
    )

    def ping(args, ctx):
        hits["n"] += 1
        return {"ok": True, "ops": [{"op": "toast", "message": "pong"}]}

    host.register("Open.ping", ping)
    bad = host.handle_intent({"action": "Open.ping", "args": {}})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "forbidden"
    assert hits["n"] == 0
    assert bad["ops"] == []

    ok = host.handle_intent(
        {
            "action": "Open.ping",
            "args": {},
            "meta": {"hello": {"effect_proof": True, "profiles": ["web.v1"]}},
        }
    )
    assert ok["ok"] is True
    assert hits["n"] == 1
    assert "effect" in ok["meta"]


def test_request_id_is_not_once():
    hits = {"n": 0}
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False, proofs="off"),
    )

    def ping(args, ctx):
        hits["n"] += 1
        return {"ok": True, "ops": [{"op": "toast", "message": str(hits["n"])}]}

    host.register("Open.ping", ping)
    a = host.handle_intent({"action": "Open.ping", "args": {}, "request_id": "r1"})
    b = host.handle_intent({"action": "Open.ping", "args": {}, "request_id": "r1"})
    assert hits["n"] == 1
    assert a["ops"] == b["ops"]
    host.handle_intent({"action": "Open.ping", "args": {}, "request_id": "r2"})
    assert hits["n"] == 2

