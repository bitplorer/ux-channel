"""Gate tests for Waves A\u2013G enhancement plane (additive only)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from ux_channel.ops import Op, plan, to_classic, from_classic, macros
from ux_channel.enhance import (
    Continuation,
    attach_continuations,
    match_continuation,
    enhance_result,
    strip_unknown_for_classic,
    PeerHello,
    SurfaceSet,
    negotiate_ops,
    Trace,
    Hop,
    attach_trace,
    region_hash,
    prefer_delta,
    SessionRecorder,
)
from ux_channel.enhance.continuations import resolve_args
from ux_channel.enhance.causal import new_trace


def test_wave_a_structured_to_classic():
    ops = plan(
        Op.toast("hi", level="info"),
        Op.morph("#badge", "<span>1</span>"),
        Op.signal_set("cart.n", 1),
    )
    classic = to_classic(ops)
    assert classic[0]["op"] == "toast"
    assert classic[0]["message"] == "hi"
    assert classic[1]["op"] == "morph"
    assert classic[1]["target"] == "#badge"
    assert classic[2]["op"] == "signal.set"
    roundtrip = from_classic(classic)
    assert roundtrip[0].ns == "ui"
    assert roundtrip[0].name == "toast"


def test_wave_a_macros():
    ops = macros.restart_timer("search", 200)
    classic = to_classic(ops)
    assert classic[0]["op"] == "timer.clear"
    assert classic[1]["op"] == "timer.set"
    assert classic[1]["ms"] == 200


def test_wave_b_continuations():
    cont = Continuation(
        event="timer.fired",
        action="search.commit",
        cap="cap.token.xyz",
        args_from={"q": "event.q"},
    )
    result = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "armed"}]}
    enhanced = attach_continuations(result, [cont])
    assert "continuations" in enhanced
    assert enhanced["continuations"][0]["action"] == "search.commit"

    matched = match_continuation(enhanced["continuations"], {"type": "timer.fired", "q": "shoes"})
    assert matched is not None
    args = resolve_args(matched, event={"q": "shoes"})
    assert args["q"] == "shoes"

    classic = strip_unknown_for_classic(enhanced)
    assert "continuations" not in classic
    assert classic["ok"] is True


def test_wave_d_negotiation():
    hello = PeerHello(
        surfaces=["dom.morph", "dom.toast"],
        features=["perception.v1"],
    )
    ops = [
        {"op": "morph", "target": "#a", "html": "x"},
        {"op": "delta.patch", "target": "#a", "patch": []},
        {"op": "toast", "message": "ok"},
    ]
    emitted, warnings = negotiate_ops(ops, hello)
    kinds = [o["op"] for o in emitted]
    assert "morph" in kinds
    assert "toast" in kinds
    assert "delta.patch" not in kinds
    assert any("delta.patch" in w for w in warnings)


def test_wave_e_causal_spine():
    tr = new_trace("intent-1")
    tr.append_hop("host-python", cap="abc")
    tr.append_hop("peer-browser", cap="abc")
    result = {"v": "1", "ok": True, "ops": []}
    out = attach_trace(result, tr)
    assert out["trace"]["intent_id"] == "intent-1"
    assert len(out["trace"]["hops"]) == 2
    assert out["trace"]["hops"][0]["peer"] == "host-python"


def test_wave_f_delta_policy():
    peer = SurfaceSet(surfaces={"dom.morph", "delta.patch"})
    full = prefer_delta(
        target="#r",
        full_html="<b>1</b>",
        patch=[{"op": "replace", "path": "/text", "value": "1"}],
        last_hash=region_hash("<b>0</b>"),
        peer=peer,
    )
    assert full[0]["op"] == "delta.patch"

    classic_peer = SurfaceSet(surfaces={"dom.morph"})
    fallback = prefer_delta(
        target="#r",
        full_html="<b>1</b>",
        patch=[{"op": "replace"}],
        last_hash=None,
        peer=classic_peer,
    )
    assert fallback[0]["op"] == "morph"


def test_wave_g_recorder_roundtrip():
    rec = SessionRecorder(session_id="s1", meta={"app": "test"})
    rec.record_intent({"action": "Cart.add", "args": {"sku": "a"}, "cap": "c"})
    rec.record_result({"ok": True, "ops": [{"op": "toast", "message": "added"}]})
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "session.json"
        rec.save(path)
        loaded = SessionRecorder.load(path)
    assert loaded.session_id == "s1"
    intents = list(loaded.iter_intents())
    assert intents[0]["action"] == "Cart.add"
    results = list(loaded.iter_results())
    assert results[0]["ok"] is True


def test_enhance_result_composes_envelopes():
    base = {"v": "1", "ok": True, "ops": [{"op": "noop"}]}
    cont = Continuation(event="http.response", action="done", cap="c")
    tr = Trace(intent_id="i1", hops=[Hop(peer="h", at=1.0, cap_fingerprint="x")])
    out = enhance_result(base, continuations=[cont], trace=tr)
    assert "continuations" in out and "trace" in out
    assert strip_unknown_for_classic(out)["ops"][0]["op"] == "noop"
