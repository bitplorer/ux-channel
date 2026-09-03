from ux_channel import Result, morph, toast
from ux_channel.protocol.encode import Navigate, encode_result
from ux_channel.protocol.types import Intent


def test_result_ops_builder():
    r = Result.success(morph("#a", "<div id='a'>1</div>"), toast("hi"))
    assert r.ok
    assert r.v == "1"
    assert r.ops[0]["op"] == "morph"
    assert r.ops[1]["op"] == "toast"
    d = r.to_dict()
    assert d["ops"][0]["target"] == "#a"


def test_encode_navigate():
    r = encode_result(Navigate("/home"))
    assert r.ops[0]["op"] == "navigate"
    assert r.ops[0]["href"] == "/home"


def test_encode_html_with_target():
    r = encode_result("<div>x</div>", default_target="#root")
    assert r.ops[0]["op"] == "morph"
    assert r.ops[0]["html"] == "<div>x</div>"


def test_intent_roundtrip():
    raw = {
        "v": "1",
        "action": "Counter.inc",
        "args": {"n": 2},
        "cap": "tok",
        "request_id": "r1",
    }
    intent = Intent.from_dict(raw)
    assert intent.action == "Counter.inc"
    assert intent.args["n"] == 2
    assert intent.to_dict()["action"] == "Counter.inc"


def test_encode_graph_compiles_to_ops_and_drops_pocket():
    """Handler ``_graph`` sugar becomes Result.ops immediately — no meta pocket."""
    from ux_channel.arch.effects import graph, seq, toast as graph_toast

    r = encode_result({"_graph": graph(graph_toast("hi"))})
    assert r.ok
    assert r.ops[0]["op"] == "toast"
    assert r.ops[0]["message"] == "hi"
    assert "_graph" not in (r.meta or {})
    d = r.to_dict()
    assert "_graph" not in (d.get("meta") or {})
    assert all(isinstance(o, dict) and "op" in o for o in d["ops"])

    # Empty hello → classic floor (seq flattens). Not a Host projector.
    r2 = encode_result({"ok": True, "_graph": graph(seq(graph_toast("a"), graph_toast("b")))})
    assert [o["op"] for o in r2.ops] == ["toast", "toast"]
    assert "_graph" not in (r2.meta or {})

    parked = Result.success(toast("x"), **{"_graph": graph(graph_toast("y"))})
    r3 = encode_result(parked)
    assert r3.ops[0]["op"] == "toast"
    assert r3.ops[0]["message"] == "y"
    assert "_graph" not in (r3.meta or {})


def test_dispatch_op_event_name_field():
    """Regression: _op first param must not be named name (clashes with event name)."""
    from ux_channel.protocol.ops import dispatch
    op = dispatch("modal:opened", detail={"a": 1})
    assert op["op"] == "dispatch"
    assert op["name"] == "modal:opened"
    assert op["detail"] == {"a": 1}
